"""Admin CRUD가 공유하는 세 가지 가드.

`delete_entity`가 존재하는 이유는 spec 7 "마스터 데이터" 절이다. 마스터 FK에는 `ondelete`를
걸지 않으므로 참조가 남은 행을 지우면 PostgreSQL이 거부하는 것이 옳다. 다만 그 `IntegrityError`를
그대로 두면 통일 에러 핸들러의 catch-all로 떨어져 **500**이 되고, Agent는 5xx를 재시도하므로
절대 성공할 수 없는 요청에 재시도 루프가 걸린다. 출장 금액 오버플로에서 이미 겪은 실패다.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ConflictError, ValidationError

#: bcrypt 5.x는 72바이트를 넘는 비밀번호를 자르지 않고 예외로 던진다. UTF-8 한글은 3바이트라
#: **24자면 경계**다. Pydantic의 max_length는 문자 수라서 이 검사를 대신할 수 없다.
MAX_PASSWORD_BYTES = 72
MIN_PASSWORD_LENGTH = 8


def assert_password_length(password: str, *, field: str = "password") -> None:
    """순수 검증 — DB 접근 없음."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValidationError(
            "PASSWORD_TOO_SHORT",
            f"비밀번호는 {MIN_PASSWORD_LENGTH}자 이상이어야 합니다",
            field=field,
        )
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValidationError(
            "PASSWORD_TOO_LONG",
            f"비밀번호는 UTF-8 기준 {MAX_PASSWORD_BYTES}바이트를 넘을 수 없습니다 (한글 24자)",
            field=field,
        )


async def assert_department(session: AsyncSession, department_id: int) -> None:
    """부서 존재 확인.

    `user.department_id`에는 FK가 없다 — 공유 테이블이 우리 스키마를 역참조하면 계정을
    공유하는 상대 프로젝트가 사용자를 만들 때 우리 department 행이 있어야 하기 때문이다.
    그래서 존재 검증을 서비스가 한다. 관리자 생성/수정과 미인증 가입이 **같은 함수**를
    부른다 — 복사하면 검증이 두 벌이 되어 한쪽만 고쳐진다.
    """
    from app.models import Department

    if await session.get(Department, department_id) is None:
        raise ValidationError(
            "INVALID_DEPARTMENT",
            f"존재하지 않는 부서입니다: {department_id}",
            field="department_id",
        )


async def assert_unique(
    session: AsyncSession, column, value: str, *, code: str, message: str, field: str
) -> None:
    """유니크 위반을 삽입 전에 409로 잡는다.

    `IntegrityError`를 받아 변환하지 않는 이유: 어떤 컬럼이 겹쳤는지 알 수 없어 `field`를
    채울 수 없다. TOCTOU가 남지만(동시에 같은 코드를 만들면 둘 다 통과) 최종 방어선은 DB의
    유니크 제약이다.
    """
    found = await session.scalar(select(column).where(column == value).limit(1))
    if found is not None:
        raise ConflictError(code, message, field=field)


async def delete_entity(session: AsyncSession, entity: Any, *, message: str) -> None:
    """ORM 삭제 + 참조 위반을 409 `HAS_DEPENDENTS`로 변환한다.

    Core의 일괄 `delete()`가 아니라 `session.delete()`를 쓴다 — `CodeGroup.codes`의
    `cascade="all, delete-orphan"`은 ORM 객체 삭제에만 적용되기 때문이다(spec 7).
    """
    await session.delete(entity)
    try:
        await session.flush()
    except IntegrityError as exc:
        # 실패한 flush 뒤의 세션은 오염 상태다. 롤백하지 않으면 이후 모든 문장이
        # PendingRollbackError가 되어 진짜 원인이 묻힌다.
        await session.rollback()
        raise ConflictError("HAS_DEPENDENTS", message) from exc
    await session.commit()
