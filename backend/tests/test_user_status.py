import pytest

from app.enums import UserStatus
from app.errors import ConflictError, ForbiddenError
from app.services.user_status import (
    SIGNUP_ALLOWED_TRANSITIONS,
    SIGNUP_TRANSITION_ACTOR,
    SignupActor,
    assert_signup_transition_allowed,
)


def test_user_status_members():
    # 리터럴에서 파생시킨다. set(UserStatus)로 쓰면 멤버를 늘리는 변경과 테스트가
    # 함께 움직여 통과한다.
    assert {s.value for s in UserStatus} == {"PENDING", "ACTIVE", "REJECTED"}


def test_user_status_is_str():
    # StrEnum이어야 varchar 저장·JSON 직렬화가 지금의 role과 같은 모양이 된다.
    assert UserStatus.PENDING == "PENDING"


# 리터럴이다. SIGNUP_ALLOWED_TRANSITIONS에서 파생시키면 표를 넓히는 버그와
# 테스트가 함께 움직여 통과한다.
_LEGAL = [
    (UserStatus.PENDING, UserStatus.ACTIVE),
    (UserStatus.PENDING, UserStatus.REJECTED),
    (UserStatus.REJECTED, UserStatus.PENDING),
]
_ILLEGAL = [
    (UserStatus.ACTIVE, UserStatus.PENDING),
    (UserStatus.ACTIVE, UserStatus.REJECTED),
    (UserStatus.ACTIVE, UserStatus.ACTIVE),
    (UserStatus.PENDING, UserStatus.PENDING),
    (UserStatus.REJECTED, UserStatus.ACTIVE),
    (UserStatus.REJECTED, UserStatus.REJECTED),
]


@pytest.mark.parametrize(("current", "target"), _LEGAL)
def test_legal_transitions_pass(current, target):
    actor = SIGNUP_TRANSITION_ACTOR[(current, target)]
    assert_signup_transition_allowed(current, target, actor=actor)


@pytest.mark.parametrize(("current", "target"), _ILLEGAL)
def test_illegal_transitions_conflict(current, target):
    with pytest.raises(ConflictError) as exc:
        assert_signup_transition_allowed(current, target, actor=SignupActor.ADMIN)
    assert exc.value.code == "USER_INVALID_TRANSITION"
    assert exc.value.status_code == 409


def test_transition_table_covers_every_status():
    assert set(SIGNUP_ALLOWED_TRANSITIONS) == set(UserStatus)


def test_wrong_actor_is_forbidden():
    # 재신청(REJECTED -> PENDING)은 가입자의 전이다. 관리자 주체로 부르면 거부해야 한다.
    with pytest.raises(ForbiddenError) as exc:
        assert_signup_transition_allowed(
            UserStatus.REJECTED, UserStatus.PENDING, actor=SignupActor.ADMIN
        )
    assert exc.value.code == "WRONG_TRANSITION_ACTOR"


def test_admin_transition_rejects_applicant_actor():
    with pytest.raises(ForbiddenError):
        assert_signup_transition_allowed(
            UserStatus.PENDING, UserStatus.ACTIVE, actor=SignupActor.APPLICANT
        )
