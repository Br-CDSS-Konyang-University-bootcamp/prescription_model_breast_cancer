# src/rag/algorithm_esmo.py
# 실행: team_project 폴더에서 python -m src.rag.algorithm_esmo  (확인용 출력: --show, 그림 하나만: --show mbc 2)
# 입력: data/guidelines/esmo_*.pdf (convert_pdf_to_md.py와 같은 PDF)
# 출력: data/chunks/esmo_algorithm_chunks.json
#
# ESMO 치료 알고리즘 그림(Figure)을 "조건 → 권고" 경로 문장으로 바꾼다 (PROJECT.md §15.6 알고리즘 도식).
# 본문 변환(md)에서는 그림 글자가 권고 사이에 끼어 들어 지웠다 (convert_pdf_to_md.postprocess). 여기서는 PDF를 직접 읽는다.
# 그림은 그림 파일이 아니라 PDF 안의 선·상자(벡터)라서 좌표를 읽을 수 있다:
#   1. 상자: 테두리나 색이 있는 닫힌 도형. 안의 글자가 상자 내용이다 (위첨자는 각주 표시 ^a)
#   2. 연결선: 열린 선과 가는 막대. 끝이 서로 닿는 선은 한 묶음이다
#   3. 화살촉: 작은 삼각형. 뾰족한 끝이 닿은 상자가 도착 상자, 묶음에 닿은 나머지 상자가 출발 상자다
#   4. 상자 밖 글자(PD 등)는 가장 가까운 연결선 묶음의 이름표다. 점선 연결은 '(optional)'로 적는다
#   5. 맨 위 상자에서 끝 상자까지 경로 하나 = 청크 하나. 그림 전체 = 부모 청크 (색인하지 않음)
# ESMO EBC(2024) 그림은 글자를 글꼴이 아닌 도형으로 그려 PDF에서 글자를 읽을 수 없다. 상자·연결선은 똑같이 좌표로 읽고,
# 상자 글자는 data/guidelines/esmo_figure_text.csv(상자 가운데 좌표 → 글자, 그림을 보고 옮겨 적음)에서 가져온다.
# 자동 변환이라 사람 검수가 필요하다 (data/chunks/esmo_algorithm_review.csv, PROJECT.md 남은 과제).
import argparse
import csv
import json
import math
import re
from pathlib import Path

from .chunk_common import CHUNKS_DIR, attach_parent, clean_text, find_biomarker_tags, find_drugs, make_chunk, stable_key
from .chunker_esmo import COPYRIGHT, DOCS, HER2_POS, _ebc_line, _evidence
from .convert_pdf_to_md import GUIDELINES_DIR, _install_symbol_fix, printed_page_range

OUTPUT_JSON = CHUNKS_DIR / "esmo_algorithm_chunks.json"
FIGURE_TEXT_CSV = GUIDELINES_DIR / "esmo_figure_text.csv"
TEXT_MATCH = 5.0   # 글자 표의 좌표와 상자 가운데가 이 거리 안이면 같은 상자
REVIEW_CSV = CHUNKS_DIR / "esmo_algorithm_review.csv"

# 치료 알고리즘 그림만 쓴다 (진단·병기 그림 Figure 1, 겨드랑이 림프절 수술 그림 EBC Figure 3은 약제 권고가 없다).
# 그림 번호: (chunk_id용 이름, subtype, line). line이 None이면 경로에서 판단한다 (EBC: 수술 앞 = 선행, 뒤 = 보조)
FIGURES = {
    "esmo_ebc_2024-02": {
        2: ("overview", ["any"], None),
        4: ("hrpos-et", ["HR+/HER2-", "HR+/HER2+"], ["adjuvant"]),  # 보조 내분비요법 그림
        5: ("hrpos", ["HR+/HER2-"], None),
        6: ("her2pos", HER2_POS, None),
        7: ("tnbc", ["TNBC"], None),
    },
    "esmo_mbc_2026-05": {
        2: ("luminal-1l", ["HR+/HER2-"], ["1L"]),
        3: ("luminal-2l", ["HR+/HER2-"], ["2L"]),
        4: ("luminal-3l", ["HR+/HER2-"], [">=3L"]),
        5: ("her2-1l", HER2_POS, ["1L"]),
        6: ("her2-2l", HER2_POS, ["2L"]),
        7: ("her2-3l", HER2_POS, [">=3L"]),
        8: ("tnbc-1l", ["TNBC"], ["1L"]),
        9: ("tnbc-2l", ["TNBC"], ["2L", ">=3L"]),
        10: ("site-omd", ["any"], ["any"]),
    },
}

