# src/rag/bench_reranker.py
# 재정렬 모델이 왜 느린지 나눠서 잰다. 실행: team_project 폴더에서 python -m src.rag.bench_reranker [--model 이름]
#   1) 모델 불러오기  2) 후보 수(5·10·20개)에 따른 시간  3) CPU 스레드 수  4) 최대 입력 길이(max_length)
# 실제 ESMO 권고 청크와 평가 문제집 질의를 쓴다. 색인(Qdrant)은 쓰지 않는다.
import argparse
import sys
import time

from .chunk_store import load_guideline_chunks, select_index_chunks
from .client import RERANKER_NAME
from .evaluate import load_cases

REPEAT = 3  # 같은 조건을 몇 번 재서 평균 낼지


def _time(fn) -> float:
    fn()  # 첫 실행은 준비 과정이 섞이므로 빼고 잰다
    start = time.perf_counter()
    for _ in range(REPEAT):
        fn()
    return (time.perf_counter() - start) / REPEAT


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="재정렬 모델 속도를 원인별로 잰다")
    parser.add_argument("--model", default=RERANKER_NAME, help="비교할 재정렬 모델 이름")
    args = parser.parse_args(argv)

    import torch
    from sentence_transformers import CrossEncoder

    texts = [c["text"] for c in select_index_chunks(load_guideline_chunks())]
    query = load_cases()[0]["query"]
    print(f"모델: {args.model}")
    print(f"CPU 스레드 기본값: {torch.get_num_threads()} | GPU 사용 가능: {torch.cuda.is_available()}")

    start = time.perf_counter()
    model = CrossEncoder(args.model)
    print(f"모델 불러오기: {time.perf_counter() - start:.1f}초 | 설정된 최대 입력 길이: {model.max_seq_length}")

    def run(n):
        return lambda: model.predict([(query, t) for t in texts[:n]], show_progress_bar=False)

    print("\n[후보 수별] (스레드 기본값)")
    for n in (5, 10, 20):
        print(f"  {n:>2}개: {_time(run(n)):.2f}초")

    print("\n[CPU 스레드 수별] (후보 20개)")
    default_threads = torch.get_num_threads()
    for threads in sorted({1, 2, 4, max(1, default_threads // 2), default_threads}):
        torch.set_num_threads(threads)
        print(f"  {threads:>2}개: {_time(run(20)):.2f}초")
    torch.set_num_threads(default_threads)

    print("\n[최대 입력 길이별] (후보 20개)")
    for max_length in (512, 256):
        model.max_seq_length = max_length
        print(f"  {max_length}: {_time(run(20)):.2f}초")
    print("\n권고 청크 길이(글자): 최대", max(len(t) for t in texts), "| 평균", sum(len(t) for t in texts) // len(texts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
