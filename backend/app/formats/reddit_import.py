"""Parse an uploaded Reddit dump (``.zst``-compressed or plain NDJSON) into
row dicts shaped like the fixed ``submissions``/``comments`` tables.

Pure parsing -- no database access. ``file_service.upload_zst`` pulls
batches off ``iter_zst_records`` on a worker thread and writes them with
``raw_data_repo.bulk_insert_*`` on the request's async session.
"""

import codecs
import html
import json
import math
from collections import Counter
from typing import Iterator

import zstandard as zstd

# Every zstd frame starts with these four bytes; anything else is read as
# plain NDJSON.
_ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"

# Bodies Reddit leaves behind when a post/comment is gone.
_REMOVED_BODIES = {"[deleted]", "[removed]"}


class ImportFormatError(ValueError):
    """The upload isn't readable as a zstd-compressed or plain NDJSON dump."""


def decompress_zst_file(file_path: str, chunk_size: int = 16384) -> Iterator[str]:
    """Yield non-empty lines from ``file_path``: zstd-decompressed when it
    starts with the zstd magic number, plain UTF-8 text otherwise.

    Raises :class:`ImportFormatError` on a truncated/corrupt zstd stream or
    text that isn't UTF-8 -- an import that silently stopped halfway used
    to be reported as a success.
    """
    with open(file_path, "rb") as fh:
        is_zstd = fh.read(4) == _ZSTD_MAGIC

    try:
        if is_zstd:
            yield from _zstd_lines(file_path, chunk_size)
        else:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                yield from _non_empty_lines(f)
    except (zstd.ZstdError, UnicodeDecodeError) as exc:
        raise ImportFormatError(f"The file could not be read as a Reddit data dump: {exc}") from exc


def _zstd_lines(file_path: str, chunk_size: int) -> Iterator[str]:
    """Decompress frame by frame so a file that ends mid-frame (a
    truncated download) is an error rather than a quietly short import --
    ``stream_reader`` just stops at the end of the input.
    """
    dctx = zstd.ZstdDecompressor(max_window_size=2**31)
    decoder = codecs.getincrementaldecoder("utf-8-sig")()
    dobj = dctx.decompressobj()
    mid_frame = False
    pending = ""
    with open(file_path, "rb") as fh:
        while chunk := fh.read(chunk_size):
            while chunk:
                pending += decoder.decode(dobj.decompress(chunk))
                mid_frame = not dobj.eof
                if dobj.eof:
                    chunk = dobj.unused_data
                    dobj = dctx.decompressobj()
                else:
                    chunk = b""
            *lines, pending = pending.split("\n")
            yield from _non_empty_lines(lines)
    if mid_frame:
        raise ImportFormatError("The .zst file is truncated or corrupt.")
    yield from _non_empty_lines([pending + decoder.decode(b"", final=True)])


def _non_empty_lines(lines: Iterator[str]) -> Iterator[str]:
    for line in lines:
        line = line.strip()
        if line:
            yield line


def _clean_text(value: object) -> str | None:
    """Reddit dumps HTML-escape text (``&amp;``, ``&lt;``) and can carry
    NUL bytes, which Postgres rejects in a text column.
    """
    if value is None:
        return None
    return html.unescape(str(value)).replace("\x00", "")


def _int_or_none(value: object, *, bits: int = 32) -> int | None:
    """An integer column's value from a dump field, or ``None``.

    Dumps from different periods store numbers as ints, floats or
    strings; the database driver rejects anything but an int that fits
    the column, which used to fail the whole upload.
    """
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    limit = 2 ** (bits - 1)
    return int(number) if math.isfinite(number) and -limit <= number < limit else None


def _id(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _submission_record(data: dict) -> dict | None:
    title = _clean_text(data.get("title"))
    selftext = _clean_text(data.get("selftext"))
    if selftext in _REMOVED_BODIES:
        return None
    if not selftext or not selftext.strip():
        selftext = ""
    if not selftext and (not title or not title.strip() or title in _REMOVED_BODIES):
        return None
    return {
        "id": _id(data.get("id")),
        "subreddit": data.get("subreddit"),
        "title": title,
        "selftext": selftext,
        "author": data.get("author"),
        "created_utc": _int_or_none(data.get("created_utc"), bits=64),
        "score": _int_or_none(data.get("score")),
        "num_comments": _int_or_none(data.get("num_comments")),
    }


def _comment_record(data: dict) -> dict | None:
    body = _clean_text(data.get("body"))
    if not body or not body.strip() or body in _REMOVED_BODIES:
        return None
    return {
        "id": _id(data.get("id")),
        "subreddit": data.get("subreddit"),
        "body": body,
        "author": data.get("author"),
        "created_utc": _int_or_none(data.get("created_utc"), bits=64),
        "score": _int_or_none(data.get("score")),
        "link_id": (data.get("link_id") or "").replace("t3_", ""),
        "parent_id": data.get("parent_id") or "",
    }


def iter_zst_records(file_path: str, data_type: str, skipped: Counter | None = None) -> Iterator[dict]:
    """Yield one row dict per usable line of ``file_path``.

    ``data_type`` is ``"submissions"`` or ``"comments"``. Lines that aren't
    a JSON object, rows with no usable text (empty, ``[deleted]``,
    ``[removed]``), rows without an id, and repeated ids (first occurrence
    wins) are skipped -- and tallied by reason in ``skipped``, so the
    upload can say what it left out.
    """
    tally = skipped if skipped is not None else Counter()
    to_record = _submission_record if data_type == "submissions" else _comment_record
    seen: set[str] = set()
    for line in decompress_zst_file(file_path):
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            data = None
        if not isinstance(data, dict):
            tally["unreadable"] += 1
            continue
        record = to_record(data)
        if record is None:
            tally["no_text"] += 1
        elif not record["id"]:
            tally["no_id"] += 1
        elif record["id"] in seen:
            tally["duplicate"] += 1
        else:
            seen.add(record["id"])
            yield record
