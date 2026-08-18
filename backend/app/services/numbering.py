"""업무 문서번호 채번.

`max() + 1` 방식이라 동시에 두 요청이 들어오면 같은 번호를 계산할 수 있다. 이 데모는
단일 백엔드 인스턴스로 배포하고, 마지막 방어선으로 `trip.trip_no`에 unique 제약이
걸려 있어 중복 저장은 일어나지 않는다 (그 경우 500이 난다). 멀티 레플리카로 가면
Postgres 시퀀스나 advisory lock이 필요하다.
"""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ExpenseReport, Trip


async def next_trip_no(session: AsyncSession, today: date) -> str:
    """`BT-YYYY-NNNN`. 연도별로 0001부터 다시 센다.

    today를 인자로 받는 이유는 테스트를 결정적으로 만들기 위해서다. 호출부가
    date.today()를 넘긴다.

    문자열 max()가 성립하는 것은 일련번호가 4자리로 0-패딩되어 있기 때문이다.
    """
    prefix = f"BT-{today.year}-"
    last = (
        await session.execute(
            select(func.max(Trip.trip_no)).where(Trip.trip_no.like(f"{prefix}%"))
        )
    ).scalar_one_or_none()
    sequence = int(last[len(prefix) :]) + 1 if last else 1
    return f"{prefix}{sequence:04d}"


async def next_report_no(session: AsyncSession, today: date) -> str:
    """`EX-YYYY-NNNN`. 연도별로 0001부터 다시 센다.

    `next_trip_no`와 같은 max() + 1 방식이고 같은 한계를 갖는다 — 단일 인스턴스 전제,
    마지막 방어선은 `expense_report.report_no`의 unique 제약이다.
    """
    prefix = f"EX-{today.year}-"
    last = (
        await session.execute(
            select(func.max(ExpenseReport.report_no)).where(
                ExpenseReport.report_no.like(f"{prefix}%")
            )
        )
    ).scalar_one_or_none()
    sequence = int(last[len(prefix) :]) + 1 if last else 1
    return f"{prefix}{sequence:04d}"
