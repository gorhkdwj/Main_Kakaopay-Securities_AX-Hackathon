#!/usr/bin/env python3
"""제출용 프롬프트 로그 수집 — 복사만(무편집). 헌법 §13-4.

모든 로그 소스(worktree별 `logs/`)를 한 폴더로 **복사만** 한다.
- 편집·병합·정렬·넘버링 절대 금지(무편집 제출 규정 — 위반 시 실격).
- 파일명 = 세션 UUID라 충돌 없음. 복사 후 소스와 대상의 SHA-256을 대조해
  '무편집'을 기계적으로 증명한다.

사용:
  py -3 scripts/submission/collect_logs.py                 # 기본: repo logs → out/submission/logs
  py -3 scripts/submission/collect_logs.py --src <worktreeA> --src <worktreeB>
"""
import argparse
import hashlib
import os
import shutil
import sys


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def iter_logs(src_root: str):
    """src_root/logs/ 아래 모든 로그 파일을 (절대경로, logs 기준 상대경로)로 yield."""
    logs = os.path.join(src_root, "logs")
    if not os.path.isdir(logs):
        return
    for dp, _dn, files in os.walk(logs):
        for fn in files:
            if fn.startswith("."):   # .gitkeep 등 제외
                continue
            full = os.path.join(dp, fn)
            yield full, os.path.relpath(full, logs)


def main() -> int:
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap = argparse.ArgumentParser(description="프롬프트 로그 복사 수집(무편집).")
    ap.add_argument("--src", action="append", help="로그 소스 루트(반복 지정). 기본: repo 루트")
    ap.add_argument("--dest", help="수집 대상. 기본: <repo>/out/submission/logs")
    ap.add_argument("--no-clean", action="store_true", help="대상 폴더를 비우지 않음")
    args = ap.parse_args()

    srcs = args.src or [repo]
    dest = args.dest or os.path.join(repo, "out", "submission", "logs")

    # 안전장치: 자동 정리는 out/submission 하위 대상에만 적용(임의 경로 rmtree 방지)
    norm = os.path.normpath(dest).replace("\\", "/")
    if not args.no_clean and os.path.isdir(dest):
        if "/out/" in norm and "/submission/" in norm:
            shutil.rmtree(dest)
        else:
            print("경고: 대상이 out/submission 하위가 아니어서 자동 정리를 건너뜁니다: %s" % dest)

    seen: dict[str, str] = {}     # rel -> hash (중복 UUID 감지)
    per_tool: dict[str, int] = {}
    total = 0
    total_bytes = 0
    collisions: list[str] = []
    mismatches: list[str] = []

    for src in srcs:
        for full, rel in iter_logs(src):
            src_hash = sha256(full)
            if rel in seen:
                if seen[rel] != src_hash:
                    collisions.append(rel)   # 같은 UUID인데 내용이 다름 — 사람이 확인해야 함
                continue                     # 첫 복사본 유지(무편집)
            seen[rel] = src_hash
            d = os.path.join(dest, rel)
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copy2(full, d)            # 복사만(메타데이터·mtime 보존)
            if sha256(d) != src_hash:
                mismatches.append(rel)       # 복사본이 원본과 다름 — 있어선 안 됨
            total += 1
            total_bytes += os.path.getsize(full)
            tool = rel.replace("\\", "/").split("/")[0]
            per_tool[tool] = per_tool.get(tool, 0) + 1

    print("소스     : %s" % ", ".join(srcs))
    print("대상     : %s" % dest)
    print("수집 파일: %d개 (%s bytes)" % (total, format(total_bytes, ",")))
    for t, c in sorted(per_tool.items()):
        print("   - %s: %d개" % (t, c))
    print("해시 불일치(편집 의심): %d %s" % (len(mismatches), mismatches or ""))
    print("UUID 충돌(동일 이름·다른 내용): %d %s" % (len(collisions), collisions or ""))
    ok = not mismatches and not collisions
    print("결과: %s" % ("무편집 복사 검증 통과 [OK]" if ok else "확인 필요 [WARN]"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
