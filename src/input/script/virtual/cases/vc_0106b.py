"""VC-0106b VC-0106과 같은 환자 이야기, 같은 수술 병리 보고서 안에 Ki-67 두 값 (본문 15%, 판독 요약 25%).

같은 시점의 다른 값은 자동으로 고르지 않는다 (IN-5): proliferation.ki67_percent 칸을 두지 않고 두 값을 conflicts[]에 넣는다.
외부 병원 생검은 넣지 않는다 (시점 차이와 섞이지 않게).
"""
from src.input.script.virtual.cases.vc_0106 import mdt_note, surgery_report
from src.input.script.virtual.virtual_chart import Chart


def build() -> Chart:
    c = Chart("VC-0106b", "2022-09-14", 45, ident_no="0116")
    surgery_report(c, ki67="conflict")
    mdt_note(c)
    c.omit.add("proliferation.ki67_percent")
    return c
