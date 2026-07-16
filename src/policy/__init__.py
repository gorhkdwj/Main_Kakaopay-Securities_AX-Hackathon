"""판단 여권(Decision Passport) · 정책 가드 패키지 (S3).

AI 출력(계약 §6 JSON)이 화면에 렌더링되기 전에 금지 표현·출처 없는 사실·
수량 불일치를 차단하는 결정론 검사 계층입니다. LLM·네트워크 호출이 없습니다.

공개 인터페이스:
    from src.policy.guard import check_response
    from src.policy.lexicon import find_violations, LEXICON_VERSION
"""

from src.policy.guard import check_response
from src.policy.lexicon import LEXICON_VERSION, find_violations

__all__ = ["check_response", "find_violations", "LEXICON_VERSION"]
