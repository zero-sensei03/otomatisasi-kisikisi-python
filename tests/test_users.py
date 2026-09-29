import pytest

from app.core.security import hash_password, verify_password
from app.models import Teacher, User, UserRole
from app.schemas.user import UserCreate
from app.services.user import UserService


def create_admin(db_session):
    admin = User(
        username="admin",
        email="admin@example.com",
        password_hash=hash_password("Password@123"),
        full_name="Administrator",
        role=UserRole.ADMIN,
        is_active=True,
    )

    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)

    return admin


def create_guru(
    db_session,
    username="guru",
    email="guru@example.com",
    full_name="Guru Test",
    employee_number="GURU001",
    is_active=True,
):
    user = User(
        username=username,
        email=email,
        password_hash=hash_password(
            "Password@123"
        ),
        full_name=full_name,
        role=UserRole.GURU,
        is_active=is_active,
    )

    db_session.add(user)
    db_session.flush()

    teacher = Teacher(
        user_id=user.id,
        employee_number=employee_number,
    )

    db_session.add(teacher)
    db_session.commit()
    db_session.refresh(user)

    return user


# ============================================================
# HELPER / READ TESTS
# ============================================================


def test_get_all_users(db_session):
    create_admin(db_session)
    create_guru(db_session)

    service = UserService(db_session)

    users = service.get_all()

    assert len(users) == 2


def test_get_all_users_empty(db_session):
    service = UserService(db_session)

    users = service.get_all()

    assert users == []


def test_get_user_by_id(db_session):
    user = create_guru(db_session)

    service = UserService(db_session)

    result = service.get_by_id(user.id)

    assert result is not None
    assert result.id == user.id
    assert result.username == "guru"


def test_get_user_by_id_not_found(db_session):
    service = UserService(db_session)

    result = service.get_by_id(99999)

    assert result is None


# ============================================================
# CREATE TESTS
# ============================================================


def test_create_guru(db_session):
    service = UserService(db_session)

    data = UserCreate(
        username="newguru",
        email="newguru@example.com",
        password="Password@123",
        full_name="New Guru",
    )

    user = service.create_guru(
        data,
        employee_number="GURU002",
    )

    assert user.id is not None
    assert user.username == "newguru"
    assert user.email == "newguru@example.com"
    assert user.full_name == "New Guru"
    assert user.role == UserRole.GURU
    assert user.is_active is True

    assert verify_password(
        "Password@123",
        user.password_hash,
    )

    teacher = (
        db_session.query(Teacher)
        .filter(
            Teacher.user_id == user.id
        )
        .first()
    )

    assert teacher is not None
    assert teacher.employee_number == "GURU002"


def test_create_guru_without_employee_number(
    db_session,
):
    service = UserService(db_session)

    data = UserCreate(
        username="newguru",
        email="newguru@example.com",
        password="Password@123",
        full_name="New Guru",
    )

    user = service.create_guru(data)

    assert user.id is not None

    teacher = (
        db_session.query(Teacher)
        .filter(
            Teacher.user_id == user.id
        )
        .first()
    )

    assert teacher is not None
    assert teacher.employee_number is None


def test_create_guru_duplicate_username(
    db_session,
):
    create_guru(db_session)

    service = UserService(db_session)

    data = UserCreate(
        username="guru",
        email="newemail@example.com",
        password="Password@123",
        full_name="Another Guru",
    )

    with pytest.raises(
        ValueError,
        match="Username sudah digunakan",
    ):
        service.create_guru(data)


def test_create_guru_duplicate_email(
    db_session,
):
    create_guru(db_session)

    service = UserService(db_session)

    data = UserCreate(
        username="anotherguru",
        email="guru@example.com",
        password="Password@123",
        full_name="Another Guru",
    )

    with pytest.raises(
        ValueError,
        match="Email sudah digunakan",
    ):
        service.create_guru(data)


def test_create_guru_creates_teacher_profile(
    db_session,
):
    service = UserService(db_session)

    data = UserCreate(
        username="teacherprofile",
        email="teacherprofile@example.com",
        password="Password@123",
        full_name="Teacher Profile",
    )

    user = service.create_guru(
        data,
        employee_number="EMP001",
    )

    teacher = (
        db_session.query(Teacher)
        .filter(
            Teacher.user_id == user.id
        )
        .first()
    )

    assert teacher is not None
    assert teacher.user_id == user.id
    assert teacher.employee_number == "EMP001"


# ============================================================
# UPDATE TESTS
# ============================================================


def test_update_guru(db_session):
    user = create_guru(db_session)

    service = UserService(db_session)

    old_password_hash = user.password_hash

    updated_user = service.update_guru(
        user_id=user.id,
        username="updatedguru",
        email="updated@example.com",
        full_name="Updated Guru",
        employee_number="GURU999",
        password="NewPassword@123",
    )

    assert updated_user.username == "updatedguru"
    assert updated_user.email == "updated@example.com"
    assert updated_user.full_name == "Updated Guru"

    assert updated_user.password_hash != old_password_hash

    assert verify_password(
        "NewPassword@123",
        updated_user.password_hash,
    )

    teacher = (
        db_session.query(Teacher)
        .filter(
            Teacher.user_id == user.id
        )
        .first()
    )

    assert teacher is not None
    assert teacher.employee_number == "GURU999"


def test_update_guru_without_password_change(
    db_session,
):
    user = create_guru(db_session)

    original_password_hash = user.password_hash

    service = UserService(db_session)

    updated_user = service.update_guru(
        user_id=user.id,
        username="updatedguru",
        email="updated@example.com",
        full_name="Updated Guru",
    )

    assert updated_user.username == "updatedguru"
    assert (
        updated_user.password_hash
        == original_password_hash
    )

    assert verify_password(
        "Password@123",
        updated_user.password_hash,
    )


