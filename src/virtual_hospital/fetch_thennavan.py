"""Thennavan 2021 Data S2 (mmc3.xlsx)를 받아 local/thennavan2021/에 둔다 (M-05 grade 판독 점수).

PMC 부록 주소는 자동 받기를 막는 확인 화면이 떠서, 같은 부록을 공식 API로 주는 Europe PMC를 쓴다
(부록 전체 zip에서 mmc3.xlsx만 꺼내고 zip은 지운다). 원본은 CC BY-NC-ND 4.0이라 git에 넣지 않는다.

실행 (team_project 폴더, team_project 환경): python -m src.virtual_hospital.fetch_thennavan
"""
from __future__ import annotations

import io
import zipfile

import requests

from src.virtual_hospital.tcga import NOTTINGHAM

URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC9028992/supplementaryFiles"


def main() -> int:
    if NOTTINGHAM.exists():
        print(f"이미 있음: {NOTTINGHAM}")
        return 0
    r = requests.get(URL, timeout=300)
    r.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = [n for n in z.namelist() if n.rsplit("/", 1)[-1] == "mmc3.xlsx"]
    if len(names) != 1:
        raise SystemExit(f"zip 안에 mmc3.xlsx가 하나가 아님: {names}")
    NOTTINGHAM.parent.mkdir(parents=True, exist_ok=True)
    NOTTINGHAM.write_bytes(z.read(names[0]))
    print(f"받음: {NOTTINGHAM} ({NOTTINGHAM.stat().st_size:,} 바이트)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
