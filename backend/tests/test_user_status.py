from app.enums import UserStatus


def test_user_status_members():
    # 리터럴에서 파생시킨다. set(UserStatus)로 쓰면 멤버를 늘리는 변경과 테스트가
    # 함께 움직여 통과한다.
    assert {s.value for s in UserStatus} == {"PENDING", "ACTIVE", "REJECTED"}


def test_user_status_is_str():
    # StrEnum이어야 varchar 저장·JSON 직렬화가 지금의 role과 같은 모양이 된다.
    assert UserStatus.PENDING == "PENDING"
