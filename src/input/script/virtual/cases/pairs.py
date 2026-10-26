"""짝 사례 (최소 대조쌍, notes/evaluation_plan_2026-10-23.md §2.1).

기본 사례에서 판정을 가르는 값 하나만 경계 양쪽으로 바꾼다. 같은 묶음(group)의 기본 사례와 짝 사례를 모두 맞혀야 통과로 센다.
expect_a는 A 정답에서 확인하는 값 (tests/input/test_virtual_charts.py), expect는 B·C·D가 정답을 쓸 때 볼 기대 판정 초안이다.
급여·지침 기대는 A의 초안이라 각 담당자가 공고·지침 원문으로 확정한다.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Pair:
    id: str
    base: str
    params: dict
    group: str
    change: str
    expect_a: dict = field(default_factory=dict)   # 경로 -> 값. 'deemed:규칙'은 상태, 'deemed_gap:규칙'은 gap_days
    expect: dict = field(default_factory=dict)     # B / C / D -> 기대 판정 초안


GROUPS = {
    "G1": ("보조 내분비 종료 후 재발 기간", "VC-0103", "기본: 보조 anastrozole 복용 중 전이 (gap -5)"),
    "G2": ("보조요법 종료 후 무병 기간 (DFI)", "VC-0104", "기본: paclitaxel 종료 240일 뒤 전이. 종료일 2023-01-07 + 6개월 = 181일"),
    "G3": ("PD-L1 점수·검사법", "VC-0104", "기본: 22C3 CPS 12"),
    "G4": ("ER Allred 총점", "VC-0107", "기본: Allred 8 (5+3). 0~2 음성, 3~4 저발현, 5는 비율 점수로 가름, 6~8 양성"),
    "G5": ("PR Allred 총점", "VC-0109", "기본: Allred 5 (3+2). 0~2 음성, 3 이상 양성"),
    "G6": ("HER2 IHC·ISH", "VC-0101", "기본: 간 재생검 HER2 1+ (저발현)"),
}

PAIRS = [
    Pair("VC-0103-g365", "VC-0103", {"adj_gap": 365}, "G1",
         "anastrozole을 전이 365일 전에 부작용으로 중단",
         {"deemed:DEEM-ENDO-ADJ-1Y": "met", "deemed_gap:DEEM-ENDO-ADJ-1Y": 365, "deemed:DEEM-SG-1Y": "met"},
         {"C": "ESMO MBC 그림 2 '보조 ET 중 또는 종료 12개월 이내 재발', PIK3CA wt (fig2-a9baa4) → fulvestrant–CDK4/6",
          "D": "3.다 fulvestrant + CDK4/6 (2차 이상, 간주 규칙 met) 급여 / 3.가 AI + CDK4/6 (1차)은 '보조 AI 종료 1년 이후 재발' 불충족"}),
    Pair("VC-0103-g366", "VC-0103", {"adj_gap": 366}, "G1",
         "anastrozole을 전이 366일 전에 부작용으로 중단",
         {"deemed:DEEM-ENDO-ADJ-1Y": "not_met", "deemed_gap:DEEM-ENDO-ADJ-1Y": 366, "deemed:DEEM-SG-1Y": "not_met"},
         {"C": "ESMO MBC 그림 2 '종료 12개월 넘어 재발' (fig2-1ae139) → AI–CDK4/6",
          "D": "3.가 AI + CDK4/6 (1차) 급여 (종료 1년 이후 재발. '이후'에 365일이 드는지는 D가 원문 확인) / "
               "3.다 fulvestrant + CDK4/6 (2차 이상)은 간주 규칙 not_met이라 불충족"}),
    Pair("VC-0104-dfi180", "VC-0104", {"dfi": 180}, "G2",
         "paclitaxel 종료 180일 뒤 간 전이 (6개월 하루 전)",
         {"deemed:DEEM-SG-1Y": "met", "deemed_gap:DEEM-SG-1Y": 180, "recurrence.metastasis_day.value": 381},
         {"C": "ESMO MBC TNBC 1차 PD-L1+: pembrolizumab–ChT은 무병 기간 6개월 이상일 때 (본문 M44·M45). 6개월 안 재발 갈래 확인",
          "D": "4.가.6 pembrolizumab + 항암 '보조요법 종료 6개월 이후 재발' 불충족 → 급여 아님"}),
    Pair("VC-0104-dfi182", "VC-0104", {"dfi": 182}, "G2",
         "paclitaxel 종료 182일 뒤 간 전이 (6개월 하루 뒤)",
         {"deemed:DEEM-SG-1Y": "met", "deemed_gap:DEEM-SG-1Y": 182, "recurrence.metastasis_day.value": 383},
         {"D": "4.가.6 pembrolizumab '6개월 이후 재발' 충족 → 기본 사례와 같음 (covered_conditions_unverified, 급여인정기관 요건)"}),
    Pair("VC-0104-cps9", "VC-0104", {"pdl1": ("22C3 pharmDx, CPS 9", {"assay": "22C3", "score_type": "CPS", "score": 9})},
         "G3", "PD-L1 22C3 CPS 9",
         {"receptors.pdl1.value.score": 9},
         {"B": "PD-L1 negative (pembrolizumab 기준 22C3 CPS ≥ 10 미달)",
          "C": "ESMO MBC 그림 8 PD-L1- (fig8-b39e9e). 생식세포 BRCA 미시행 → 검사 권고",
          "D": "4.가.6 pembrolizumab CPS 조건 불충족"}),
    Pair("VC-0104-cps10", "VC-0104", {"pdl1": ("22C3 pharmDx, CPS 10", {"assay": "22C3", "score_type": "CPS", "score": 10})},
         "G3", "PD-L1 22C3 CPS 10 (경계)",
         {"receptors.pdl1.value.score": 10},
         {"B": "PD-L1 positive (CPS ≥ 10, 경계 포함)", "D": "4.가.6 CPS 조건 충족 (기본 사례와 같음)"}),
    Pair("VC-0104-sp142", "VC-0104", {"pdl1": ("SP142, IC 1%", {"assay": "SP142", "score_type": "IC", "score": 1})},
         "G3", "PD-L1 검사법 SP142, IC 1% (22C3 결과 없음)",
         {"receptors.pdl1.value.assay": "SP142"},
         {"B": "pembrolizumab 판정에는 쓰지 않음 (검사법이 기준과 다름). atezolizumab 기준 SP142 IC ≥ 1% positive",
          "C": "ESMO MBC 그림 8 PD-L1+ 중 atezolizumab–nab-paclitaxel",
          "D": "pembrolizumab: 22C3 결과 없음 → 조건 확인 불가. atezolizumab 급여 기준은 D가 원문 확인"}),
    Pair("VC-0107-er2", "VC-0107", {"er": (1, 1)}, "G4", "ER Allred 2 (1+1)",
         {"receptors.er_percent.value.allred.total": 2},
         {"B": "ER negative. PR 양성(Allred 8)이라 아형은 HR+/HER2- (ER 음성·PR 양성도 HR+, 2026-10-15)"}),
    Pair("VC-0107-er3", "VC-0107", {"er": (2, 1)}, "G4", "ER Allred 3 (2+1)",
         {"receptors.er_percent.value.allred.total": 3},
         {"B": "ER low (저발현, ER-low 태그). 아형 HR+/HER2-",
          "C": "ESMO의 ER-low 언급 (TNBC에 가깝게 다룸) 검색 확인"}),
    Pair("VC-0107-er5ps2", "VC-0107", {"er": (2, 3)}, "G4", "ER Allred 5 (PS 2 + IS 3)",
         {"receptors.er_percent.value.allred.total": 5, "receptors.er_percent.value.allred.ps": 2},
         {"B": "ER low (5점은 비율 점수로 가름: PS 2 = 1~10%)"}),
    Pair("VC-0107-er5ps3", "VC-0107", {"er": (3, 2)}, "G4", "ER Allred 5 (PS 3 + IS 2)",
         {"receptors.er_percent.value.allred.total": 5, "receptors.er_percent.value.allred.ps": 3},
         {"B": "ER positive (5점, PS 3 = 11~33%)"}),
    Pair("VC-0107-er6", "VC-0107", {"er": (3, 3)}, "G4", "ER Allred 6 (3+3)",
         {"receptors.er_percent.value.allred.total": 6},
         {"B": "ER positive"}),
    Pair("VC-0109-pr2", "VC-0109", {"pr": (1, 1)}, "G5", "PR Allred 2 (1+1)",
         {"receptors.pr_percent.value.allred.total": 2},
         {"B": "PR negative. ER 양성이라 아형은 HR+/HER2- 그대로"}),
    Pair("VC-0109-pr3", "VC-0109", {"pr": (2, 1)}, "G5", "PR Allred 3 (2+1)",
         {"receptors.pr_percent.value.allred.total": 3},
         {"B": "PR positive (3점 이상)"}),
    Pair("VC-0101-her2-0", "VC-0101", {"her2": "0"}, "G6", "간 재생검 HER2 IHC 0, 막 염색 없음",
         {"receptors.her2_ihc.value.score": "0"},
         {"B": "HER2 negative (0). 원발 1+와 다름 → reason에 변화 기록, 전이성 HER2 재판정 확인"}),
    Pair("VC-0101-her2-0f", "VC-0101", {"her2": "0f"}, "G6", "간 재생검 HER2 IHC 0 + 희미한 불완전 막 염색 (<10%)",
         {"receptors.her2_ihc.value.faint": True},
         {"B": "HER2 ultralow (심평원 기준 최종 음성, 아형 HER2-)", "C": "이후 차수에서 T-DXd 갈래 (ESMO MBC 그림 4 HER2 low or ultralow)"}),
    Pair("VC-0101-her2-2n", "VC-0101", {"her2": "2+n"}, "G6", "간 재생검 HER2 IHC 2+, SISH 비증폭",
         {"receptors.her2_ihc.value.score": "2+", "receptors.her2_ish.value.result": "not_amplified"},
         {"B": "HER2 low (2+ / ISH 비증폭)"}),
    Pair("VC-0101-her2-2a", "VC-0101", {"her2": "2+a"}, "G6", "간 재생검 HER2 IHC 2+, SISH 증폭",
         {"receptors.her2_ish.value.result": "amplified"},
         {"B": "HER2 positive → 아형 HR+/HER2+ (재생검 기준)",
          "C": "ESMO MBC HER2+ 1차 (그림 5, ER+) — 전이 후 HER2 표적 치료 없음",
          "D": "HER2 표적 요법 행이 후보가 됨 (고식적 항암)"}),
    Pair("VC-0101-her2-3p", "VC-0101", {"her2": "3+"}, "G6", "간 재생검 HER2 IHC 3+",
         {"receptors.her2_ihc.value.score": "3+"},
         {"B": "HER2 positive → 아형 HR+/HER2+", "C": "VC-0101-her2-2a와 같음", "D": "VC-0101-her2-2a와 같음"}),
]
BY_ID = {p.id: p for p in PAIRS}


def get(fields: dict, path: str):
    """expect_a 경로 값. 'deemed:규칙' / 'deemed_gap:규칙' / 'a.b.c' (fields 아래 경로)."""
    if path.startswith(("deemed:", "deemed_gap:")):
        kind, rule = path.split(":", 1)
        d = next(x for x in fields["deemed_lines"] if x["rule_id"] == rule)
        return d["status"] if kind == "deemed" else d["gap_days"]
    cur = fields
    for k in path.split("."):
        cur = cur[k]
    return cur
