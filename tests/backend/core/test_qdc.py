"""Conformance tests for the REFI-QDA Codebook (.qdc) serializer.

The rules asserted here are transcribed from the REFI-QDA 1.5 standard's
``Codebook.xsd`` (namespace ``urn:QDA-XML:codebook:1.0``)::

    CodeBookType: sequence(Codes, Sets?)          attr: origin
    CodesType:    sequence(Code+)
    CodeType:     sequence(Description?, Code*)
                  attrs: guid (required), name (required),
                         isCodable (required), color (optional)
    GUIDType:     ([0-9a-fA-F]{8}-{4}-{4}-{4}-{12}) or the same in braces
    RGBType:      #RRGGBB or #RGB

There is no XSD validator in this project's dependencies and the schema
host is not reachable, so the constraints are checked directly rather
than by validating against a downloaded .xsd. They are pinned here
because a .qdc that violates them is rejected by the QDA software the
format exists to reach -- which is a silent failure for the researcher,
who only finds out at import time in the other tool.
"""

from __future__ import annotations

import colorsys
import re
import uuid
import xml.etree.ElementTree as ET

import pytest

from backend.app.core.qdc import (
    QDC_NAMESPACE,
    code_uid_to_color_hex,
    code_uid_to_guid,
    serialize_codes_to_qdc,
)

GUID_RE = re.compile(
    r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
    r"|(\{[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\})"
)
RGB_RE = re.compile(r"#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})")

NS = {"q": QDC_NAMESPACE}
CODE_TAG = f"{{{QDC_NAMESPACE}}}Code"


def _code(code_uid, name, position, *, family_uid="", family_name="", **fields):
    row = {
        "code_uid": code_uid,
        "family_uid": family_uid,
        "family_name": family_name,
        "name": name,
        "position": position,
        "body": "",
        "definition": None,
        "inclusion": None,
        "exclusion": None,
        "keywords": None,
        "example": None,
    }
    row.update(fields)
    return row


def _sample():
    return [
        _code(
            "3f2b1a9c4d5e6f708192a3b4c5d6e7f8", "Trust in clinicians", 1,
            family_uid="aaaabbbbccccddddeeeeffff00001111", family_name="Relational",
            definition="Confidence in a clinician's judgement.",
            inclusion="Explicit statements of confidence.",
        ),
        _code(
            "c1", "Waiting", 2,
            family_uid="aaaabbbbccccddddeeeeffff00001111", family_name="Relational",
            definition="Time spent waiting for care.",
        ),
        _code("99887766-5544-3322-1100-aabbccddeeff", "Standalone", 3, definition="No family."),
    ]


class TestSchemaConformance:
    def test_root_is_codebook_in_the_refi_namespace(self):
        root = ET.fromstring(serialize_codes_to_qdc(_sample()))
        assert root.tag == f"{{{QDC_NAMESPACE}}}CodeBook"

    def test_root_carries_origin_and_no_name_attribute(self):
        """CodeBookType declares ``origin`` and nothing else -- a ``name``
        on the root is the schema violation the earlier implementation had.
        """
        root = ET.fromstring(serialize_codes_to_qdc(_sample()))
        assert root.get("origin")
        assert set(root.attrib) == {"origin"}

    def test_every_guid_matches_GUIDType(self):
        root = ET.fromstring(serialize_codes_to_qdc(_sample()))
        guids = [c.get("guid") for c in root.iter(CODE_TAG)]
        assert guids
        for guid in guids:
            assert GUID_RE.fullmatch(guid), f"{guid!r} is not a GUIDType"

    def test_every_color_matches_RGBType(self):
        root = ET.fromstring(serialize_codes_to_qdc(_sample()))
        colors = [c.get("color") for c in root.iter(CODE_TAG) if c.get("color") is not None]
        assert colors
        for color in colors:
            assert RGB_RE.fullmatch(color), f"{color!r} is not an RGBType"

    def test_required_attributes_present_on_every_code(self):
        root = ET.fromstring(serialize_codes_to_qdc(_sample()))
        for code in root.iter(CODE_TAG):
            assert code.get("guid") is not None
            assert code.get("name") is not None
            assert code.get("isCodable") in ("true", "false")

    def test_description_precedes_any_nested_code(self):
        """CodeType is ``sequence(Description?, Code*)`` -- a Description
        written after a child Code is out of order and invalid.
        """
        root = ET.fromstring(serialize_codes_to_qdc(_sample()))
        for code in root.iter(CODE_TAG):
            tags = [child.tag.split("}")[-1] for child in code]
            if "Description" in tags:
                assert tags.index("Description") == 0
            assert tags.count("Description") <= 1

    def test_codes_element_is_the_only_child_of_root(self):
        root = ET.fromstring(serialize_codes_to_qdc(_sample()))
        assert [c.tag.split("}")[-1] for c in root] == ["Codes"]


