"""VC-0106b VC-0106과 같은 환자 이야기. 외부 병원 생검 판독과 본원 병리과의 같은 슬라이드 재판독에서 Ki-67이 다름.

외부 생검 판독 25%, 본원 재판독 15%. 같은 검체(생검일 day 0)라 시점으로 고를 수 없다 (IN-5):
proliferation.ki67_percent 칸을 두지 않고 두 값을 conflicts[]에 넣는다. 수술 병리는 Ki-67을 다시 재지 않았다.
(VC-0106은 외부 생검과 본원 수술처럼 시점이 다른 두 값 → 최신 값을 고르는 사례. 2026-11-02 사용자 지적으로
'같은 보고서 안의 두 값'을 이유가 적힌 이야기로 바꿈)
"""
from src.input.script.virtual.cases.vc_0106 import mdt_note, surgery_report
from src.input.script.virtual.virtual_chart import Chart, F, kdate

NOTE = "같은 생검 슬라이드의 판독이 다름 (외부 병원 25%, 본원 병리과 재판독 15%)"


def build() -> Chart:
    c = Chart("VC-0106b", "2022-09-14", 45, ident_no="0116")
    D = c.on
    bx = dict(role="conflict", specimen="primary", observed_date=D(0), note=NOTE)

    d = c.doc("pathology", D(3))
    d.t("<병리 조직검사 결과>\n").ident(55, full=False)
    d.t(f"{kdate(D(3))} 가상의원 판독 (사본). {kdate(D(0))} 좌측 유방 중심 생검. Invasive ductal carcinoma.\n")
    d.put("ER 양성", F("receptors.er_percent", {"result": "positive"}, role="history:newer_result",
                      specimen="primary", observed_date=D(0))).t(", ")
    d.put("Ki-67 25%", F("proliferation.ki67_percent", {"percent": 25}, **bx)).t(".\n")

    d = c.doc("pathology", D(10))
    d.t("[병리 자문 판독]  외부 슬라이드 재판독\n").ident(55, full=False)
    d.t(f"보고일: {kdate(D(10))}\n")
    d.t(f"의뢰 검체: 가상의원 좌측 유방 중심 생검 슬라이드 (생검일 {kdate(D(0))}), 본원 병리과 재판독\n  ")
    d.put("Ki-67: 15%", F("proliferation.ki67_percent", {"percent": 15}, **bx))
    d.t("\n소견: 외부 판독(Ki-67 25%)과 차이 있음. 본원은 열점(hot spot)이 아닌 종양 전체 평균으로 계수함.\n판독의: 박가상\n")

    surgery_report(c, ki67=False)
    mdt_note(c, discussion="논의: Ki-67이 외부 판독 25%, 본원 재판독 15%로 달라 고위험 기준(20%)을 사이에 둠. "
                           "보조 항암 후 내분비요법에 CDK4/6 억제제를 추가할지\n")
    c.omit.add("proliferation.ki67_percent")
    return c
