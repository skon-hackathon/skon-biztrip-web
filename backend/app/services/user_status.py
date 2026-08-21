"""가입 상태전이의 적법성과 수행 주체를 한 번에 판단한다.

호출부는 `assert_signup_transition_allowed` **하나만** 부른다. 적법성 표와 주체 표를
따로 부를 수 있게 열어두지 않는 이유는 출장·정산에서 이미 정한 것과 같다 — 나뉘어 있으면
언젠가 한쪽만 부르고, 그 실패는 fail-open이다. 여기서는 "미인증 가입 경로가 관리자 전용
승인 전이를 통과한다"가 된다.

전이를 추가하고 주체를 빠뜨리면 임포트 시점에 RuntimeError로 죽는다.
"""

from enum import Enum

from app.enums import UserStatus
from app.errors import ConflictError, ForbiddenError


class SignupActor(Enum):
    """전이를 수행할 수 있는 주체."""

    ADMIN = "ADMIN"
    #: 미인증 가입자. 로그인하지 않은 상태에서 재신청을 수행한다.
    APPLICANT = "APPLICANT"


SIGNUP_ALLOWED_TRANSITIONS: dict[UserStatus, frozenset[UserStatus]] = {
    UserStatus.PENDING: frozenset({UserStatus.ACTIVE, UserStatus.REJECTED}),
    UserStatus.REJECTED: frozenset({UserStatus.PENDING}),
    # ACTIVE에서 나가는 전이는 없다. 계정 정지는 전이가 아니라
    # PATCH /admin/users/{id}의 is_active 변경이다.
    UserStatus.ACTIVE: frozenset(),
}

_missing_statuses = set(UserStatus) - set(SIGNUP_ALLOWED_TRANSITIONS)
if _missing_statuses:
    raise RuntimeError(f"SIGNUP_ALLOWED_TRANSITIONS missing entries for {_missing_statuses}")

#: 각 전이의 수행 주체. 아래 가드가 SIGNUP_ALLOWED_TRANSITIONS와의 일치를 임포트
#: 시점에 강제한다 — 전이를 추가하고 주체를 빠뜨리면 조용히 "아무나 가능"이 되는 게
#: 아니라 임포트가 깨진다.
SIGNUP_TRANSITION_ACTOR: dict[tuple[UserStatus, UserStatus], SignupActor] = {
    (UserStatus.PENDING, UserStatus.ACTIVE): SignupActor.ADMIN,
    (UserStatus.PENDING, UserStatus.REJECTED): SignupActor.ADMIN,
    (UserStatus.REJECTED, UserStatus.PENDING): SignupActor.APPLICANT,
}

_all_transitions = {
    (current, target)
    for current, targets in SIGNUP_ALLOWED_TRANSITIONS.items()
    for target in targets
}
_missing_actors = _all_transitions - set(SIGNUP_TRANSITION_ACTOR)
_extra_actors = set(SIGNUP_TRANSITION_ACTOR) - _all_transitions
if _missing_actors or _extra_actors:
    raise RuntimeError(
        "SIGNUP_TRANSITION_ACTOR가 SIGNUP_ALLOWED_TRANSITIONS와 어긋납니다: "
        f"missing={_missing_actors} extra={_extra_actors}"
    )


def assert_signup_transition_allowed(
    current: UserStatus, target: UserStatus, *, actor: SignupActor
) -> None:
    """적법성과 주체를 한 번에 검사한다. 호출부는 이것만 부른다."""
    if target not in SIGNUP_ALLOWED_TRANSITIONS[current]:
        raise ConflictError(
            "USER_INVALID_TRANSITION",
            f"{current} 상태에서 {target} 로 변경할 수 없습니다",
        )
    expected = SIGNUP_TRANSITION_ACTOR[(current, target)]
    if actor is not expected:
        raise ForbiddenError(
            "WRONG_TRANSITION_ACTOR", "이 전이를 수행할 수 있는 주체가 아닙니다"
        )
