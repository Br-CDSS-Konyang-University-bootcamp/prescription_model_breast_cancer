"""치료 전 임상 종양 크기(stage.clinical_size_mm) 안전장치 (2026-11-09).

판독지 Findings까지 크기를 뽑게 하면서, 다른 크기가 이 칸에 들어가지 않게 하는 규칙을 확인한다.
"""
import pytest

from src.input.script.pipeline import _choose, _clinical_size


@pytest.mark.parametrize("quote, mm", [
    ("좌측 유방 5.5 cm 종괴", 55),
    ("좌측 유방 5.5 cm 종괴, 좌측 액와 림프절 3개 비대.", 55),     # 한 줄에 림프절이 같이 있어도 유방 마디만 본다
    ("좌측 유방 2.8 cm 종괴 (BI-RADS 5), 좌측 액와 림프절 전이 의심", 28),
    ("우측 유방 2.7 cm 종괴(SUVmax 6.2)", 27),
    ("Left breast 18 mm irregular mass", 18),
])
def test_breast_mass_size(quote, mm):
    assert _clinical_size(quote) == mm


@pytest.mark.parametrize("quote", [
    "간 S4 2.0 cm 종괴",                     # 유방 밖의 종괴
    "좌측 액와 림프절 종괴 1.5 cm",           # 림프절
    "양측 폐 다발성 결절 (최대 1.6 cm)",
    "우측 유방 0.6 cm 낭종 (BI-RADS 2)",      # 양성 병변
    "좌측 유방 1.2 cm 잔존 종괴",             # 치료 뒤 잔존 크기
    "좌측 유방 불규칙 종괴",                  # 크기 없음
])
def test_not_clinical_size(quote):
    assert _clinical_size(quote) is None


def _e(value, date, quote):
    return {"status": "present", "value": value, "source": {"doc_id": "D", "quote": quote}, "_date": date}


def test_earliest_image_wins():
    """치료 전 MRI 3.5 cm 뒤에 같은 유방 1.2 cm 영상이 와도 치료 전 값을 고른다."""
    chosen = _choose("stage.clinical_size_mm", [_e(35, "2025-05-15", "좌측 유방 3.5 cm 종괴"),
                                                _e(12, "2025-08-20", "좌측 유방 1.2 cm 종괴")])
    assert chosen["value"] == 35 and "history" not in chosen


def test_same_day_two_masses_is_conflict():
    chosen = _choose("stage.clinical_size_mm", [_e(28, "2025-05-15", "좌측 유방 2.8 cm 종괴"),
                                                _e(11, "2025-05-15", "좌측 유방 1.1 cm 종괴")])
    assert "conflict" in chosen