class TestHierarchy:
    def test_family_becomes_a_non_codable_parent_holding_its_codes(self):
        root = ET.fromstring(serialize_codes_to_qdc(_sample()))
        top = list(root.find("q:Codes", NS))
        assert [c.get("name") for c in top] == ["Relational", "Standalone"]

        family = top[0]
        assert family.get("isCodable") == "false"
        children = family.findall("q:Code", NS)
        assert [c.get("name") for c in children] == ["Trust in clinicians", "Waiting"]
        assert all(c.get("isCodable") == "true" for c in children)

    def test_code_without_a_family_is_written_at_the_top_level(self):
        root = ET.fromstring(serialize_codes_to_qdc(_sample()))
        standalone = list(root.find("q:Codes", NS))[1]
        assert standalone.get("name") == "Standalone"
        assert standalone.get("isCodable") == "true"
        assert standalone.findall("q:Code", NS) == []

    def test_two_families_sharing_a_name_stay_separate(self):
        """Grouping is by ``family_uid``, matching
        ``render_codes_to_markdown`` -- a shared ``family_name`` must not
        silently merge two families.
        """
        codes = [
            _code("a1", "A", 1, family_uid="f1", family_name="Same"),
            _code("b1", "B", 2, family_uid="f2", family_name="Same"),
        ]
        root = ET.fromstring(serialize_codes_to_qdc(codes))
        families = list(root.find("q:Codes", NS))
        assert len(families) == 2
        assert [f.get("name") for f in families] == ["Same", "Same"]
        assert families[0].get("guid") != families[1].get("guid")

    def test_code_order_follows_the_order_given(self):
        codes = [_code("z", "Zebra", 1), _code("a", "Aardvark", 2)]
        root = ET.fromstring(serialize_codes_to_qdc(codes))
        assert [c.get("name") for c in root.find("q:Codes", NS)] == ["Zebra", "Aardvark"]


class TestGuidMapping:
    def test_bare_32_hex_uid_is_rehyphenated_not_replaced(self):
        """``uuid4().hex`` -- what this app mints -- is the same UUID
        written without hyphens, so the identity must survive the mapping.
        """
        raw = uuid.uuid4()
        assert code_uid_to_guid(raw.hex) == str(raw)

    def test_already_hyphenated_uid_passes_through(self):
        raw = str(uuid.uuid4())
        assert code_uid_to_guid(raw) == raw

    def test_non_uuid_uid_gets_a_stable_derived_guid(self):
        first = code_uid_to_guid("c1")
        assert GUID_RE.fullmatch(first)
        assert code_uid_to_guid("c1") == first, "must be stable across calls"
        assert code_uid_to_guid("c2") != first, "distinct uids must not collide"

    def test_empty_uid_still_yields_a_valid_guid(self):
        assert GUID_RE.fullmatch(code_uid_to_guid(""))
        assert GUID_RE.fullmatch(code_uid_to_guid(None))


class TestColor:
    @pytest.mark.parametrize(
        "code_uid,expected_hue,expected_lightness",
        [
            ("c1", 238, 73),
            ("a", 97, 72),
            ("u1", 76, 71),
            ("3f2b1a9c4d5e6f708192a3b4c5d6e7f8", 28, 63),
            ("trust_in_clinicians", 280, 55),
            ("", 0, 55),
        ],
    )
    def test_hue_and_lightness_match_the_frontend(self, code_uid, expected_hue, expected_lightness):
        """Pinned against ``getCodeColor`` in
        ``frontend/src/lib/codingUtils.js``, evaluated in node -- the
        exported color is the one the researcher sees on the code in the
        app, so the two must not drift.
        """
        hex_color = code_uid_to_color_hex(code_uid)
        r, g, b = (int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5))
        hue, lightness, _ = colorsys.rgb_to_hls(r, g, b)
        assert round(hue * 360) == expected_hue
        assert round(lightness * 100) == expected_lightness

    def test_color_is_uppercase_six_digit_hex(self):
        assert re.fullmatch(r"#[0-9A-F]{6}", code_uid_to_color_hex("anything"))


class TestOutputShape:
    def test_declaration_is_double_quoted(self):
        assert serialize_codes_to_qdc(_sample()).startswith('<?xml version="1.0" encoding="utf-8"?>\n')

    def test_serialization_is_deterministic(self):
        codes = _sample()
        assert serialize_codes_to_qdc(codes) == serialize_codes_to_qdc(codes)

    def test_xml_special_characters_are_escaped(self):
        codes = [_code("x", "Waiting & <delays>", 1, definition='He said "no" & left')]
        out = serialize_codes_to_qdc(codes)
        assert "Waiting &amp; &lt;delays&gt;" in out
        # Parses back to the original text rather than to escaped markup.
        root = ET.fromstring(out)
        code = list(root.find("q:Codes", NS))[0]
        assert code.get("name") == "Waiting & <delays>"
        assert 'He said "no" & left' in code.find("q:Description", NS).text

    def test_labelled_fields_are_folded_into_one_description(self):
        codes = [
            _code("x", "A", 1, definition="D", inclusion="I", exclusion="E", keywords="K", example="X")
        ]
        root = ET.fromstring(serialize_codes_to_qdc(codes))
        text = list(root.find("q:Codes", NS))[0].find("q:Description", NS).text
        assert text.splitlines() == [
            "Definition: D",
            "Inclusion Criteria: I",
            "Exclusion Criteria: E",
            "Key Words: K",
            "Example: X",
        ]

    def test_code_without_prose_omits_the_description_element(self):
        root = ET.fromstring(serialize_codes_to_qdc([_code("x", "A", 1)]))
        assert list(root.find("q:Codes", NS))[0].find("q:Description", NS) is None

    def test_empty_codebook_serializes_without_raising(self):
        """``CodesType`` requires ``Code+``, so an empty codebook cannot be
        valid in this format. It must still not blow up the export -- see
        ``serialize_codes_to_qdc``'s docstring for why no placeholder code
        is invented to satisfy the validator.
        """
        root = ET.fromstring(serialize_codes_to_qdc([]))
        assert root.find("q:Codes", NS) is not None
        assert list(root.find("q:Codes", NS)) == []
