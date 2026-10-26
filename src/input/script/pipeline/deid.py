"""IN-0 비식별화 [규칙] (notes/input_module_design.md §2 IN-0, §7 결정 5·6).

정규식으로 차트 전체에서 식별정보를 찾아 대응표를 만들고, LLM에 보낼 문서마다 같은 대응표로 가린다.
대응표는 메모리에만 두고 파일로 저장하지 않으며 LLM에 넘기지 않는다. 인용 확인(quote.locate)이 이 표로 구절을 되돌린다.

- 이름: '환자명·성명·이름' 또는 '담당의·판독의·집도의·Pathologist' 같은 이름표 뒤 한글 2~4자. 찾은 이름은 문서 어디서든 가린다
- 등록번호: '등록번호·병록번호·MRN' 뒤 숫자
- 주민번호: 앞 6자리-뒷자리 (뒤를 *로 가린 표기 포함)
- 연락처: 0으로 시작하는 전화번호
- 주소: '주소:' 뒤, 또는 시·도 이름으로 시작해 시·군·구가 이어지는 줄

남기는 것: 날짜, 나이·성별(F/54), 병원·검사기관 이름 (판정과 근거 확인에 필요).
"""
from __future__ import annotations

import re

PROVINCES = "서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주"
PATTERNS = [  # (종류, 정규식). 값은 첫 번째 묶음 (없으면 전체)
    ("이름", re.compile(r"(?:환자명|성명|이름|담당의|주치의|판독의|집도의|의뢰의|Name|Pathologist|Radiologist|Physician)"
                       r"\s*[:：]\s*([가-힣]{2,4})(?![가-힣])", re.I)),
    ("등록번호", re.compile(r"(?:등록번호|병록번호|MRN|Patient ID)\s*[:：]?\s*(\d{5,})", re.I)),
    ("주민번호", re.compile(r"(?<!\d)(\d{6}-[1-4][\d*]{6})(?![\d*])")),
    ("연락처", re.compile(r"(?<!\d)(0\d{1,2}-\d{3,4}-\d{4})(?!\d)")),
    ("주소", re.compile(rf"(?:주소\s*[:：]\s*(.+)$|^\s*((?:{PROVINCES})\S*\s+\S+(?:시|군|구)\s.*)$)", re.M)),
]


def identifiers(chart: str) -> dict[str, str]:
    """{가림 표시: 원래 값}. 같은 값은 같은 표시 ([이름1]이 문서마다 같은 사람)."""
    found: dict[str, str] = {}
    counts: dict[str, int] = {}
    for kind, pat in PATTERNS:
        for m in pat.finditer(chart):
            value = next((g for g in m.groups() if g), m.group(0)).strip()
            if value in found:
                continue
            counts[kind] = counts.get(kind, 0) + 1
            found[value] = f"[{kind}{counts[kind]}]"
    return {tag: value for value, tag in found.items()}


def mask(text: str, mapping: dict[str, str]) -> str:
    """대응표의 원래 값을 모두 가림 표시로 바꾼다. 긴 값부터 (주소 안의 이름 등)."""
    for tag, value in sorted(mapping.items(), key=lambda kv: -len(kv[1])):
        text = text.replace(value, tag)
    return text
