"""Parse an uploaded Reddit dump (``.zst``-compressed or plain NDJSON) into
row dicts shaped like the fixed ``submissions``/``comments`` tables.

Pure parsing -- no database access. ``file_service.upload_zst`` pulls
batches off ``iter_zst_records`` on a worker thread and writes them with
``raw_data_repo.bulk_insert_*`` on the request's async session.
"""

import io
import json
from typing import Iterator

import zstandard as zstd


def decompress_zst_file(file_path: str, chunk_size: int = 16384) -> Iterator[str]:
    """Yield non-empty lines from ``file_path``, reading it as plain UTF-8
    text first and falling back to zstd decompression.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield line
        return
    except UnicodeDecodeError:
        pass

    try:
        dctx = zstd.ZstdDecompressor(max_window_size=2**31)
        with open(file_path, "rb") as ifh:
            reader = dctx.stream_reader(ifh, read_size=chunk_size)
            text_buffer = io.TextIOWrapper(reader, encoding="utf-8", errors="ignore")
            for line in text_buffer:
                line = line.strip()
                if line:
                    yield line
    except Exception as e:
        print(f"Error decompressing {file_path}: {e}")


def _submission_record(data: dict) -> dict | None:
    selftext = data.get("selftext")
    if not selftext or selftext == "[deleted]":
        return None
    return {
        "id": data.get("id"),
        "subreddit": data.get("subreddit"),
        "title": data.get("title"),
        "selftext": selftext,
        "author": data.get("author"),
        "created_utc": data.get("created_utc"),
        "score": data.get("score"),
        "num_comments": data.get("num_comments"),
    }


def _comment_record(data: dict) -> dict | None:
    body = data.get("body")
    if not body or body == "[deleted]":
        return None
    return {
        "id": data.get("id"),
        "subreddit": data.get("subreddit"),
        "body": body,
        "author": data.get("author"),
        "created_utc": data.get("created_utc"),
        "score": data.get("score"),
        "link_id": (data.get("link_id") or "").replace("t3_", ""),
        "parent_id": data.get("parent_id") or "",
    }


def iter_zst_records(file_path: str, data_type: str) -> Iterator[dict]:
    """Yield one row dict per usable line of ``file_path``.

    ``data_type`` is ``"submissions"`` or ``"comments"``. Unparseable
    lines, rows with an empty/``[deleted]`` body, rows without an id, and
    repeated ids (first occurrence wins) are skipped.
    """
    to_record = _submission_record if data_type == "submissions" else _comment_record
    seen: set[str] = set()
    for line in decompress_zst_file(file_path):
        try:
            data = json.loads(line)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        record = to_record(data)
        if record is None or not record["id"] or record["id"] in seen:
            continue
        seen.add(record["id"])
        yield record