TOUCH = 2.5        # 선 끝이 다른 선·상자에 닿았다고 보는 거리 (pt)
TIP_TOUCH = 5.0    # 화살촉 끝과 도착 상자 사이 (상자 윗변의 홈 때문에 조금 넉넉히)
LABEL_NEAR = 12.0  # 상자 밖 글자를 연결선 이름표로 붙이는 거리
THIN = 2.5         # 이보다 가는 채운 도형은 선으로 본다
ARROW_MAX = 12.0   # 화살촉·이음 장식(마름모) 크기 상한
# 경로 문장에 붙이지 않는 각주: 점수 체계 설명은 모든 그림에 같은 문장이다
GENERIC_FOOTNOTE = re.compile(r"was used to calculate scores|ESCAT scores? apply|have been (calculated|defined)",
                              re.IGNORECASE)
CAPTION = re.compile(r"^Figure (\d+)\.\s+(.+)$")
# 그림에만 쓰는 요법 줄임말 → 약 이름 (청크 drugs용. 본문은 그대로 둔다)
REGIMEN_ABBREVIATIONS = {r"\bHP\b": "pertuzumab trastuzumab", r"\bAC/EC\b": "doxorubicin epirubicin cyclophosphamide"}


# ---------- 도형 분류 ----------

def _points(item):
    """그리기 명령 하나의 점들. l: 선, c: 곡선(끝점만), re: 사각형, qu: 사각형."""
    kind = item[0]
    if kind == "l":
        return [item[1], item[2]]
    if kind == "c":
        return [item[1], item[4]]
    if kind == "re":
        r = item[1]
        return [r.tl, r.tr, r.br, r.bl, r.tl]
    if kind == "qu":
        q = item[1]
        return [q.ul, q.ur, q.lr, q.ll, q.ul]
    return []


def _is_white(color):
    return color is not None and all(c > 0.95 for c in color)


def _subpaths(items):
    """그리기 명령을 이어진 조각으로 나눈다. 한 도형 안에 상자 테두리 여러 개가 함께 들어 있는 경우가 있다."""
    parts, current, last = [], [], None
    for it in items:
        pts = _points(it)
        if not pts:
            continue
        if it[0] in ("re", "qu"):
            parts.append(([pts], True))
            continue
        if last is not None and math.dist(last, pts[0]) > 0.5:
            parts.append((current, False))
            current = []
        current.append(pts)
        last = pts[-1]
    if current:
        parts.append((current, False))
    out = []
    for pieces, is_rect in parts:
        pts = [p for piece in pieces for p in piece]
        out.append((pieces, pts, is_rect or math.dist(pts[0], pts[-1]) < 1.5))
    return out


def classify(drawings, region):
    """→ (상자 rect 목록 [(rect, dashed)], 선분 목록 [((x0,y0),(x1,y1), dashed)], 화살촉 [(꼭짓점들, 끝점)], 이음 장식 rect)"""
    import pymupdf
    boxes, segments, arrows, joints = [], [], [], []
    area = region + (-3, -3, 3, 3)
    for d in drawings:
        r = d["rect"]
        # 세로·가로 선은 넓이가 0이라 intersects가 거짓이 된다. 모서리가 영역 안에 있는지로 본다
        if not (area.contains(r.tl) or area.contains(r.br)):
            continue
        dashed = bool(d.get("dashes") and d["dashes"] not in ("[] 0", "[] 0.0"))
        filled = d.get("fill") is not None
        stroked = d.get("color") is not None and "s" in d["type"]
        if filled and (r.width < THIN or r.height < THIN):
            # 가는 막대로 그린 선 (그림 틀도 여기 들어오지만 상자에 닿지 않아 경로에 안 쓰인다)
            if r.width < r.height:
                segments.append(((r.x0 + r.width / 2, r.y0), (r.x0 + r.width / 2, r.y1), dashed))
            else:
                segments.append(((r.x0, r.y0 + r.height / 2), (r.x1, r.y0 + r.height / 2), dashed))
            continue
        for pieces, pts, closed in _subpaths(d["items"]):
            sr = pymupdf.Rect(min(p.x for p in pts), min(p.y for p in pts), max(p.x for p in pts), max(p.y for p in pts))
            if filled and not stroked and sr.width <= ARROW_MAX and sr.height <= ARROW_MAX:
                corners = []
                for p in pts:
                    if all(math.dist(p, q) > 0.5 for q in corners):
                        corners.append(p)
                if len(corners) == 3:
                    # 끝점 = 가장 긴 변의 맞은편 꼭짓점
                    a, b, c = corners
                    sides = [(math.dist(b, c), a), (math.dist(a, c), b), (math.dist(a, b), c)]
                    arrows.append((corners, max(sides, key=lambda s: s[0])[1]))
                else:
                    joints.append(sr)
                continue
            if closed and (stroked or (filled and not _is_white(d["fill"]))) and sr.width > 12 and sr.height > 8:
                boxes.append((sr, dashed))
                continue
            if closed and filled:  # 흰 바탕 (이름표 'PD' 뒤의 흰 사각형 등)
                continue
            if stroked:
                for piece in pieces:
                    for a, b in zip(piece, piece[1:]):
                        segments.append(((a.x, a.y), (b.x, b.y), dashed))
    boxes += _dashed_boxes(segments)
    boxes = _merge_boxes(boxes)
    # EBC 그림은 글자를 글꼴이 아닌 도형으로 그려서 글자 조각이 작은 도형으로 잡힌다. 상자 안의 것은 버린다
    inside = lambda pts: any(all(b.contains(p) for p in pts) for b, _ in boxes)
    arrows = [a for a in arrows if not inside(a[0])]
    joints = [j for j in joints if not inside([j.tl, j.br])]
    return boxes, segments, arrows, joints


