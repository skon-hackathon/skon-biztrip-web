"""자동매칭 규칙 (spec 5.6). DB 접근이 없는 순수 함수다.

입력은 출장 기간과 거래 뷰 리스트뿐이다. "누구의 카드인가"와 "다른 리포트가 이미
가져갔는가"는 조회가 필요하므로 `services/expenses.py`가 판단해서 걸러 넘긴다.
그렇게 나눠야 규칙 전체를 DB 없이 단위테스트할 수 있다.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

#: 업무 날짜는 KST 기준이다. UTC로 비교하면 밤 결제가 하루 밀린다.
KST = ZoneInfo("Asia/Seoul")

#: 카드 가맹점 업종(MERCHANT_CATEGORY) → 정산 비목(EXPENSE_CATEGORY) 추천.
#: 추천일 뿐이며 사용자가 바꿀 수 있다. 값 자체는 두 공통코드 그룹에 실재해야 한다.
MERCHANT_TO_EXPENSE: dict[str, str] = {
    "MEAL": "MEAL",
    "TRANSPORT": "TRANSPORT",
    "LODGING": "LODGING",
    "ENTERTAIN": "ENTERTAIN",
    "ETC": "ETC",
}
DEFAULT_EXPENSE_CATEGORY = "ETC"

#: 출장 전후로 며칠까지 후보로 볼 것인가 (spec 5.6: start - 1일 ~ end + 1일).
WINDOW_DAYS = 1


@dataclass(frozen=True)
class TransactionView:
    """매칭 판정에 필요한 거래 필드만 담는다. ORM 객체를 그대로 받지 않는 이유는
    이 모듈이 세션·lazy load에 얽히지 않게 하기 위해서다."""

    id: int
    approved_at: datetime
    merchant_category_code: str
    amount_krw: Decimal
    is_cancelled: bool


@dataclass(frozen=True)
class MatchCandidate:
    transaction_id: int
    reasons: tuple[str, ...]
    suggested_category_code: str


def local_date(moment: datetime) -> date:
    """timestamptz를 KST 날짜로 접는다.

    naive datetime을 조용히 UTC로 가정하지 않는다 — 그렇게 하면 DB 설정이 바뀌었을 때
    매칭 창이 9시간 밀리고 아무도 눈치채지 못한다.
    """
    if moment.tzinfo is None:
        raise ValueError("approved_at은 타임존을 가진 datetime이어야 합니다")
    return moment.astimezone(KST).date()


def suggest_expense_category(merchant_category_code: str) -> str:
    return MERCHANT_TO_EXPENSE.get(merchant_category_code, DEFAULT_EXPENSE_CATEGORY)


def _reasons(day: date, *, start_date: date, end_date: date, category: str) -> tuple[str, ...]:
    """매칭 사유는 UI와 API가 **같은 문자열**을 쓴다 (spec 5.6). 화면에서 따로 만들면
    Agent가 받는 설명과 사람이 보는 설명이 갈라진다."""
    if day < start_date:
        return ("출발 전일 교통비",) if category == "TRANSPORT" else ("출발 전일 승인",)
    if day > end_date:
        return ("종료 익일 교통비",) if category == "TRANSPORT" else ("종료 익일 승인",)
    if category == "LODGING":
        return ("출장기간 내 승인", "출장기간 내 숙박")
    return ("출장기간 내 승인",)


def find_candidates(
    *,
    start_date: date,
    end_date: date,
    transactions: list[TransactionView],
    excluded_transaction_ids: frozenset[int] = frozenset(),
) -> list[MatchCandidate]:
    """후보를 승인 시각 오름차순(같으면 id 오름차순)으로 돌려준다."""
    window_start = start_date - timedelta(days=WINDOW_DAYS)
    window_end = end_date + timedelta(days=WINDOW_DAYS)

    picked: list[tuple[datetime, int, MatchCandidate]] = []
    for transaction in transactions:
        if transaction.is_cancelled or transaction.id in excluded_transaction_ids:
            continue
        day = local_date(transaction.approved_at)
        if day < window_start or day > window_end:
            continue
        picked.append(
            (
                transaction.approved_at,
                transaction.id,
                MatchCandidate(
                    transaction_id=transaction.id,
                    reasons=_reasons(
                        day,
                        start_date=start_date,
                        end_date=end_date,
                        category=transaction.merchant_category_code,
                    ),
                    suggested_category_code=suggest_expense_category(
                        transaction.merchant_category_code
                    ),
                ),
            )
        )
    picked.sort(key=lambda row: (row[0], row[1]))
    return [candidate for _, _, candidate in picked]
