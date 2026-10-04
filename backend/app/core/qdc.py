"""REFI-QDA Codebook (``.qdc``) serializer.

Writes the codebook interchange format the REFI-QDA standard defines, so
a codebook built here imports into NVivo, ATLAS.ti, MAXQDA, Quirkos and
the other QDA packages that implement it. Export only -- nothing here
parses ``.qdc``, so no XML is ever read from an untrusted source.

The contract below is taken from the REFI-QDA 1.5 standard's
``Codebook.xsd`` (namespace ``urn:QDA-XML:codebook:1.0``; schema
published at http://schema.qdasoftware.org/versions/Codebook/v1.0/)::

    CodeBookType: sequence(Codes, Sets?)          attr: origin
    CodesType:    sequence(Code+)
    CodeType:     sequence(Description?, Code*)
                  attrs: guid (required), name (required),
                         isCodable (required), color (optional)
    GUIDType:     ([0-9a-fA-F]{8}-{4}-{4}-{4}-{12}) or the same in braces
    RGBType:      #RRGGBB or #RGB

Three consequences of that schema drive this module:

* ``CodeBook`` takes **no** ``name`` attribute -- only ``origin``. The
  codebook's own name has nowhere to live in this format, so it is
  carried by the download's filename instead.
* ``guid`` must be a *hyphenated* UUID. This app mints ``code_uid`` as
  ``uuid.uuid4().hex`` -- 32 hex digits with no hyphens -- which does not
  match ``GUIDType``, so uids are mapped through ``code_uid_to_guid``
  rather than written straight through. Emitting the raw uid produces a
  file other QDA software rejects at validation.
* ``Description`` must come *before* any nested ``Code`` (it's an
  ``xsd:sequence``), which is why ``_append_code`` writes it first.

A code family becomes a parent ``Code`` with ``isCodable="false"`` -- a
grouping researchers don't code onto directly -- holding its codes as
nested ``Code`` elements, which is how the standard represents a code
hierarchy. Codes with no family are written at the top level.

Output is deterministic: the same codebook always serializes to the same
bytes, matching the guarantee the rest of ``export_service`` makes.
"""

from __future__ import annotations

import colorsys
import uuid
import xml.etree.ElementTree as ET
from typing import Any, Sequence

from backend.app.core.codebook_render import _body_from_fields
from backend.app.core.export_text import xml_safe

QDC_NAMESPACE = "urn:QDA-XML:codebook:1.0"
QDC_ORIGIN = "Qualitative Coding Tool"

# Namespace for the UUIDv5 fallback in ``code_uid_to_guid``. Fixed
# forever: changing it would hand every code a new guid, and a guid is
# the identity another QDA tool matches a re-import against.
_QDC_UID_NAMESPACE = uuid.UUID("6ba7b812-9dad-11d1-80b4-00c04fd430c8")


def _to_int32(n: int) -> int:
    """JavaScript ``ToInt32`` -- what ``<<`` coerces its operand to."""
    n &= 0xFFFFFFFF
    return n - 0x100000000 if n >= 0x80000000 else n


def _js_code_hash(key: str) -> int:
    """Port of the string hash in ``frontend/src/lib/codingUtils.js``.

    Mirrors JavaScript's semantics exactly rather than approximately: only
    ``<<`` coerces to int32 there, while the running value stays a
    float64, so masking every iteration (as a naive port does) drifts from
    the browser and the exported colors stop matching the ones on screen.
    The value stays well inside 2**53, so plain Python ints reproduce it.
    """
    h = 0
    for ch in key:
        # `<<` wraps its RESULT back to int32 too, not just its operand --
        # without the outer coercion this drifts once a key is long enough
        # to overflow, and the colors stop matching the browser's.
        h = ord(ch) + (_to_int32(_to_int32(h) << 5) - h)
    return h


def code_uid_to_color_hex(code_uid: str | None) -> str:
    """The code's on-screen color as ``#RRGGBB``.

    ``getCodeColor`` in ``frontend/src/lib/codingUtils.js`` returns
    ``hsl(h, 85%, l%)``; the schema's ``RGBType`` only accepts hex, so the
    same HSL is converted here. Exported colors therefore match what the
    researcher sees in the app.
    """
    h = _js_code_hash(str(code_uid or ""))
    hue = abs(h) % 360
    lightness = (55 + (abs(h) % 20)) / 100.0
    r, g, b = colorsys.hls_to_rgb(hue / 360.0, lightness, 0.85)
    return f"#{round(r * 255):02X}{round(g * 255):02X}{round(b * 255):02X}"