def _dashed_boxes(segments):
    """점선 상자는 변(점선 선분 4개)과 둥근 모서리 조각으로 나뉘어 그려진다. 위·아래 가로 점선과
    왼쪽·오른쪽 세로 점선이 사각형을 이루면 상자로 되살리고, 그 조각들은 segments에서 뺀다."""
    import pymupdf
    horiz = [s for s in segments if s[2] and abs(s[0][1] - s[1][1]) < 0.5]
    vert = [s for s in segments if s[2] and abs(s[0][0] - s[1][0]) < 0.5]
    span = lambda s, k: (min(s[0][k], s[1][k]), max(s[0][k], s[1][k]))
    found = []
    for top in horiz:
        for bottom in horiz:
            (tx0, tx1), (bx0, bx1) = span(top, 0), span(bottom, 0)
            dy = bottom[0][1] - top[0][1]
            if not (8 < dy < 80) or min(tx1, bx1) - max(tx0, bx0) < 0.7 * min(tx1 - tx0, bx1 - bx0):
                continue
            x0, x1, y0, y1 = min(tx0, bx0), max(tx1, bx1), top[0][1], bottom[0][1]
            side = lambda v, x: (x - 10 <= v[0][0] <= x + 10 and y0 - 2 <= span(v, 1)[0] and span(v, 1)[1] <= y1 + 2)
            left = [v for v in vert if side(v, x0) and v[0][0] <= x0 + 2]
            right = [v for v in vert if side(v, x1) and v[0][0] >= x1 - 2]
            if left and right:
                r = pymupdf.Rect(left[0][0][0], y0, right[0][0][0], y1)
                found.append((r, True))
                border = r + (-2, -2, 2, 2)
                for s in [s for s in segments if border.contains(s[0]) and border.contains(s[1])
                          and _rect_dist(((s[0][0] + s[1][0]) / 2, (s[0][1] + s[1][1]) / 2), r + (3, 3, -3, -3)) > 0]:
                    segments.remove(s)
    return found


def _merge_boxes(boxes):
    """안쪽 상자와 맞붙은 상자(위 칸 파랑 + 아래 칸 흰색 'If HR+, adjuvant ET')를 하나로 합친다."""
    merged = []
    for rect, dashed in sorted(boxes, key=lambda b: -b[0].get_area()):
        for i, (m, md) in enumerate(merged):
            inside = m.contains(rect) or (m + (-1, -1, 1, 1)).contains(rect)
            x_overlap = min(m.x1, rect.x1) - max(m.x0, rect.x0)
            stacked = (x_overlap > 0.8 * min(m.width, rect.width)
                       and (abs(rect.y0 - m.y1) < 2 or abs(m.y0 - rect.y1) < 2))
            if inside or stacked:
                merged[i] = (m | rect, md and dashed)
                break
        else:
            merged.append((rect, dashed))
    return merged


# ---------- 기하 ----------

