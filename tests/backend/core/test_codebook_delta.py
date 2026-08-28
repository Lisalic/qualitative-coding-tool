"""Tests for backend/app/core/codebook_delta.py -- the field-level delta
a compacted (non-materialized, non-keyframe) artifact_versions row
stores instead of a full codebook_codes row set. See
version_service._demote_if_eligible and
ArtifactVersion.codes_materialized's docstring for where this fits.
"""

from backend.app.core.codebook_delta import apply_delta, encode_delta
from backend.app.services.version_service import _codes_hash


def _code(uid, **overrides):
    row = {
        "code_uid": uid, "family_uid": "f1", "family_name": "F", "name": uid,
        "body": "", "definition": None, "inclusion": None, "exclusion": None,
        "keywords": None, "example": None, "position": 0,
    }
    row.update(overrides)
    return row


def _roundtrip_ok(a, b):
    """The property the whole scheme depends on: applying the encoded
    delta to `a` must reconstruct exactly `b`, verified with the same
    canonical hash version_service already uses for no-op suppression.

    ``_codes_hash`` is sensitive to LIST ORDER, not to the `position`
    field's value (real callers always feed it a `version_repo.list_codes`
    result, which is already `ORDER BY position` -- see its docstring).
    ``apply_delta`` always returns its result position-sorted, so `b` is
    sorted here too before hashing, matching what a real DB read of `b`
    would produce -- this fixture's hand-written list literals aren't
    necessarily written in position order.
    """
    delta = encode_delta(a, b)
    reconstructed = apply_delta(a, delta)
    b_sorted = sorted(b, key=lambda c: c["position"])
    assert _codes_hash(reconstructed) == _codes_hash(b_sorted)
    return delta


class TestEncodeApplyRoundTrip:
    def test_no_change(self):
        a = [_code("u1", position=0), _code("u2", position=1)]
        delta = _roundtrip_ok(a, a)
        assert delta == {"added": [], "removed": [], "modified": [], "positions": {}}

    def test_added(self):
        a = [_code("u1", position=0)]
        b = [_code("u1", position=0), _code("u2", position=1)]
        delta = _roundtrip_ok(a, b)
        assert delta["removed"] == []
        assert [c["code_uid"] for c in delta["added"]] == ["u2"]

    def test_removed(self):
        a = [_code("u1", position=0), _code("u2", position=1)]
        b = [_code("u1", position=0)]
        delta = _roundtrip_ok(a, b)
        assert delta["added"] == []
        assert delta["removed"] == ["u2"]

    def test_renamed_field_only(self):
        a = [_code("u1", name="Old", position=0)]
        b = [_code("u1", name="New", position=0)]
        delta = _roundtrip_ok(a, b)
        assert delta["modified"] == [{"code_uid": "u1", "fields": {"name": "New"}}]
        assert delta["positions"] == {}

    def test_content_field_change(self):
        a = [_code("u1", definition="old def", position=0)]
        b = [_code("u1", definition="new def", position=0)]
        delta = _roundtrip_ok(a, b)
        assert delta["modified"] == [{"code_uid": "u1", "fields": {"definition": "new def"}}]

    def test_family_name_only_change_is_captured(self):
        # The codebook_diff.py trap this module deliberately avoids: a
        # family-name-only change (same family_uid) shows as neither
        # `moved` nor `redefined` in diff_codes's display buckets, so a
        # naive "walk diff.renamed/redefined/moved" encoder would silently
        # drop it. encode_delta computes fields directly, not from those
        # buckets, so it must not miss this.
        a = [_code("u1", family_name="Old Family", position=0)]
        b = [_code("u1", family_name="New Family", position=0)]
        delta = _roundtrip_ok(a, b)
        assert delta["modified"] == [{"code_uid": "u1", "fields": {"family_name": "New Family"}}]

    def test_position_only_change(self):
        a = [_code("u1", position=0), _code("u2", position=1)]
        b = [_code("u1", position=1), _code("u2", position=0)]
        delta = _roundtrip_ok(a, b)
        assert delta["modified"] == []
        assert delta["positions"] == {"u1": 1, "u2": 0}

    def test_renamed_and_reordered_in_one_commit(self):
        # The other codebook_diff.py trap: a code that is BOTH renamed
        # and moved to a new position in the same commit never appears in
        # diff_codes's `reordered` bucket at all (renamed takes priority
        # for display). encode_delta computes positions independently of
        # any diff bucket, so this must still round-trip exactly.
        a = [_code("u1", name="Old", position=0), _code("u2", position=1)]
        b = [_code("u1", name="New", position=1), _code("u2", position=0)]
        delta = _roundtrip_ok(a, b)
        assert delta["modified"] == [{"code_uid": "u1", "fields": {"name": "New"}}]
        assert delta["positions"] == {"u1": 1, "u2": 0}

    def test_moved_to_a_different_family(self):
        a = [_code("u1", family_uid="fam1", family_name="Fam1", position=0)]
        b = [_code("u1", family_uid="fam2", family_name="Fam2", position=0)]
        delta = _roundtrip_ok(a, b)
        assert delta["modified"] == [
            {"code_uid": "u1", "fields": {"family_uid": "fam2", "family_name": "Fam2"}}
        ]

    def test_add_remove_and_modify_together(self):
        a = [_code("u1", position=0), _code("u2", position=1), _code("u3", position=2)]
        b = [_code("u1", name="Renamed", position=0), _code("u3", position=1), _code("u4", position=2)]
        delta = _roundtrip_ok(a, b)
        assert set(delta["removed"]) == {"u2"}
        assert [c["code_uid"] for c in delta["added"]] == ["u4"]
        assert delta["modified"] == [{"code_uid": "u1", "fields": {"name": "Renamed"}}]

    def test_churn_cancels_out_to_nothing(self):
        # A code added then removed relative to the anchor nets out to no
        # `added`/`removed` entry at all -- the single-hop-from-anchor
        # design's actual space payoff over a naive incremental chain.
        a = [_code("u1", position=0)]
        b = [_code("u1", position=0)]  # u2 was added and removed in between, net no-op
        delta = encode_delta(a, b)
        assert delta == {"added": [], "removed": [], "modified": [], "positions": {}}

    def test_empty_to_nonempty(self):
        delta = _roundtrip_ok([], [_code("u1", position=0)])
        assert [c["code_uid"] for c in delta["added"]] == ["u1"]

    def test_nonempty_to_empty(self):
        delta = _roundtrip_ok([_code("u1", position=0)], [])
        assert delta["removed"] == ["u1"]


class TestApplyDeltaEdgeCases:
    def test_falsy_delta_returns_codes_unchanged(self):
        a = [_code("u2", position=1), _code("u1", position=0)]
        assert [c["code_uid"] for c in apply_delta(a, None)] == ["u1", "u2"]
        assert [c["code_uid"] for c in apply_delta(a, {})] == ["u1", "u2"]

    def test_modified_entry_for_a_uid_not_present_is_ignored(self):
        # Defensive: a delta referencing a uid that isn't in the base
        # snapshot (shouldn't happen in practice) must not raise.
        a = [_code("u1", position=0)]
        delta = {"added": [], "removed": [], "modified": [{"code_uid": "ghost", "fields": {"name": "x"}}], "positions": {}}
        result = apply_delta(a, delta)
        assert [c["code_uid"] for c in result] == ["u1"]

    def test_result_is_sorted_by_position(self):
        a = [_code("u1", position=5), _code("u2", position=1)]
        result = apply_delta(a, None)
        assert [c["code_uid"] for c in result] == ["u2", "u1"]
