from sqlalchemy import select

from app.enums import UserRole
from app.models import Code, CodeGroup, CostCenter, Department, FundCenter, User


async def test_can_persist_department_and_user(db_session):
    dept = Department(code="D100", name="배터리연구소")
    db_session.add(dept)
    await db_session.flush()

    manager = User(
        email="manager@skon.example",
        password_hash="x",
        name="김팀장",
        employee_no="E0001",
        department_id=dept.id,
        position_code="TEAM_LEADER",
        role=UserRole.MANAGER,
    )
    db_session.add(manager)
    await db_session.flush()

    member = User(
        email="member@skon.example",
        password_hash="x",
        name="이사원",
        employee_no="E0002",
        department_id=dept.id,
        position_code="STAFF",
        role=UserRole.EMPLOYEE,
        manager_id=manager.id,
    )
    db_session.add(member)
    await db_session.flush()

    found = (await db_session.execute(select(User).where(User.email == "member@skon.example"))).scalar_one()
    assert found.manager_id == manager.id
    assert found.role is UserRole.EMPLOYEE
    assert found.is_active is True


async def test_department_can_have_parent_department(db_session):
    parent = Department(code="D000", name="본부")
    db_session.add(parent)
    await db_session.flush()

    child = Department(code="D001", name="배터리연구소", parent_id=parent.id)
    db_session.add(child)
    await db_session.flush()

    found = (await db_session.execute(select(Department).where(Department.code == "D001"))).scalar_one()
    assert found.parent_id == parent.id


async def test_code_group_holds_codes_with_extra(db_session):
    group = CodeGroup(group_code="COUNTRY", name="국가")
    db_session.add(group)
    await db_session.flush()

    db_session.add(
        Code(group_id=group.id, code="US", name="미국", sort_order=1, extra={"currency": "USD"})
    )
    await db_session.flush()

    code = (await db_session.execute(select(Code).where(Code.code == "US"))).scalar_one()
    assert code.extra["currency"] == "USD"
    assert code.is_active is True


async def test_centers_can_link_to_department(db_session):
    dept = Department(code="D200", name="구매팀")
    db_session.add(dept)
    await db_session.flush()

    db_session.add(FundCenter(code="FC1010", name="배터리연구소 비용처리", department_id=dept.id))
    db_session.add(CostCenter(code="CC2030", name="구매팀 비용사용", department_id=dept.id))
    await db_session.flush()

    fc = (await db_session.execute(select(FundCenter).where(FundCenter.code == "FC1010"))).scalar_one()
    cc = (await db_session.execute(select(CostCenter).where(CostCenter.code == "CC2030"))).scalar_one()
    assert fc.department_id == dept.id
    assert cc.is_active is True
