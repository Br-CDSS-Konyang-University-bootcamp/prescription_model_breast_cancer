"""급여 기준 자동 업데이트 전체 흐름 (§8 처리 흐름 1–9).

  1. 수집        게시판 확인 -> 새 파일만 내려받기 -> 파일 검사 (온라인)
                 또는 data/reimbursement/raw/의 가장 최근 파일 사용 (--offline)
  2. 책자 검증    공고책자 읽기, 목차(Ⅰ~Ⅳ, 별첨) 순서대로 책자 전체를 섹션으로 나눠 저장 (sections/),
                 validate_booklet (목차 분할·개정 이력·변경 표시·공고전문 대조), 깨진 글자
  3. 유방암 추출  나눈 섹션 중 일반원칙([별표] 앞) + 유방암 섹션 + '40. 기타 항암제 병용요법'의 유방암 행.
                 표의 연번 연속성, 책자의 다른 곳에 남은 '유방' 언급
  4. 허가초과     유방암 인정 요법·검토중 요법, validate_offlabel
  5. 청크 검사    스키마, 빠진 낱말, 원문에 없는 낱말, 깨진 글자, 약제명, 이전 실행 대비 행 수
  6. 투여 조건    Claude API로 조건 JSON (conditions.py). 근거 인용이 원문에 없으면 버린다.
                 API 키가 없거나 일부가 실패해도 멈추지 않는다 (조건 없이 반영, 경고로 남김)
  7. 반영        오류가 없을 때만: 레지스트리 반영(신설·변경·삭제), 청크 파일 저장, 현재 파일 교체
                 오류가 있으면 아무것도 바꾸지 않고 마지막 정상 청크 파일을 계속 쓴다 (처리 흐름 9)

결과물 (모두 git에 올리지 않는다. 공고 원문·가공물 외부 공개 금지):
  data/reimbursement/chunks/reimbursement_chunks_current.jsonl   마지막 정상 청크 (C의 색인에 넣을 파일)
  data/reimbursement/chunks/reimbursement_chunks_<책자>_<허가초과>.jsonl
  data/reimbursement/index_status.json                           화면 하단 요약 + 예정·진행중 공고 (B에게)
  data/reimbursement/conditions_cache.jsonl                      Claude API 조건 결과 저장본
  data/reimbursement/reports/run_<시각>.json                     단계별 검사 결과
  data/reimbursement/reports/last_good.json                      마지막 정상 실행 (행 수 비교 기준)

사용 (team_project 폴더에서):
    python -m src.reimbursement.pipeline              # 게시판 확인부터
    python -m src.reimbursement.pipeline --offline    # 이미 받은 파일로만
    python -m src.reimbursement.pipeline --no-llm     # Claude API를 부르지 않고 저장된 조건만 쓴다
    python -m src.reimbursement.pipeline --cross-check  # pdfplumber로 한 번 더 읽어 비교 (첫 실행 1분 남짓)
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from . import qc
from .booklet import Booklet, load_booklet, section_records, sha256
from .chunks import (
    COMBO_TITLE, GENERAL_TITLE, SUPP_TITLE, BookletChunks, booklet_chunks, check_chunks, general_source,
    offlabel_chunks, write_jsonl,
)
from .dates import KST, date_from_filename, today_kst
from .notice import load_notice
from .offlabel import OffLabel, load_offlabel, validate_offlabel
from .registry import Registry
from .status import IN_REVIEW, NOTICED, SCHEDULED, summarize
from .validate import Report, validate_booklet

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "reimbursement"
CURRENT = "reimbursement_chunks_current.jsonl"

# 청크에 붙이는 머리표 낱말 (원문에 없어도 된다)
LABEL_WORDS = {"연번", "항암요법", "투여대상", "위", "연번과", "같음", "열", "항암제", "병용요법",
               "허가사항", "급여", "요법", "급여기준", "비고", "유방암", "9", "40", "기타",
               "허가초과", "인정", "검토중인", "판정에", "쓰지", "않음", "요법코드", "투여단계",
               "투여요법", "항암화학요법"}


@dataclass
class Stage:
    name: str
    report: Report = field(default_factory=Report)
    skipped: bool = False

    def merge(self, other: Report, prefix: str = "") -> None:
        p = f"[{prefix}] " if prefix else ""
        self.report.errors += [p + m for m in other.errors]
        self.report.warnings += [p + m for m in other.warnings]
        self.report.info += [p + m for m in other.info]


@dataclass
class RunResult:
    started: str
    stages: list[Stage]
    counts: dict[str, int] = field(default_factory=dict)
    chunks_path: Path | None = None
    current_path: Path | None = None
    summary_line: str | None = None
    index_status: dict | None = None
    pending_notices: list[dict] = field(default_factory=list)
    diff: dict[str, dict[str, list[str]]] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return all(s.report.ok for s in self.stages)

    def to_dict(self) -> dict:
        return {
            "started": self.started, "ok": self.ok, "summary": self.summary_line,
            "index_status": self.index_status, "pending_notices": self.pending_notices,
            "counts": self.counts, "diff": self.diff,
            "chunks_path": str(self.chunks_path) if self.chunks_path else None,
            "stages": [{"name": s.name, "skipped": s.skipped, **s.report.to_dict()} for s in self.stages],
        }

    def render(self) -> str:
        out = []
        for s in self.stages:
            r = s.report
            state = "건너뜀" if s.skipped else ("통과" if r.ok else "실패")
            out.append(f"\n== {s.name}: {state} (오류 {len(r.errors)}, 경고 {len(r.warnings)})")
            out += [f"  [오류] {m}" for m in r.errors]
            out += [f"  [경고] {m}" for m in r.warnings]
            out += [f"  [정보] {m}" for m in r.info]
        out.append("")
        if self.ok and self.chunks_path:
            out.append(f"결과: 정상. 청크 {self.counts.get('chunks', 0)}개 -> {self.current_path}")
        else:
            out.append("결과: 실패. 아무것도 바꾸지 않았다. 마지막 정상 청크 파일을 계속 쓴다.")
        if self.summary_line:
            out.append(self.summary_line)
        return "\n".join(out)


# ---------- 1. 수집 ----------

def _latest_local(raw: Path, pattern: str) -> Path | None:
    """파일명 날짜가 가장 늦은 파일. 같은 날짜로 다시 올라온 파일이 있으면 나중에 받은 것."""
    files = []
    for p in raw.glob(pattern):
        try:
            files.append((date_from_filename(p.name), p.stat().st_mtime, p))
        except ValueError:
            continue
    return max(files)[2] if files else None


@dataclass
class Inputs:
    booklet: Path | None = None
    offlabel: Path | None = None
    plan: object | None = None        # fetch.Plan (온라인일 때)
    http: object | None = None


def stage_collect(reg: Registry, raw: Path, offline: bool, today: date, st: Stage,
                  with_offlabel: bool = False) -> Inputs:
    """with_offlabel이 아니면 허가초과 xlsx는 받지도 검사하지도 않는다 (설계 문서 범위 밖, 팀 결정 대기)."""
    inp = Inputs()
    sources = ("booklet", "offlabel") if with_offlabel else ("booklet",)
    if not offline:
        from .fetch import Http, make_plan, run_downloads
        try:
            http = Http()
            plan = make_plan(http, reg, today, sources)
            for m in plan.messages:
                (st.report.warn if m.startswith("[경고]") else st.report.info.append)(
                    m.removeprefix("[경고] "))
            for d in run_downloads(http, reg, plan, raw):
                st.merge(d.report, d.source)
                st.report.info.append(f"{d.source}: {'있던 파일 사용' if d.reused else '내려받음'} {d.path.name}")
            inp.plan, inp.http = plan, http
        except Exception as e:      # 사이트 장애·구조 변경: 이미 받은 파일로 계속한다
            st.report.warn(f"게시판 확인 실패 ({type(e).__name__}: {e}). 이미 받은 파일로 진행")
    for source, pattern in (("booklet", "공고책자_*.pdf"), ("offlabel", "*_[0-9][0-9][0-9][0-9][0-9][0-9].xlsx")):
        if source not in sources:
            continue
        p = _latest_local(raw, pattern)
        if p is None:
            (st.report.error if source == "booklet" else st.report.warn)(f"{source} 파일이 {raw}에 없음")
            continue
        rep = qc.check_file(p)
        st.merge(rep, source)
        reg.add_document(source, file_hash=sha256(p), file_name=p.name,
                         effective_date=date_from_filename(p.name))
        setattr(inp, source, p)
    return inp


# ---------- 2. 책자 ----------

def _notice_for(b: Booklet, raw: Path, inp: Inputs, reg: Registry, st: Stage):
    """책자와 같은 공고번호의 공고전문. 없으면 (온라인일 때) 받아 온다."""
    local = raw / f"공고전문_{b.file_date:%Y%m%d}.pdf"
    if not local.exists() and inp.plan is not None:
        from .fetch import fetch_notice_pdf
        row = next((n for n in inp.plan.all_notices if n.doc_no == b.doc_no), None)
        if row is not None:
            d = fetch_notice_pdf(inp.http, reg, row, raw)
            if d is not None:
                st.merge(d.report, "notice")
                local = d.path
    if not local.exists():
        st.report.warn(f"제{b.doc_no}호 공고전문 PDF가 없어 공고 대조(신설·변경·삭제 반영 확인)를 건너뜀")
        return None
    n = load_notice(local)
    if n.doc_no != b.doc_no:
        st.report.warn(f"공고전문 번호 제{n.doc_no}호가 책자 제{b.doc_no}호와 다름: 대조 생략")
        return None
    return n


def write_sections(b: Booklet, sections_dir: Path) -> Path:
    """1단계 결과: 책자 전체를 목차 단위로 나눈 파일 (섹션 하나 = 한 줄). 공고 원문이므로 git 제외."""
    return write_jsonl(section_records(b), sections_dir / f"booklet_sections_{b.file_date:%Y%m%d}.jsonl")


def stage_booklet(reg: Registry, inp: Inputs, raw: Path, cross_check: bool, st: Stage,
                  sections_dir: Path | None = None):
    cache = DATA / "cache"
    b = load_booklet(inp.booklet, cache)
    if sections_dir is not None:
        p = write_sections(b, sections_dir)
        st.report.info.append(f"목차 단위 분할 저장: {p.name} (섹션 {len(b.sections)}개)")
    other = load_booklet(inp.booklet, cache, engine="pdfplumber") if cross_check else None
    notice = _notice_for(b, raw, inp, reg, st)
    prev = reg.last_good_booklet(exclude_hash=b.file_hash)
    rep = validate_booklet(
        b, other=other, notice=notice,
        previous_doc_no=prev["doc_no"] if prev else None,
        previous_file_date=date.fromisoformat(prev["effective_date"]) if prev else None,
    )
    st.merge(rep)
    doc_id = reg.add_document("booklet", file_hash=b.file_hash, file_name=b.path.name,
                              doc_no=b.doc_no, effective_date=b.file_date)
    reg.update_document(doc_id, doc_no=b.doc_no)     # 수집 단계에서는 공고번호를 몰랐다
    reg.save_validation(doc_id, rep.to_dict())
    texts = {k: b.section_text(k) for k in ("cancer:유방암", "combination") if k in b.sections}
    st.merge(qc.check_garbled(texts), "원문")
    st.report.info.append(f"{b.path.name}: 제{b.doc_no}호, 파일명 날짜 {b.file_date}, {len(b.pages)}쪽")
    # §8 가정 검증: 책자 파일명 날짜 = 마지막 반영 공고의 시행일. 실행마다 보고서에 남겨 몇 달간 대조한다
    last = b.last_notice
    if last.effective_date == b.file_date:
        st.report.info.append(f"가정 확인: 책자 날짜 {b.file_date} = 마지막 공고 제{last.doc_no}호 시행일 (일치)")
    else:
        st.report.warn(f"가정 불일치: 책자 날짜 {b.file_date}, 마지막 공고 제{last.doc_no}호 시행일 "
                       f"{last.effective_date}")
    return b, doc_id


# ---------- 3. 유방암 추출 ----------

def _strip_table_headers(text: str) -> str:
    text = re.sub(r"(?m)^\s*연번\s*\n\s*항암요법\s*\n\s*투여대상\s*$", "", text)
    return re.sub(r"(?m)^\s*연번\s*\n\s*주요\s*\n\s*암종\s*\n\s*항암제 병용요법\s*\n\s*허가사항\s*\n"
                  r"\s*급여 요법\s*\n\s*급여기준\s*\n\s*비고\s*$", "", text)


def stage_extract(b: Booklet, st: Stage) -> BookletChunks:
    bc = booklet_chunks(b)
    for w in bc.warnings:
        st.report.error(f"표 읽기: {w}")
    tables = {f"9. 유방암 > {s.path}": [r.no for r in s.rows] for s in bc.table.subsections}
    st.merge(qc.check_row_numbers(tables))
    if bc.combo and bc.combo.breast:
        st.report.info.append(f"{COMBO_TITLE}: 유방암 행 연번 {[r.no for r in bc.combo.breast]}")
    # 병용요법 표의 '유방' 언급이 모두 유방암 행(암종 칸 포함)에 들어갔는지
    sections = {k: b.section_text(k) for k in b.sections if k != "cancer:유방암"}
    covered = {"combination": "\n".join(("유방암\n" if r.starts_group else "") + r.text
                                        for r in bc.combo.breast) if bc.combo else ""}
    covered.update(bc.supp_sources)         # Ⅳ 기타 약제: 유방암 줄을 모두 넣었는지
    st.merge(qc.check_breast_scope(sections, covered))
    n_rows = sum(len(s.rows) for s in bc.table.subsections)
    st.report.info.append(f"유방암 섹션: 소단원 {len(bc.table.subsections)}개, 표 행 {n_rows}개")
    supp = [c for c in bc.chunks if "-supp-" in c["chunk_id"] and c["chunk_kind"] != "section"]
    st.report.info.append(f"{SUPP_TITLE}: 약제 {len(bc.supp_sources)}개, 조건 묶음 {len(supp)}개")
    return bc


# ---------- 4. 허가초과 ----------

def stage_offlabel(inp: Inputs, st: Stage, enabled: bool = True) -> OffLabel | None:
    if not enabled:
        st.skipped = True
        st.report.info.append("허가초과 목록: 설계 문서 범위 밖, 팀 결정 대기 (받지도 청크로 만들지도 않음. --with-offlabel로 켬)")
        return None
    if inp.offlabel is None:
        st.skipped = True
        return None
    o = load_offlabel(inp.offlabel)
    st.merge(validate_offlabel(o))
    return o


# ---------- 5. 청크 검사 ----------

def stage_chunks(b: Booklet, bc: BookletChunks, o: OffLabel | None, before: dict | None,
                 st: Stage) -> tuple[list[dict], dict[str, int]]:
    ol_chunks = offlabel_chunks(o) if o else []
    chunks = bc.chunks + ol_chunks
    for e in check_chunks(chunks):
        st.report.error(f"스키마: {e}")

    # 책자: 원문 = 유방암 섹션 + 병용요법 안내·유방암 행
    combo_src = ""
    if bc.combo and bc.combo.breast:
        combo_src = "\n".join([COMBO_TITLE, *bc.combo.intro, *(f"{r.no}\n{r.text}" for r in bc.combo.breast)])
    src_b = _strip_table_headers(b.section_text("유방암")) + "\n" + combo_src
    general = [c for c in bc.chunks if "-general-" in c["chunk_id"]]
    supp = [c for c in bc.chunks if c["chunk_id"].endswith("-supp") or "-supp-" in c["chunk_id"]]
    breast = [c for c in bc.chunks if c not in general and c not in supp]
    out_b = "\n".join(c["text"] for c in breast)
    # 부모(소단원) 청크가 행 전체를 다시 담고 있으므로, 행 청크 쪽과 부모 청크 쪽을 따로 검사한다.
    # 행 청크 쪽 = 투여 원칙 + 행 청크 + 소단원 제목·주석 + 병용요법 안내
    leaf = [c["text"] for c in breast if c["chunk_kind"] != "section" or c["chunk_id"].endswith("-bc-principle")]
    leaf += [f"[9. 유방암 > {s.path}]\n" + "\n".join(s.notes) for s in bc.table.subsections]
    if bc.combo and bc.combo.breast:
        leaf += [COMBO_TITLE, *bc.combo.intro]
    parents = "\n".join(c["text"] for c in breast if c["chunk_kind"] == "section")
    st.merge(qc.check_coverage(src_b, "\n".join(leaf), "책자 유방암 (행 청크)"))
    st.merge(qc.check_coverage(src_b, parents, "책자 유방암 (소단원 청크)"))
    st.merge(qc.check_foreign(src_b, out_b, "책자 유방암", LABEL_WORDS))

    # 일반원칙 ([별표] 앞까지): 모든 암종 공통 규칙
    src_g = general_source(b)
    if not general:
        st.report.error("일반원칙 청크를 만들지 못함 (제목 인식 실패)")
    else:
        out_g = "\n".join(c["text"] for c in general)
        st.merge(qc.check_coverage(src_g, out_g, "책자 일반원칙"))
        st.merge(qc.check_foreign(src_g, out_g, "책자 일반원칙", LABEL_WORDS | set(GENERAL_TITLE.split())))

    # Ⅳ 기타 약제: 청크 글이 그 약제 섹션 원문에서 왔는지 (다른 암종 줄은 일부러 뺐으므로 빠진 낱말은 보지 않는다.
    # 유방암 줄을 모두 넣었는지는 3단계 '유방' 언급 검사가 본다)
    if supp:
        src_s = "\n".join(b.section_text(k) for k in bc.supp_sources) + "\n" + b.section_text("part:기타 약제") \
            if "part:기타 약제" in b.sections else "\n".join(b.section_text(k) for k in bc.supp_sources)
        st.merge(qc.check_foreign(src_s, "\n".join(c["text"] for c in supp), SUPP_TITLE,
                                  LABEL_WORDS | {"Ⅳ", "약제", "가", "나", "나-1", "나-2", "1", "2", "3"}))

    if o is not None:
        cells = [" ".join([r.code, r.regimen, r.target, r.line, r.setting, r.copay]) for r in o.approved]
        cells += [f"{v.no} {v.text}" for v in o.reviewing]
        src_o = "\n".join(cells)
        out_o = "\n".join(c["text"] for c in ol_chunks)
        st.merge(qc.check_coverage(src_o, out_o, "허가초과"))
        st.merge(qc.check_foreign(src_o, out_o, "허가초과", LABEL_WORDS))

    # 설계 §2.4: 공고 이력을 못 읽은 행은 목록으로 남긴다. 책자에 표시가 없는 행(개정된 적 없는 요법)은
    # notice_no·effective_from에 책자 공고번호·날짜를 넣었다
    untagged = [c["chunk_id"].rsplit("-", 2)[-2] + "-" + c["chunk_id"].rsplit("-", 1)[-1]
                for c in bc.chunks if c["chunk_kind"] != "section" and not c["reimbursement"].get("history")]
    if untagged:
        st.report.info.append(f"공고 표시가 없는 행 {len(untagged)}개 (책자 공고번호·날짜를 씀): {', '.join(untagged)}")

    st.merge(qc.check_garbled({c["chunk_id"]: c["text"] for c in chunks}))
    st.merge(qc.check_drugs(chunks, bc.drug_scans, src_b))

    counts = {f"9. 유방암 > {s.path}": len(s.rows) for s in bc.table.subsections}
    counts[f"{GENERAL_TITLE} (청크)"] = len(general)
    counts[COMBO_TITLE] = len(bc.combo.breast) if bc.combo else 0
    counts[f"{SUPP_TITLE} (조건 묶음)"] = sum(c["chunk_kind"] != "section" for c in supp)
    if o is not None:
        counts["허가초과 인정 (유방암)"] = len(o.approved)
    counts["chunks"] = len(chunks)
    st.merge(qc.check_counts(counts, before, out_of_scope=set() if o is not None else {"허가초과 인정 (유방암)"}))
    return chunks, counts


# ---------- 6. 투여 조건 ----------

def stage_conditions(chunks: list[dict], bc: BookletChunks, cache_path: Path, use_api: bool,
                     st: Stage, structurer=None, review_path: Path | None = None) -> None:
    """contexts: 행 청크마다 근거로 함께 넘길 소단원 제목·머리 규칙·주석 (chunks.booklet_chunks가 만든다)."""
    from .conditions import Cache, attach_conditions, export_review, is_empty

    rep = attach_conditions(chunks, bc.contexts, structurer=structurer, cache=Cache(cache_path),
                            use_api=use_api)
    total = sum(c["chunk_kind"] in ("reimbursement_condition", "offlabel_regimen") for c in chunks)
    done = sum(not is_empty(c["reimbursement"].get("conditions") or {}) for c in chunks)
    st.report.info.append(f"대상 {total}개 중 조건 정리 {done}개 (저장본 {rep.from_cache}, 새 요청 {rep.requested})")
    if rep.requested:
        st.report.info.append(f"사용량: 입력 {rep.input_tokens:,} 토큰, 출력 {rep.output_tokens:,} 토큰")
    if rep.skipped_no_api:
        reason = rep.unavailable_reason or "--no-llm"
        st.report.warn(f"조건을 정리하지 못한 청크 {len(rep.skipped_no_api)}개 ({reason}). 조건 없이 반영한다")
    for cid, probs in rep.rejected.items():
        st.report.warn(f"{cid}: 조건 버림 - {'; '.join(probs[:3])}")
    for cid, err in rep.failed.items():
        st.report.warn(f"{cid}: 요청 실패 - {err}")
    if rep.empty:
        st.report.info.append(f"조건이 없는 청크 {len(rep.empty)}개: {', '.join(rep.empty[:10])}")
    for e in check_chunks(chunks):      # 조건을 붙인 뒤에도 공용 형식에 맞는지
        st.report.error(f"스키마: {e}")
    # 사람 전수 검수표 (설계 §3.5). 조건이 하나라도 있을 때만 만든다
    if review_path is not None and (p := export_review(chunks, review_path)):
        st.report.info.append(f"검수표: {p.name} (엑셀로 열어 검수(O/X) 칸을 채운다)")


# ---------- 7. 반영 ----------

def _pending_notices(inp: Inputs, today: date) -> list[dict]:
    """recommendation.options[].pending_notices 형식의 예정·진행중 목록. B가 회색 태그로 쓴다."""
    from .fetch import BASE, BOARD_NOTICE, BOARD_PREVIEW

    if inp.plan is None:
        return []
    out = []
    for n in inp.plan.all_notices:
        if n.effective_date > today:
            out.append({"status": "scheduled", "title": f"공고 제{n.doc_no}호 {n.title}",
                        "date": n.effective_date.isoformat(),
                        "url": f"{BASE}{BOARD_NOTICE}&brdScnBltNo=4&brdBltNo={n.brd_blt_no}"})
    for p, s in inp.plan.previews:
        if s in (IN_REVIEW, SCHEDULED):
            out.append({"status": "in_progress" if s == IN_REVIEW else "scheduled",
                        "title": f"공고예고 {p.title}", "date": p.period_end.isoformat(),
                        "url": f"{BASE}{BOARD_PREVIEW}"})
    return out


def stage_apply(reg: Registry, b: Booklet, booklet_doc: int, bc: BookletChunks, o: OffLabel | None,
                chunks: list[dict], out_dir: Path, st: Stage, res: RunResult) -> None:
    d = reg.apply_booklet(booklet_doc, b.file_date, bc.items)
    res.diff["booklet"] = {"added": d.added, "changed": d.changed, "removed": d.removed}
    if o is not None:
        prev = reg.last_good("offlabel", exclude_hash=o.file_hash)
        doc = reg.add_document("offlabel", file_hash=o.file_hash, file_name=o.path.name,
                               effective_date=o.file_date)
        od = reg.apply_booklet(doc, o.file_date, o.items())
        rep = validate_offlabel(o, diff=od,
                                previous_file_date=date.fromisoformat(prev["effective_date"]) if prev else None)
        reg.save_validation(doc, rep.to_dict())
        st.report.warnings += [f"[허가초과 변경대비표] {w}" for w in rep.warnings]
        res.diff["offlabel"] = {"added": od.added, "changed": od.changed, "removed": od.removed}
    for k, v in res.diff.items():
        st.report.info.append(f"{k}: 신설 {len(v['added'])}, 변경 {len(v['changed'])}, 삭제 {len(v['removed'])}")
    tag = f"{b.file_date:%Y%m%d}" + (f"_{o.file_date:%y%m%d}" if o else "")
    res.chunks_path = write_jsonl(chunks, out_dir / f"reimbursement_chunks_{tag}.jsonl")
    res.current_path = out_dir / CURRENT
    tmp = res.current_path.with_suffix(".part")
    shutil.copyfile(res.chunks_path, tmp)
    tmp.replace(res.current_path)
    st.report.info.append(f"저장: {res.chunks_path.name} -> {CURRENT}")
    status_path = out_dir.parent / "index_status.json"
    status_path.write_text(json.dumps({"index_status": res.index_status, "summary": res.summary_line,
                                       "pending_notices": res.pending_notices},
                                      ensure_ascii=False, indent=1), encoding="utf-8")
    st.report.info.append(f"저장: {status_path.name} (화면 하단 요약, 예정·진행중 {len(res.pending_notices)}건)")


# ---------- 실행 ----------

def _summary(b: Booklet, inp: Inputs, today: date):
    notices, previews = [], []
    if inp.plan is not None:
        notices = [(n.doc_no, n.effective_date) for n in inp.plan.all_notices]
        previews = [(p.period_end, s == NOTICED) for p, s in inp.plan.previews]
    return summarize(b.file_date, b.doc_no, notices, previews, today)


def run(*, raw: Path = DATA / "raw", db: Path = DATA / "registry.db", out_dir: Path = DATA / "chunks",
        reports: Path = DATA / "reports", offline: bool = False, cross_check: bool = False,
        today: date | None = None, use_llm: bool = True, structurer=None,
        with_offlabel: bool = False) -> RunResult:
    """structurer: 테스트에서 Claude API 대신 넣는 가짜 (본문, 안내) -> (조건, 사용량).
    with_offlabel: 허가초과 목록 청크도 만든다 (B의 설계 문서는 이번 범위에서 제외, 기본 끔)."""
    today = today or today_kst()
    started = datetime.now(KST).isoformat(timespec="seconds")
    names = ["1. 수집", "2. 책자 읽기·목차 단위 분할·검증", "3. 유방암 부분 추출", "4. 허가초과 목록", "5. 청크 검사",
             "6. 투여 조건 정리", "7. 반영"]
    stages = [Stage(n) for n in names]
    res = RunResult(started, stages)
    db.parent.mkdir(parents=True, exist_ok=True)
    raw.mkdir(parents=True, exist_ok=True)
    last_good = reports / "last_good.json"
    before = json.loads(last_good.read_text(encoding="utf-8")).get("counts") if last_good.exists() else None

    reg = Registry(db)
    cur = 0
    booklet_doc = None
    try:
        inp = stage_collect(reg, raw, offline, today, stages[0], with_offlabel)
        if not stages[0].report.ok:
            for s in stages[1:]:
                s.skipped = True
            return res
        cur = 1
        b, booklet_doc = stage_booklet(reg, inp, raw, cross_check, stages[1], out_dir.parent / "sections")
        cur = 2
        bc = stage_extract(b, stages[2])
        cur = 3
        o = stage_offlabel(inp, stages[3], with_offlabel)
        cur = 4
        chunks, res.counts = stage_chunks(b, bc, o, before, stages[4])
        summary = _summary(b, inp, today)
        res.summary_line, res.index_status = summary.line(), summary.index_status()
        res.pending_notices = _pending_notices(inp, today)
        cur = 5
        if res.ok:
            stage_conditions(chunks, bc, out_dir.parent / "conditions_cache.jsonl", use_llm, stages[5],
                             structurer, reports / f"conditions_review_{b.file_date:%Y%m%d}.tsv")
        else:
            stages[5].skipped = True
        cur = 6
        if res.ok:
            stage_apply(reg, b, booklet_doc, bc, o, chunks, out_dir, stages[6], res)
        else:
            stages[6].skipped = True
    except Exception as e:      # 단계 하나가 깨져도 보고서는 남기고, 반영은 하지 않는다
        stages[cur].report.error(f"실행 중 예외: {type(e).__name__}: {e}")
        for s in stages[cur + 1:]:
            s.skipped = True
        res.chunks_path = None
    finally:
        if booklet_doc is not None and not res.ok:
            failed = [s.name for s in stages if not s.report.ok]
            reg.set_status(booklet_doc, "failed", f"검사 실패: {', '.join(failed)}")
        reg.close()
        reports.mkdir(parents=True, exist_ok=True)
        stamp = started.replace(":", "").replace("-", "")[:15]
        (reports / f"run_{stamp}.json").write_text(
            json.dumps(res.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
        if res.ok and res.chunks_path:
            shutil.copyfile(reports / f"run_{stamp}.json", last_good)
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="게시판에 접속하지 않고 이미 받은 파일만 쓴다")
    ap.add_argument("--cross-check", action="store_true", help="pdfplumber로 한 번 더 읽어 비교")
    ap.add_argument("--today", type=date.fromisoformat, help="판정 기준일 (기본: 오늘, KST)")
    ap.add_argument("--raw", type=Path, default=DATA / "raw")
    ap.add_argument("--db", type=Path, default=DATA / "registry.db")
    ap.add_argument("--out-dir", type=Path, default=DATA / "chunks")
    ap.add_argument("--reports", type=Path, default=DATA / "reports")
    ap.add_argument("--no-llm", action="store_true", help="Claude API를 부르지 않고 저장된 조건만 쓴다")
    ap.add_argument("--with-offlabel", action="store_true",
                    help="허가초과 목록 청크도 만든다 (설계 문서 범위 밖, 기본 끔)")
    args = ap.parse_args(argv)
    res = run(raw=args.raw, db=args.db, out_dir=args.out_dir, reports=args.reports,
              offline=args.offline, cross_check=args.cross_check, today=args.today,
              use_llm=not args.no_llm, with_offlabel=args.with_offlabel)
    print(res.render())
    return 0 if res.ok else 1


if __name__ == "__main__":
    sys.exit(main())
