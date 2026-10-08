"""설정 검사. 서버가 뜨기 전에 지킬 수 없는 설정을 거부한다."""

from __future__ import annotations

import pytest

from app.config import Settings
from app.query.catalog import EXAMPLE_QUESTIONS, FEW_SHOT


def test_qry_r016_default_settings_fit_in_one_minute() -> None:
    """QRY-R016 기본값은 3 × (15 + 5) = 60초라 받는다."""
    Settings().check()


def test_qry_r016_settings_over_one_minute_are_refused() -> None:
    """QRY-R016 생성 제한 시간을 30초로 올리면 최악 3 × (30 + 5) = 105초라 거부한다."""
    with pytest.raises(ValueError, match="105"):
        Settings(generation_timeout_seconds=30).check()


def test_qry_r018_examples_do_not_overlap_few_shot() -> None:
    """QRY-R018 사용자에게 보이는 예시 질문은 프롬프트의 예시와 겹치지 않는다."""
    few_shot_questions = {question for question, _ in FEW_SHOT}
    assert few_shot_questions.isdisjoint(EXAMPLE_QUESTIONS)
