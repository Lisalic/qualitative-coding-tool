"""Tests for backend/app/core/coder_rollup.py -- the pure reduction from
a row's per-quote ``coder`` values to one AI/Human/Both label (B1).
"""

from backend.app.core.coder_rollup import ROLLUP_AI, ROLLUP_BOTH, ROLLUP_HUMAN, roll_up
from backend.app.storage_models import CODER_AI, CODER_HUMAN


class TestRollUp:
    def test_no_entries_is_none(self) -> None:
        assert roll_up([]) is None

    def test_all_human(self) -> None:
        assert roll_up([CODER_HUMAN, CODER_HUMAN]) == ROLLUP_HUMAN

    def test_all_ai(self) -> None:
        assert roll_up([CODER_AI, CODER_AI]) == ROLLUP_AI

    def test_mixed_is_both(self) -> None:
        assert roll_up([CODER_HUMAN, CODER_AI]) == ROLLUP_BOTH

    def test_mixed_order_independent(self) -> None:
        assert roll_up([CODER_AI, CODER_HUMAN, CODER_AI]) == ROLLUP_BOTH

    def test_single_ai(self) -> None:
        assert roll_up([CODER_AI]) == ROLLUP_AI

    def test_single_human(self) -> None:
        assert roll_up([CODER_HUMAN]) == ROLLUP_HUMAN

    def test_accepts_any_iterable_not_just_a_list(self) -> None:
        assert roll_up(c for c in [CODER_HUMAN, CODER_AI]) == ROLLUP_BOTH
