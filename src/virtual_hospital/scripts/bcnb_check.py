"""BCNB 자료 점검 (환자별 라벨은 출력하지 않고 개수·ID만). 실행: python -m src.virtual_hospital.scripts.bcnb_check data/virtual_hospital/local/bcnb_raw"""
import collections
import json
import re
import sys
import zipfile
from pathlib import Path

import pandas as pd
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
root = Path(sys.argv[1])
out = collections.OrderedDict()

# 1. 임상 표
df = pd.read_excel(root / "patient-clinical-data.xlsx")
out["임상 표 크기"] = df.shape
out["열"] = list(df.columns)
out["결측 (열별)"] = {c: int(n) for c, n in df.isna().sum().items() if n}
idc = "Patient ID"
ids = set(df[idc].astype(int))
out["ID 중복"] = int(df[idc].duplicated().sum())
out["ID 범위"] = (min(ids), max(ids), "빠진 번호", sorted(set(range(1, max(ids) + 1)) - ids)[:20])
for c in ["ER", "PR", "HER2", "HER2 Expression", "Molecular subtype", "ALN status", "Tumour Type", "Surgical",
          "Histological grading"]:
    if c in df:
        out[f"분포 {c}"] = df[c].value_counts(dropna=False).to_dict()
for c in ["Age(years)", "Tumour Size(cm)", "Number of lymph node metastases"]:
    if c in df:
        s = pd.to_numeric(df[c], errors="coerce")
        out[f"범위 {c}"] = {"min": s.min(), "max": s.max(), "숫자 아님": int(s.isna().sum() - df[c].isna().sum())}

# 2. 서로 맞는지
bad = collections.defaultdict(list)
for _, r in df.iterrows():
    pid = int(r[idc])
    e, h = str(r.get("HER2 Expression")), str(r.get("HER2"))
    if e in ("0", "1+") and h != "Negative":
        bad["HER2 0·1+인데 양성"].append(pid)
    if e == "3+" and h != "Positive":
        bad["HER2 3+인데 음성"].append(pid)
    n = pd.to_numeric(r.get("Number of lymph node metastases"), errors="coerce")
    aln = str(r.get("ALN status"))
    if pd.notna(n):
        want = "N0" if n == 0 else "N+(1-2)" if n <= 2 else "N+(>2)"
        if want != aln:
            bad[f"림프절 수와 ALN 구간 불일치"].append(pid)
    k = str(r.get("Ki67"))
    try:
        float(k)
    except ValueError:
        bad["Ki67 숫자 아님 (범위 문자열)"].append(pid)
out["서로 맞지 않음 (개수, 앞 15개 ID)"] = {k: (len(v), v[:15]) for k, v in bad.items()}

# 3. 분할
sp = {}
for name in ("train", "val", "test"):
    txt = (root / "dataset-splitting" / f"{name}_id.txt").read_text(encoding="utf-8")
    sp[name] = [int(x) for x in re.findall(r"\d+", txt)]
allsp = sp["train"] + sp["val"] + sp["test"]
out["분할 인원"] = {k: len(v) for k, v in sp.items()}
out["분할 중복 ID"] = sorted({x for x in allsp if allsp.count(x) > 1})[:20]
out["분할에 없는 임상 ID"] = sorted(ids - set(allsp))[:20]
out["임상에 없는 분할 ID"] = sorted(set(allsp) - ids)[:20]

# 4. 슬라이드·주석
wsi = root / "WSIs"
jpgs = {int(p.stem): p for p in wsi.glob("*.jpg")}
jsons = {int(p.stem): p for p in wsi.glob("*.json")}
out["jpg 수 / json 수"] = (len(jpgs), len(jsons))
out["jpg 없는 임상 ID"] = sorted(ids - set(jpgs))[:20]
out["json 없는 임상 ID"] = sorted(ids - set(jsons))[:20]
out["임상에 없는 jpg"] = sorted(set(jpgs) - ids)[:20]
probs = collections.defaultdict(list)
sizes, n_poly, keys = [], [], collections.Counter()
for pid, p in sorted(jpgs.items()):
    b = p.stat().st_size
    with open(p, "rb") as f:
        head = f.read(2)
        f.seek(-2, 2)
        tail = f.read(2)
    if head != b"\xff\xd8":
        probs["jpg 시작 표시 없음"].append(pid)
    if tail != b"\xff\xd9":
        probs["jpg 끝 표시 없음 (잘림 의심)"].append(pid)
    try:
        with Image.open(p) as im:
            w, h = im.size
        sizes.append((w, h))
    except Exception as ex:                                      # noqa: BLE001
        probs[f"이미지 열기 실패 {type(ex).__name__}"].append(pid)
        continue
    if pid in jsons:
        try:
            a = json.loads(jsons[pid].read_text(encoding="utf-8"))
        except Exception:                                        # noqa: BLE001
            probs["json 읽기 실패"].append(pid)
            continue
        keys.update(a.keys())
        polys = [x for k in a for x in (a[k] if isinstance(a[k], list) else [])]
        n_poly.append(len(polys))
        if not polys:
            probs["주석 다각형 0개"].append(pid)
        for poly in polys:
            v = poly.get("vertices", [])
            if len(v) < 3:
                probs["꼭짓점 3개 미만"].append(pid)
            if any(not (0 <= x <= w and 0 <= y <= h) for x, y in v):
                probs["주석 좌표가 이미지 밖"].append(pid)
                break
out["이미지 크기 (가로·세로 최소/최대)"] = (min(s[0] for s in sizes), max(s[0] for s in sizes),
                                     min(s[1] for s in sizes), max(s[1] for s in sizes)) if sizes else None
out["주석 최상위 키"] = dict(keys)
out["환자당 다각형 수 (최소/중앙/최대)"] = (min(n_poly), sorted(n_poly)[len(n_poly) // 2], max(n_poly)) if n_poly else None
out["슬라이드·주석 문제 (개수, 앞 15개 ID)"] = {k: (len(set(v)), sorted(set(v))[:15]) for k, v in probs.items()}

# 5. paper_patches.zip
try:
    with zipfile.ZipFile(root / "paper_patches.zip") as z:
        names = z.namelist()
        bad_member = z.testzip() if len(names) < 50000 else "건너뜀 (파일 많음)"
    tops = collections.Counter(n.split("/")[0] for n in names)
    out["paper_patches.zip"] = {"파일 수": len(names), "최상위": dict(tops.most_common(5)), "손상 첫 파일": bad_member}
except Exception as ex:                                          # noqa: BLE001
    out["paper_patches.zip"] = f"열기 실패: {type(ex).__name__}: {ex}"

for k, v in out.items():
    print(f"{k}: {v}")