def test_update_guru_creates_missing_teacher_profile(
    db_session,
):
    user = User(
        username="withoutteacher",
        email="withoutteacher@example.com",
        password_hash=hash_password(
            "Password@123"
        ),
        full_name="Without Teacher",
        role=UserRole.GURU,
        is_active=True,
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.teacher is None

    service = UserService(db_session)

    updated_user = service.update_guru(
        user_id=user.id,
        username="withteacher",
        email="withteacher@example.com",
        full_name="With Teacher",
        employee_number="NEW001",
    )

    assert updated_user.username == "withteacher"

    teacher = (
        db_session.query(Teacher)
        .filter(
            Teacher.user_id == user.id
        )
        .first()
    )

    assert teacher is not None
    assert teacher.employee_number == "NEW001"


def test_update_guru_trims_values(
    db_session,
):
    user = create_guru(db_session)

    service = UserService(db_session)

    updated_user = service.update_guru(
        user_id=user.id,
        username="  updatedguru  ",
        email="  updated@example.com  ",
        full_name="  Updated Guru  ",
        employee_number="  EMP999  ",
    )

    assert updated_user.username == "updatedguru"
    assert updated_user.email == "updated@example.com"
    assert updated_user.full_name == "Updated Guru"

    teacher = (
        db_session.query(Teacher)
        .filter(
            Teacher.user_id == user.id
        )
        .first()
    )

    assert teacher.employee_number == "EMP999"


def test_update_guru_duplicate_username(
    db_session,
):
    create_guru(db_session)

    second_user = create_guru(
        db_session,
        username="secondguru",
        email="second@example.com",
        employee_number="GURU002",
    )

    service = UserService(db_session)

    with pytest.raises(
        ValueError,
        match="Username sudah digunakan",
    ):
        service.update_guru(
            user_id=second_user.id,
            username="guru",
            email="second@example.com",
            full_name="Second Guru",
        )


def test_update_guru_duplicate_email(
    db_session,
):
    create_guru(db_session)

    second_user = create_guru(
        db_session,
        username="secondguru",
        email="second@example.com",
        employee_number="GURU002",
    )

    service = UserService(db_session)

    with pytest.raises(
        ValueError,
        match="Email sudah digunakan",
    ):
        service.update_guru(
            user_id=second_user.id,
            username="secondguru",
            email="guru@example.com",
            full_name="Second Guru",
        )


def test_update_guru_not_found(db_session):
    service = UserService(db_session)

    with pytest.raises(
        ValueError,
        match="User tidak ditemukan",
    ):
        service.update_guru(
            user_id=99999,
            username="guru",
            email="guru@example.com",
            full_name="Guru",
        )


def test_update_admin_is_rejected(db_session):
    admin = create_admin(db_session)

    service = UserService(db_session)

    with pytest.raises(
        ValueError,
        match="Hanya akun GURU yang dapat diedit",
    ):
        service.update_guru(
            user_id=admin.id,
            username="newadmin",
            email="newadmin@example.com",
            full_name="New Admin",
        )


# ============================================================
# ACTIVE / INACTIVE TESTS
# ============================================================


def test_set_active_false(db_session):
    user = create_guru(db_session)

    service = UserService(db_session)

    updated_user = service.set_active(
        user.id,
        False,
    )

    assert updated_user.is_active is False


def test_set_active_true(db_session):
    user = create_guru(
        db_session,
        is_active=False,
    )

    service = UserService(db_session)

    updated_user = service.set_active(
        user.id,
        True,
    )

    assert updated_user.is_active is True


def test_set_active_not_found(db_session):
    service = UserService(db_session)

    with pytest.raises(
        ValueError,
        match="User tidak ditemukan",
    ):
        service.set_active(
            99999,
            False,
        )


def test_set_active_admin(db_session):
    admin = create_admin(db_session)

    service = UserService(db_session)

    updated_user = service.set_active(
        admin.id,
        False,
    )

    assert updated_user.is_active is False


# ============================================================
# DELETE TESTS
# ============================================================


def test_delete_guru(db_session):
    user = create_guru(db_session)

    service = UserService(db_session)

    service.delete(
        user_id=user.id,
        current_user_id=999,
    )

    deleted_user = db_session.get(
        User,
        user.id,
    )

    assert deleted_user is None

    teacher = (
        db_session.query(Teacher)
        .filter(
            Teacher.user_id == user.id
        )
        .first()
    )

    assert teacher is None


def test_delete_user_not_found(db_session):
    service = UserService(db_session)

    with pytest.raises(
        ValueError,
        match="User tidak ditemukan",
    ):
        service.delete(
            user_id=99999,
            current_user_id=1,
        )


def test_cannot_delete_current_user(
    db_session,
):
    user = create_guru(db_session)

    service = UserService(db_session)

    with pytest.raises(
        ValueError,
        match="Akun yang sedang digunakan tidak dapat dihapus",
    ):
        service.delete(
            user_id=user.id,
            current_user_id=user.id,
        )

    existing_user = db_session.get(
        User,
        user.id,
    )

    assert existing_user is not None


def test_delete_admin_when_not_current_user(
    db_session,
):
    admin = create_admin(db_session)

    service = UserService(db_session)

    service.delete(
        user_id=admin.id,
        current_user_id=999,
    )

    deleted_admin = db_session.get(
        User,
        admin.id,
    )

    assert deleted_admin is None