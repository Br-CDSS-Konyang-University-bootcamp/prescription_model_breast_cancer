"""타일 벡터 .h5 폴더 → 슬라이드 벡터 하나씩 (.npz). 병리 유사 환자 검색용 (slide_embeddings).

타일 벡터(슬라이드당 수천 개 × 1,536차원)는 서버에 두고, 이 파일만 받아 DB에 넣는다.
numpy와 h5py만 쓰므로 이 저장소가 없는 GPU 서버에서도 파일 하나만 복사해 돌릴 수 있다.

모으는 방식: 종양 타일(tumor_tile)이 있으면 종양 타일 평균 (mean_tumor), 없으면 모든 타일 평균 (mean_all).

    python embed_slides.py <h5 폴더> <출력.npz>
    (저장소 안에서는 python -m src.virtual_hospital.scripts.embed_slides <h5 폴더> <출력.npz>)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np


def pool(path: Path) -> dict:
    import h5py
    with h5py.File(path, "r") as h:
        feats = h["features"][:].astype(np.float32)
        tumor = h["tumor_tile"][:].astype(bool) if "tumor_tile" in h else None
        attrs = {k: (v.decode() if isinstance(v, bytes) else v) for k, v in h.attrs.items()}
    use = tumor if tumor is not None and tumor.any() else np.ones(len(feats), bool)
    return {"vector": feats[use].mean(axis=0), "n_tiles": len(feats), "n_tumor": int(tumor.sum()) if tumor is not None else -1,
            "pooling": "mean_tumor" if tumor is not None and tumor.any() else "mean_all",
            "encoder": str(attrs.get("encoder", "")), "tile_px": int(attrs.get("tile", attrs.get("patch", 0))),
            "input_px": int(attrs.get("input", 0)), "mpp": float(attrs.get("mpp", np.nan))}


def main(argv: list[str]) -> int:
    src, out = Path(argv[0]), Path(argv[1])
    files = sorted(p for p in src.iterdir() if p.suffix == ".h5")
    rows, bad = [], []
    for i, f in enumerate(files, 1):
        try:
            rows.append((f.stem, pool(f.resolve())))
        except Exception as ex:                                    # noqa: BLE001 — 깨진 파일은 건너뛰고 적는다
            bad.append(f"{f.name}: {type(ex).__name__}: {ex}")
        if i % 100 == 0:
            print(f"{i}/{len(files)}", flush=True)
    keys = ["n_tiles", "n_tumor", "tile_px", "input_px", "mpp"]
    np.savez_compressed(out, names=np.array([n for n, _ in rows]), vectors=np.stack([r["vector"] for _, r in rows]),
                        pooling=np.array([r["pooling"] for _, r in rows]), encoder=np.array([r["encoder"] for _, r in rows]),
                        **{k: np.array([r[k] for _, r in rows]) for k in keys})
    print(f"{out}: 슬라이드 {len(rows)}개, 차원 {rows[0][1]['vector'].shape[0] if rows else 0}, 실패 {len(bad)}")
    for b in bad[:20]:
        print("  실패", b)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
