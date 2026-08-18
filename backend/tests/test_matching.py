"""자동매칭 순수 함수 단위테스트. DB를 쓰지 않는다 (spec 8)."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.services.matching import (
    TransactionView,
    find_candidates,
    local_date,
    suggest_expense_category,
)

START = date(2026, 5, 10)
END = date(2026, 5, 12)


def txn(
    txn_id: int,
    *,
    when: datetime,
    category: str = "MEAL",
    amount: str = "30000",
    cancelled: bool = False,
) -> TransactionView:
    return TransactionView(
        id=txn_id,
        approved_at=when,
        merchant_category_code=category,
        amount_krw=Decimal(amount),
        is_cancelled=cancelled,
    )


def kst(day: date, hour: int) -> datetime:
    """KST 시각을 UTC datetime으로 변환한다 (KST = UTC+9)."""
    return datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc) - timedelta(hours=9)


def test_local_date_uses_kst_not_utc():
    """UTC 22시는 KST로 다음 날 07시다. 업무 날짜는 KST 기준이다."""
    assert local_date(datetime(2026, 5, 10, 22, tzinfo=timezone.utc)) == date(2026, 5, 11)


def test_local_date_rejects_naive_datetime():
    with pytest.raises(ValueError):
        local_date(datetime(2026, 5, 10, 22))


def test_transaction_inside_the_trip_is_a_candidate():
    [candidate] = find_candidates(
        start_date=START, end_date=END, transactions=[txn(1, when=kst(date(2026, 5, 11), 12))]
    )
    assert candidate.transaction_id == 1
    assert "출장기간 내 승인" in candidate.reasons


def test_transaction_on_the_day_before_departure_is_a_candidate():
    [candidate] = find_candidates(
        start_date=START,
        end_date=END,
        transactions=[txn(1, when=kst(date(2026, 5, 9), 20), category="TRANSPORT")],
    )
    assert candidate.reasons == ("출발 전일 교통비",)


def test_non_transport_on_the_day_before_departure_keeps_the_generic_reason():
    [candidate] = find_candidates(
        start_date=START,
        end_date=END,
        transactions=[txn(1, when=kst(date(2026, 5, 9), 20), category="MEAL")],
    )
    assert candidate.reasons == ("출발 전일 승인",)


def test_transaction_on_the_day_after_return_is_a_candidate():
    [candidate] = find_candidates(
        start_date=START,
        end_date=END,
        transactions=[txn(1, when=kst(date(2026, 5, 13), 8), category="TRANSPORT")],
    )
    assert candidate.reasons == ("종료 익일 교통비",)


def test_lodging_inside_the_trip_gets_an_extra_reason():
    [candidate] = find_candidates(
        start_date=START,
        end_date=END,
        transactions=[txn(1, when=kst(date(2026, 5, 11), 21), category="LODGING")],
    )
    assert candidate.reasons == ("출장기간 내 승인", "출장기간 내 숙박")


def test_transaction_two_days_before_is_not_a_candidate():
    assert (
        find_candidates(
            start_date=START, end_date=END, transactions=[txn(1, when=kst(date(2026, 5, 8), 12))]
        )
        == []
    )


def test_transaction_two_days_after_is_not_a_candidate():
    assert (
        find_candidates(
            start_date=START, end_date=END, transactions=[txn(1, when=kst(date(2026, 5, 14), 12))]
        )
        == []
    )


def test_cancelled_transaction_is_not_a_candidate():
    assert (
        find_candidates(
            start_date=START,
            end_date=END,
            transactions=[txn(1, when=kst(date(2026, 5, 11), 12), cancelled=True)],
        )
        == []
    )


def test_transaction_locked_by_another_submitted_report_is_not_a_candidate():
    assert (
        find_candidates(
            start_date=START,
            end_date=END,
            transactions=[txn(1, when=kst(date(2026, 5, 11), 12))],
            excluded_transaction_ids=frozenset({1}),
        )
        == []
    )


def test_candidates_keep_a_deterministic_order():
    """승인 시각 오름차순, 같으면 id 오름차순. 화면과 API가 같은 순서를 보여야 한다."""
    result = find_candidates(
        start_date=START,
        end_date=END,
        transactions=[
            txn(3, when=kst(date(2026, 5, 12), 9)),
            txn(1, when=kst(date(2026, 5, 10), 9)),
            txn(2, when=kst(date(2026, 5, 10), 9)),
        ],
    )
    assert [candidate.transaction_id for candidate in result] == [1, 2, 3]


def test_suggested_category_maps_merchant_category():
    [candidate] = find_candidates(
        start_date=START,
        end_date=END,
        transactions=[txn(1, when=kst(date(2026, 5, 11), 12), category="LODGING")],
    )
    assert candidate.suggested_category_code == "LODGING"


def test_unknown_merchant_category_falls_back_to_etc():
    assert suggest_expense_category("SPACE_TRAVEL") == "ETC"