def code_uid_to_guid(code_uid: str | None) -> str:
    """Map an app ``code_uid`` onto a schema-valid ``GUIDType``.

    Identity-preserving where it can be: a 32-hex-digit uid (what
    ``uuid4().hex`` produces, the normal case) is the same UUID merely
    written without hyphens, so it is re-hyphenated rather than replaced.
    An already-hyphenated uid passes through lowercased. Anything else --
    a hand-written or model-supplied uid like ``"c1"`` -- has no UUID
    reading at all, so it gets a UUIDv5 derived from it: stable across
    exports, and distinct for distinct uids.
    """
    raw = str(code_uid or "").strip()
    try:
        # Accepts both the hyphenated and bare-hex spellings of a real UUID.
        return str(uuid.UUID(raw))
    except ValueError:
        return str(uuid.uuid5(_QDC_UID_NAMESPACE, raw))


def _field(code: Any, name: str) -> Any:
    """Read ``name`` off a ``CodebookCode`` row or a ``CodeRow`` dict."""
    if isinstance(code, dict):
        return code.get(name)
    return getattr(code, name, None)


def _description_for(code: Any) -> str:
    """The code's labelled prose, as one ``Description`` string.

    ``Description`` is a single ``xsd:string``, but a code here carries
    definition/inclusion/exclusion/keywords/example separately, so they
    are folded into one labelled block by the same helper that builds the
    markdown body -- the labels a reader sees in the app are the labels
    they see in the imported codebook.
    """
    body = _body_from_fields(
        definition=_field(code, "definition"),
        inclusion=_field(code, "inclusion"),
        exclusion=_field(code, "exclusion"),
        keywords=_field(code, "keywords"),
        example=_field(code, "example"),
    )
    return (body or (_field(code, "body") or "")).strip()


def _xml_text(value: Any) -> str:
    # ElementTree escapes markup but writes forbidden control characters
    # straight through, so one vertical tab pasted from Word made the
    # whole .qdc unreadable -- see ``core/export_text.py``.
    return xml_safe(value or "")


def _append_code(parent: ET.Element, code: Any) -> ET.Element:
    """Append one codable ``Code``, ``Description`` first per the schema."""
    element = ET.SubElement(
        parent,
        "Code",
        {
            "guid": code_uid_to_guid(_field(code, "code_uid")),
            "name": _xml_text(_field(code, "name")),
            "isCodable": "true",
            "color": code_uid_to_color_hex(_field(code, "code_uid")),
        },
    )
    description = _description_for(code)
    if description:
        ET.SubElement(element, "Description").text = _xml_text(description)
    return element


def serialize_codes_to_qdc(
    codes: Sequence[Any],
    *,
    origin: str = QDC_ORIGIN,
) -> str:
    """Serialize codebook codes to a REFI-QDA ``.qdc`` XML document.

    ``codes`` are taken in the order given -- ``export_service`` has
    already sorted them by ``(position, code_uid)`` -- so families appear
    in the order a researcher arranged them rather than alphabetically.

    One schema edge is deliberately left as-is: ``CodesType`` requires at
    least one ``Code``, so a codebook with no codes serializes to an empty
    ``<Codes/>`` that won't validate. Inventing a placeholder code to
    satisfy the validator would put a code in the researcher's codebook
    that they never wrote, which is worse than a file another tool
    declines to import.
    """
    root = ET.Element("CodeBook", {"xmlns": QDC_NAMESPACE, "origin": origin})
    codes_element = ET.SubElement(root, "Codes")

    # Group by family in first-appearance order. Grouping by family_uid
    # and not family_name matches `render_codes_to_markdown`: two families
    # that happen to share a name stay two families.
    groups: dict[str, list[Any]] = {}
    order: list[str] = []
    for code in codes:
        family_uid = str(_field(code, "family_uid") or "")
        if family_uid not in groups:
            groups[family_uid] = []
            order.append(family_uid)
        groups[family_uid].append(code)

    for family_uid in order:
        group = groups[family_uid]
        family_name = _xml_text(_field(group[0], "family_name"))

        if not family_uid or not family_name:
            for code in group:
                _append_code(codes_element, code)
            continue

        family_element = ET.SubElement(
            codes_element,
            "Code",
            {
                "guid": code_uid_to_guid(family_uid),
                "name": family_name,
                # A family is a grouping, not something a researcher codes
                # a segment onto, so it is explicitly not codable.
                "isCodable": "false",
            },
        )
        for code in group:
            _append_code(family_element, code)

    ET.indent(root, space="  ")
    body = ET.tostring(root, encoding="unicode")
    # ElementTree writes the declaration with single quotes. Valid XML, but
    # every .qdc in the wild uses the double-quoted spelling, so emit that
    # rather than hand commercial QDA software an unfamiliar-looking header.
    return f'<?xml version="1.0" encoding="utf-8"?>\n{body}\n' 