def _seg_dist(p, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    t = 0 if length2 == 0 else max(0, min(1, ((p[0] - ax) * dx + (p[1] - ay) * dy) / length2))
    return math.dist(p, (ax + t * dx, ay + t * dy))


def _rect_dist(p, r):
    dx = max(r.x0 - p[0], 0, p[0] - r.x1)
    dy = max(r.y0 - p[1], 0, p[1] - r.y1)
    return math.hypot(dx, dy)


def _crosses(s, t):
    """두 선분이 서로 가로지르는지 (T자·십자 이음. 끝점이 닿지 않아도 이어진 선이다)."""
    (ax, ay), (bx, by) = s[0], s[1]
    (cx, cy), (dx, dy) = t[0], t[1]

    def orient(px, py, qx, qy, rx, ry):
        return (qx - px) * (ry - py) - (qy - py) * (rx - px)

    d1, d2 = orient(cx, cy, dx, dy, ax, ay), orient(cx, cy, dx, dy, bx, by)
    d3, d4 = orient(ax, ay, bx, by, cx, cy), orient(ax, ay, bx, by, dx, dy)
    return d1 * d2 < 0 and d3 * d4 < 0


def _tip_on_line(a, b):
    """화살촉 끝이 다른 연결선에 꽂힘 (점선 화살표가 갈림길 선을 가리키는 경우). 상자 홈처럼 조금 떨어져 있다."""
    return a[0] == "a" and b[0] == "s" and _seg_dist(a[1][1], b[1][0], b[1][1]) <= TIP_TOUCH


class _Union:
    def __init__(self, n):
        self.parent = list(range(n))

    def find(self, i):
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def join(self, i, j):
        self.parent[self.find(i)] = self.find(j)


def connector_groups(segments, arrows, joints, touch=TOUCH):
    """끝이 서로 닿는 선·화살촉·이음 장식을 묶는다. → 묶음 목록 [{segments, arrows, dashed}]"""
    items = [("s", s) for s in segments] + [("a", a) for a in arrows] + [("j", j) for j in joints]
    u = _Union(len(items))

    def ends(item):
        kind, v = item
        if kind == "s":
            return [v[0], v[1]]
        if kind == "a":
            return v[0]
        return [(v.x0, v.y0), (v.x1, v.y1), (v.x0, v.y1), (v.x1, v.y0)]

    def touches(p, item):
        kind, v = item
        if kind == "s":
            return _seg_dist(p, v[0], v[1]) <= touch
        if kind == "a":  # 삼각형의 변에 닿으면 (선은 보통 밑변 가운데에 닿는다)
            c = v[0]
            return any(_seg_dist(p, c[k], c[(k + 1) % 3]) <= touch for k in range(3))
        return _rect_dist(p, v) <= touch

    for i, a in enumerate(items):
        for j in range(i + 1, len(items)):
            b = items[j]
            if (any(touches(p, b) for p in ends(a)) or any(touches(p, a) for p in ends(b))
                    or (a[0] == b[0] == "s" and _crosses(a[1], b[1]))
                    or _tip_on_line(a, b) or _tip_on_line(b, a)):
                u.join(i, j)
    groups = {}
    for i, item in enumerate(items):
        g = groups.setdefault(u.find(i), {"segments": [], "arrows": [], "joints": []})
        g[{"s": "segments", "a": "arrows", "j": "joints"}[item[0]]].append(item[1])
    out = []
    for g in groups.values():
        g["dashed"] = bool(g["segments"]) and all(s[2] for s in g["segments"])
        out.append(g)
    return out


# ---------- 글자 ----------

def _spans(page, region):
    """그림 영역 안의 글자 조각 [(rect, text, size, baseline_y)]."""
    import pymupdf
    out = []
    for block in page.get_text("dict", clip=region)["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                text = span["text"]
                if text.strip():
                    out.append((pymupdf.Rect(span["bbox"]), text, span["size"], span["origin"][1]))
    return out


def _box_text(spans):
    """상자 안 글자 조각 → 한 줄 글. 작은 글자(위첨자)는 ^로 표시하고, 줄이 ']'·':'로 끝나면 항목을 '; '로 나눈다."""
    if not spans:
        return ""
    body = max(s[2] for s in spans)
    lines = []  # [(y, [(x, text)])]
    for rect, text, size, base in sorted(spans, key=lambda s: (s[3], s[0].x0)):
        small = size < 0.8 * body
        piece = f"^{text.strip()}" if small else text
        y = base if not small else base + size  # 위첨자는 아래 기준선 줄에 붙인다
        for ln in lines:
            if abs(ln[0] - y) < 0.6 * body:
                ln[1].append((rect.x0, piece))
                break
        else:
            lines.append((y, [(rect.x0, piece)]))
    out, last_y = "", None
    for y, pieces in sorted(lines):
        gap = last_y is not None and y - last_y > 1.8 * body  # 빈 줄로 띄운 항목 (OMD 그림 마지막 상자)
        last_y = y
        line = re.sub(r"\s+", " ", "".join(p for _, p in sorted(pieces))).strip()
        line = re.sub(r"\s+\^", "^", line)
        if not out:
            out = line
        elif gap:
            out += "; " + line
        elif out.endswith(":"):
            out += " " + line
        elif re.search(r"\](\^[\w,]+)?$", out):
            out += "; " + line
        elif re.search(r"[–—-]$", out):
            out += line
        else:
            out += " " + line
    return clean_text(out).strip()


def footnotes(page, caption_rect, region):
    """그림 설명 아래 각주 a, b, c… → {글자: 문장}. 각주 줄은 작은 위첨자 글자로 시작한다.
    그림과 같은 단(가로 범위)만 읽고, 본문 크기 글자가 나오면 멈춘다."""
    import pymupdf
    notes, current = {}, None
    clip = pymupdf.Rect(region.x0, caption_rect.y1, region.x1, page.rect.y1)
    caption_size = None
    blocks = page.get_text("dict", clip=clip)["blocks"]
    for block in blocks:
        for line in block.get("lines", []):
            spans = line["spans"]
            visible = [s for s in spans if s["text"].strip()]
            if not visible:
                continue
            first = visible[0]
            body = max(s["size"] for s in visible)
            caption_size = caption_size or body
            if body > caption_size * 1.15:  # 그림 아래 본문
                return {k: re.sub(r"\s+", " ", clean_text(v)).strip() for k, v in notes.items()}
            if (re.fullmatch(r"[a-z]", first["text"].strip()) and first["size"] < 0.85 * body
                    and len(visible) > 1):
                current = first["text"].strip()
                notes[current] = "".join(s["text"] for s in spans[spans.index(first) + 1:])
            elif current:
                text = "".join(s["text"] for s in spans)
                if CAPTION.match(text) or text.startswith(("Purple:", "Volume ")):
                    current = None
                else:
                    notes[current] += " " + text
    return {k: re.sub(r"\s+", " ", clean_text(v)).strip() for k, v in notes.items()}


# ---------- 그림 → 그래프 → 경로 ----------

def find_figures(page):
    """쪽의 그림 설명 줄 [(번호, 제목, rect)]. 굵은 'Figure N.'로 시작하는 줄만 (본문의 'see Figure 3'은 빼고)."""
    import pymupdf
    found = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            spans = [s for s in line["spans"] if s["text"].strip()]
            # 굵은 글씨: 글꼴 표시(flags 16) 또는 이름 (Calibri-Bold, AdvTT….B)
            if not spans or not (spans[0]["flags"] & 16 or re.search(r"Bold|\.B$", spans[0]["font"])):
                continue
            text = re.sub(r"\s+", " ", "".join(s["text"] for s in line["spans"])).strip()
            m = CAPTION.match(text)
            if m:
                found.append((int(m.group(1)), clean_text(m.group(2)).strip(), pymupdf.Rect(line["bbox"])))
    return found


def figure_region(page, caption_rect):
    """그림 영역: 그림 설명 바로 위에 붙은 그림 틀(가는 선 사각형). 틀이 없으면 설명 위 도형 전체."""
    import pymupdf
    above = [d["rect"] for d in page.get_drawings() if d["rect"].y1 <= caption_rect.y0 + 2]
    if not above:
        return None
    region = pymupdf.Rect(above[0])
    for r in above[1:]:
        region |= r
    # 설명과 가장 가까운 아래 끝에서 위로 이어진 도형만 (같은 쪽 위에 다른 그림이 있으면 그 틈에서 자른다)
    return region


def load_figure_text(path: Path = FIGURE_TEXT_CSV) -> dict:
    """글자 표 → {(파일 이름, 그림 번호): [(x, y, 글자)]}"""
    table = {}
    if path.exists():
        with open(path, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                table.setdefault((r["file"], int(r["figure"])), []).append((float(r["x"]), float(r["y"]), r["text"]))
    return table


def build_graph(page, region, figure_text=()):
    """→ (상자 목록 [{rect, text, dashed}], 간선 목록 [(출발, 도착, 이름표, 점선)], 남은 글자, 경고)
    figure_text: PDF에 글자가 없는 그림의 상자 글자 [(x, y, 글자)] (load_figure_text)"""
    boxes, segments, arrows, joints = classify(page.get_drawings(), region)
    spans = _spans(page, region)
    nodes, used, warnings = [], set(), []
    unused_text = list(figure_text)
    for rect, dashed in boxes:
        inside = [s for i, s in enumerate(spans) if rect.contains(s[0].tl + (s[0].br - s[0].tl) / 2)]
        used.update(i for i, s in enumerate(spans) if s in inside)
        text = _box_text(inside)
        if not text and figure_text:
            center = ((rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2)
            near = [t for t in figure_text if math.dist(center, t[:2]) <= TEXT_MATCH]
            if near:
                text = near[0][2]
                unused_text = [t for t in unused_text if t is not near[0]]
            else:
                warnings.append(f"글자 표에 없는 상자: 가운데 ({center[0]:.0f}, {center[1]:.0f})")
        if text:
            nodes.append({"rect": rect, "text": text, "dashed": dashed})
    warnings += [f"상자를 못 찾은 글자 표 줄: ({x:.0f}, {y:.0f}) {t}" for x, y, t in unused_text]
    free = [s for i, s in enumerate(spans) if i not in used]

    edges = []
    groups = connector_groups(segments, arrows, joints)
    for g in groups:
        targets = {i for i, n in enumerate(nodes)
                   if any(_rect_dist(tip, n["rect"]) <= TIP_TOUCH for _, tip in g["arrows"])}
        touched = set(targets)
        for i, n in enumerate(nodes):
            for a, b, _ in g["segments"]:
                if _rect_dist(a, n["rect"]) <= TOUCH or _rect_dist(b, n["rect"]) <= TOUCH:
                    touched.add(i)
            for j in g["joints"]:
                if _rect_dist((j.x0 + j.width / 2, j.y0 + j.height / 2), n["rect"]) <= j.width:
                    touched.add(i)
        if len(touched) < 2:
            continue
        sources = touched - targets
        if not targets:  # 화살촉 없는 연결: 위 상자 → 아래 상자
            top = min(touched, key=lambda i: nodes[i]["rect"].y0)
            sources, targets = {top}, touched - {top}
        if not sources:
            warnings.append(f"출발 상자 없는 연결: {[nodes[i]['text'][:30] for i in targets]}")
            continue
        g["nodes"] = touched
        labels = []
        for rect, text, _, _ in free:
            center = (rect.x0 + rect.width / 2, rect.y0 + rect.height / 2)
            if any(_seg_dist(center, a, b) <= LABEL_NEAR for a, b, _ in g["segments"]):
                labels.append((rect.y0, rect.x0, text.strip()))
                g.setdefault("label_spans", []).append(rect)
        label = " ".join(t for _, _, t in sorted(labels)) or None
        for s in sources:
            for t in targets:
                if s == t:
                    continue
                if nodes[s]["dashed"]:
                    # 점선 상자(선택 검사 등)는 경로의 단계가 아니라 도착 상자에 붙는 참고다
                    note = re.sub(r"\s*\(optional\)$", "", nodes[s]["text"])
                    if note not in nodes[t].setdefault("notes", []):
                        nodes[t]["notes"].append(note)
                else:
                    edges.append((s, t, label, g["dashed"]))
    labelled = {id(r) for g in groups for r in g.get("label_spans", [])}
    leftover = [s[1].strip() for s in free if id(s[0]) not in labelled]
    return nodes, edges, leftover, warnings


def paths(nodes, edges):
    """맨 위 상자(들어오는 연결 없음)에서 끝 상자(나가는 연결 없음)까지 모든 경로. → [[(상자, 들어온 간선 이름표, 점선)]]"""
    out_edges = {}
    has_in = set()
    for s, t, label, dashed in edges:
        out_edges.setdefault(s, []).append((t, label, dashed))
        has_in.add(t)
    roots = [i for i in range(len(nodes)) if i not in has_in and i in out_edges]
    roots.sort(key=lambda i: (nodes[i]["rect"].y0, nodes[i]["rect"].x0))
    result = []

    def walk(i, trail):
        nexts = sorted(out_edges.get(i, []), key=lambda e: (nodes[e[0]]["rect"].y0, nodes[e[0]]["rect"].x0))
        nexts = [e for e in nexts if e[0] not in {step[0] for step in trail}]  # 고리 방지
        if not nexts:
            result.append(trail)
            return
        for t, label, dashed in nexts:
            walk(t, trail + [(t, label, dashed)])

    for r in roots:
        walk(r, [(r, None, False)])
    return result


def path_text(nodes, trail):
    parts = []
    for i, label, dashed in trail:
        step = nodes[i]["text"]
        if dashed:
            step += " (optional)"
        if nodes[i].get("notes"):
            step += " (optional: " + "; ".join(nodes[i]["notes"]) + ")"
        if label:
            parts.append(f"[{label}]")
        parts.append(step)
    return " → ".join(parts)


def _path_line(nodes, trail, fixed):
    """MBC는 그림 번호로 정한 차수. EBC는 수술 상자보다 앞의 약물 치료 = 선행, 뒤 = 보조."""
    if fixed:
        return fixed
    texts = [nodes[i]["text"] for i, _, _ in trail]
    surgery = next((k for k, t in enumerate(texts) if re.search(r"surgery", t, re.IGNORECASE)), None)
    systemic = re.compile(r"ChT|ET\b|therapy|treatment|cycles|year|trastuzumab|olaparib|abemaciclib|"
                          r"pembrolizumab|capecitabine|T-DM1|bisphosphonate", re.IGNORECASE)
    found = []
    for k, t in enumerate(texts):
        # 맨 위 상자(그림 제목, 예: 'Overview of EBC treatment')는 치료 단계가 아니다
        if surgery is None or k in (0, surgery) or not systemic.search(t) or re.search(r"surgery", t, re.IGNORECASE):
            continue
        tag = "neoadjuvant" if k < surgery else "adjuvant"
        if tag not in found:
            found.append(tag)
    for t in texts[1:]:
        found += [x for x in _ebc_line(t) if x != "any" and x not in found]
    order = ["neoadjuvant", "adjuvant"]
    return [x for x in order if x in found] or ["any"]


def _path_subtype(nodes, trail, default):
    """HER2 양성 그림의 'ER+' / 'ER-' 갈래는 HR 상태를 정한다. 아형이 any인 개요 그림은 갈래 상자의 아형을 쓴다."""
    if default == ["any"]:
        for i, _, _ in trail[1:]:
            t = re.sub(r"\^\w+", "", nodes[i]["text"]).strip()
            if t == "All HR+":
                return ["HR+/HER2-", "HR+/HER2+"]
            if t == "HR+/HER2-":
                return ["HR+/HER2-"]
            if t == "HER2+":
                return HER2_POS
            if t == "TNBC":
                return ["TNBC"]
        return default
    if default != HER2_POS:
        return default
    for i, _, _ in trail[1:]:
        t = nodes[i]["text"]
        if re.match(r"^(ER|HR)\s?\+", t):
            return ["HR+/HER2+"]
        if re.match(r"^(ER|HR)\s?[-–]", t):
            return ["HR-/HER2+"]
    return default


def figure_chunks(stem: str, pdf_path: Path) -> tuple[list[dict], list[str]]:
    import pymupdf
    _install_symbol_fix(pymupdf)
    doc_info = DOCS[stem]
    specs = FIGURES[stem]
    pdf = pymupdf.open(str(pdf_path))
    texts = load_figure_text()
    first_printed, _ = printed_page_range(pdf.metadata)
    chunks, report = [], []
    for page_index, page in enumerate(pdf):
        for number, title, caption_rect in find_figures(page):
            if number not in specs:
                continue
            slug, subtype, line = specs[number]
            region = figure_region(page, caption_rect)
            if region is None:
                report.append(f"[경고] {stem} Figure {number}: 그림 영역을 못 찾음")
                continue
            nodes, edges, leftover, warnings = build_graph(page, region, texts.get((pdf_path.name, number), ()))
            notes = footnotes(page, caption_rect, region)
            trails = paths(nodes, edges)
            page_no = first_printed + page_index if first_printed else page_index + 1
            heading = f"Figure {number}. {title}"
            children, used = [], set()
            for trail in trails:
                text = path_text(nodes, trail)
                marks = sorted({m for part in re.findall(r"\^([a-z,]+)", text) for m in part.split(",")})
                cited = [f"{m}: {notes[m]}" for m in marks if m in notes and not GENERIC_FOOTNOTE.search(notes[m])]
                full = f"{heading} (algorithm path): {text}"
                if cited:
                    full += " Footnotes: " + " ".join(cited)
                chunk_id = f"esmo-{doc_info['slug']}-{doc_info['version']}-fig{number}-{stable_key(text)}"
                n = 2
                while chunk_id in used:
                    chunk_id = f"esmo-{doc_info['slug']}-{doc_info['version']}-fig{number}-{stable_key(text)}-{n}"
                    n += 1
                used.add(chunk_id)
                chunk = make_chunk(
                    chunk_id=chunk_id, source=doc_info["source"], version=doc_info["version"],
                    section=heading, url=doc_info["url"], chunk_kind="algorithm", text=full,
                    setting=doc_info["setting"], subtype=_path_subtype(nodes, trail, subtype),
                    line=_path_line(nodes, trail, line), evidence=_evidence(nodes[trail[-1][0]]["text"]),
                    copyright_notice=COPYRIGHT)
                # 약·표지자는 경로 글로만 찾는다. 각주의 대안 약(예: 다른 탁산)과 설명 문구가 섞이면 엉뚱한 질의에 걸린다
                expanded = text
                for pattern, names in REGIMEN_ABBREVIATIONS.items():
                    expanded = re.sub(pattern, names, expanded)
                chunk["drugs"] = find_drugs(expanded)
                # 점선 상자 참고('gBRCA1/2 testing')는 검사를 권하는 말이지 변이 양성이 아니다
                chunk["biomarker_tags"] = find_biomarker_tags(re.sub(r" \(optional: [^)]*\)", "", text))
                chunk["page_start"] = chunk["page_end"] = page_no
                children.append(chunk)
            if not children:
                report.append(f"[경고] {stem} Figure {number}: 경로 없음")
                continue
            parent = attach_parent(children, chunk_id=f"esmo-{doc_info['slug']}-{doc_info['version']}-fig{number}",
                                   section=heading, heading=heading)
            parent["page_start"] = parent["page_end"] = page_no
            chunks.append(parent)
            chunks.extend(children)
            noted = {note for n in nodes for note in n.get("notes", [])}
            lonely = [n["text"][:40] for i, n in enumerate(nodes)
                      if not any(i in (e[0], e[1]) for e in edges) and n["text"] not in noted]
            report.append(f"{stem} Figure {number} (p{page_no}): 상자 {len(nodes)}, 연결 {len(edges)}, 경로 {len(children)}"
                          + (f", 연결 없는 상자 {lonely}" if lonely else "")
                          + (f", 이름표 못 붙인 글자 {leftover}" if leftover else "")
                          + "".join(f"\n  [경고] {w}" for w in warnings))
    return chunks, report


def write_review_sheet(chunks: list[dict], path: Path = REVIEW_CSV) -> None:
    """검수표: 경로 청크마다 한 줄. 이미 적은 검수 결과(status, reviewer, reviewed_on, note)는 chunk_id로 이어받는다.
    지침 문장은 넣지 않는다 (청크 JSON에 있다)."""
    old = {}
    if path.exists():
        with open(path, encoding="utf-8-sig", newline="") as f:
            old = {r["chunk_id"]: r for r in csv.DictReader(f)}
    fields = ["chunk_id", "figure", "page", "status", "reviewer", "reviewed_on", "note"]
    rows = []
    for c in chunks:
        if not c.get("parent_id"):
            continue
        prev = old.get(c["chunk_id"], {})
        rows.append({"chunk_id": c["chunk_id"], "figure": f"{c['source']} {c['section'].split('.')[0]}",
                     "page": c["page_start"], "status": prev.get("status") or "draft",
                     "reviewer": prev.get("reviewer", ""), "reviewed_on": prev.get("reviewed_on", ""),
                     "note": prev.get("note", "")})
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def process_all(pdf_dir: Path = GUIDELINES_DIR, show=None) -> list[dict]:
    all_chunks, missing = [], []
    for stem in FIGURES:
        pdf_path = pdf_dir / f"{stem}.pdf"
        if not pdf_path.exists():
            missing.append(pdf_path.name)
            continue
        chunks, report = figure_chunks(stem, pdf_path)
        print("\n".join(report))
        all_chunks.extend(chunks)
    if missing:
        raise FileNotFoundError(f"{pdf_dir}에 없는 PDF: {missing}")
    if show:
        slug, number = show
        for c in all_chunks:
            if c["chunk_id"].startswith(f"esmo-{slug}-") and f"-fig{number}-" in c["chunk_id"]:
                print(f"\n{c['chunk_id']} {c['subtype']} {c['line']}\n  {c['text']}")
        return all_chunks
    OUTPUT_JSON.write_text(json.dumps(all_chunks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_review_sheet(all_chunks)
    n_paths = sum(1 for c in all_chunks if c.get("parent_id"))
    print(f"알고리즘 청크 {len(all_chunks)}개 (경로 {n_paths}개 + 그림 부모) 저장 -> {OUTPUT_JSON}")
    print(f"검수표 -> {REVIEW_CSV}")
    return all_chunks


def main():
    ap = argparse.ArgumentParser(description="ESMO 알고리즘 그림 → 경로 청크")
    ap.add_argument("--show", nargs=2, metavar=("DOC", "FIGURE"),
                    help="저장하지 않고 그림 하나의 경로만 출력. 예: --show mbc 2")
    ap.add_argument("--pdf-dir", type=Path, default=GUIDELINES_DIR, help="PDF 폴더 (기본 data/guidelines)")
    args = ap.parse_args()
    process_all(args.pdf_dir, show=(args.show[0], int(args.show[1])) if args.show else None)


if __name__ == "__main__":
    main()
