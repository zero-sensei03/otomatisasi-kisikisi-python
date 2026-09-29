import pytest

from app.models import ClassRoom
from app.schemas.class_room import (
    ClassRoomCreate,
    ClassRoomUpdate,
)
from app.services.class_room import ClassRoomService


def create_class_room(
    db_session,
    name="VII-A",
    grade_level="VII",
    description="Kelas VII A",
    is_active=True,
):
    class_room = ClassRoom(
        name=name,
        grade_level=grade_level,
        description=description,
        is_active=is_active,
    )

    db_session.add(class_room)
    db_session.commit()
    db_session.refresh(class_room)

    return class_room


# ============================================================
# SCHEMA TESTS
# ============================================================


def test_class_room_create_schema():
    class_room = ClassRoomCreate(
        name="VII-A",
        grade_level="VII",
        description="Kelas VII A",
    )

    assert class_room.name == "VII-A"
    assert class_room.grade_level == "VII"
    assert class_room.description == "Kelas VII A"


def test_class_room_update_schema():
    class_room = ClassRoomUpdate(
        name="VIII-B",
        grade_level="VIII",
    )

    assert class_room.name == "VIII-B"
    assert class_room.grade_level == "VIII"
    assert class_room.description is None


# ============================================================
# CREATE TESTS
# ============================================================


def test_class_room_service_create(db_session):
    service = ClassRoomService(db_session)

    data = ClassRoomCreate(
        name="VII-A",
        grade_level="VII",
        description="Kelas VII A",
    )

    class_room = service.create(data)

    assert class_room.id is not None
    assert class_room.name == "VII-A"
    assert class_room.grade_level == "VII"
    assert class_room.description == "Kelas VII A"
    assert class_room.is_active is True


def test_class_room_create_trims_name(db_session):
    service = ClassRoomService(db_session)

    data = ClassRoomCreate(
        name="  VII-A  ",
        grade_level="VII",
    )

    class_room = service.create(data)

    assert class_room.name == "VII-A"


def test_class_room_create_trims_grade_level(
    db_session,
):
    service = ClassRoomService(db_session)

    data = ClassRoomCreate(
        name="VII-A",
        grade_level="  VII  ",
    )

    class_room = service.create(data)

    assert class_room.grade_level == "VII"


def test_class_room_create_trims_description(
    db_session,
):
    service = ClassRoomService(db_session)

    data = ClassRoomCreate(
        name="VII-A",
        grade_level="VII",
        description="  Kelas VII A  ",
    )

    class_room = service.create(data)

    assert class_room.description == "Kelas VII A"


def test_class_room_create_without_description(
    db_session,
):
    service = ClassRoomService(db_session)

    data = ClassRoomCreate(
        name="VII-A",
        grade_level="VII",
    )

    class_room = service.create(data)

    assert class_room.description is None


def test_class_room_create_duplicate_name(
    db_session,
):
    create_class_room(db_session)

    service = ClassRoomService(db_session)

    data = ClassRoomCreate(
        name="VII-A",
        grade_level="VII",
    )

    with pytest.raises(
        ValueError,
        match="Nama kelas sudah digunakan",
    ):
        service.create(data)


def test_class_room_create_empty_name(
    db_session,
):
    service = ClassRoomService(db_session)

    data = ClassRoomCreate(
        name="   ",
        grade_level="VII",
    )

    with pytest.raises(
        ValueError,
        match="Nama kelas wajib diisi",
    ):
        service.create(data)


def test_class_room_create_empty_grade_level(
    db_session,
):
    service = ClassRoomService(db_session)

    data = ClassRoomCreate(
        name="VII-A",
        grade_level="   ",
    )

    with pytest.raises(
        ValueError,
        match="Tingkat kelas wajib diisi",
    ):
        service.create(data)


# ============================================================
# READ TESTS
# ============================================================


def test_class_room_get_all(db_session):
    create_class_room(
        db_session,
        name="VII-A",
        grade_level="VII",
    )

    create_class_room(
        db_session,
        name="VIII-A",
        grade_level="VIII",
    )

    create_class_room(
        db_session,
        name="IX-A",
        grade_level="IX",
    )

    service = ClassRoomService(db_session)

    class_rooms = service.get_all()

    assert len(class_rooms) == 3

    names = [
        class_room.name
        for class_room in class_rooms
    ]

    assert "VII-A" in names
    assert "VIII-A" in names
    assert "IX-A" in names


def test_class_room_get_all_empty(db_session):
    service = ClassRoomService(db_session)

    class_rooms = service.get_all()

    assert class_rooms == []


def test_class_room_get_by_id(db_session):
    class_room = create_class_room(
        db_session
    )

    service = ClassRoomService(db_session)

    result = service.get_by_id(
        class_room.id
    )

    assert result is not None
    assert result.id == class_room.id
    assert result.name == "VII-A"
    assert result.grade_level == "VII"


def test_class_room_get_by_id_not_found(
    db_session,
):
    service = ClassRoomService(db_session)

    result = service.get_by_id(99999)

    assert result is None


# ============================================================
# UPDATE TESTS
# ============================================================


def test_class_room_update(db_session):
    class_room = create_class_room(
        db_session
    )

    service = ClassRoomService(db_session)

    data = ClassRoomUpdate(
        name="VII-B",
        grade_level="VII",
        description="Kelas VII B",
    )

    updated_class_room = service.update(
        class_room.id,
        data,
    )

    assert updated_class_room.id == class_room.id
    assert updated_class_room.name == "VII-B"
    assert updated_class_room.grade_level == "VII"
    assert (
        updated_class_room.description
        == "Kelas VII B"
    )


def test_class_room_update_without_description(
    db_session,
):
    class_room = create_class_room(
        db_session
    )

    service = ClassRoomService(db_session)

    data = ClassRoomUpdate(
        name="VII-B",
        grade_level="VII",
    )

    updated_class_room = service.update(
        class_room.id,
        data,
    )

    assert updated_class_room.name == "VII-B"
    assert updated_class_room.description is None


def test_class_room_update_trims_values(
    db_session,
):
    class_room = create_class_room(
        db_session
    )

    service = ClassRoomService(db_session)

    data = ClassRoomUpdate(
        name="  VII-B  ",
        grade_level="  VII  ",
        description="  Kelas VII B  ",
    )

    updated_class_room = service.update(
        class_room.id,
        data,
    )

    assert updated_class_room.name == "VII-B"
    assert updated_class_room.grade_level == "VII"
    assert (
        updated_class_room.description
        == "Kelas VII B"
    )


def test_class_room_update_duplicate_name(
    db_session,
):
    create_class_room(
        db_session,
        name="VII-A",
    )

    second_class = create_class_room(
        db_session,
        name="VII-B",
    )

    service = ClassRoomService(db_session)

    data = ClassRoomUpdate(
        name="VII-A",
        grade_level="VII",
    )

    with pytest.raises(
        ValueError,
        match="Nama kelas sudah digunakan",
    ):
        service.update(
            second_class.id,
            data,
        )


def test_class_room_update_same_name(
    db_session,
):
    class_room = create_class_room(
        db_session,
        name="VII-A",
    )

    service = ClassRoomService(db_session)

    data = ClassRoomUpdate(
        name="VII-A",
        grade_level="VII",
        description="Updated description",
    )

    updated_class_room = service.update(
        class_room.id,
        data,
    )

    assert updated_class_room.name == "VII-A"
    assert (
        updated_class_room.description
        == "Updated description"
    )


def test_class_room_update_empty_name(
    db_session,
):
    class_room = create_class_room(
        db_session
    )

    service = ClassRoomService(db_session)

    data = ClassRoomUpdate(
        name="   ",
        grade_level="VII",
    )

    with pytest.raises(
        ValueError,
        match="Nama kelas wajib diisi",
    ):
        service.update(
            class_room.id,
            data,
        )


def test_class_room_update_empty_grade_level(
    db_session,
):
    class_room = create_class_room(
        db_session
    )

    service = ClassRoomService(db_session)

    data = ClassRoomUpdate(
        name="VII-B",
        grade_level="   ",
    )

    with pytest.raises(
        ValueError,
        match="Tingkat kelas wajib diisi",
    ):
        service.update(
            class_room.id,
            data,
        )


def test_class_room_update_not_found(
    db_session,
):
    service = ClassRoomService(db_session)

    data = ClassRoomUpdate(
        name="VII-A",
        grade_level="VII",
    )

    with pytest.raises(
        ValueError,
        match="Kelas tidak ditemukan",
    ):
        service.update(
            99999,
            data,
        )


# ============================================================
# ACTIVE / INACTIVE TESTS
# ============================================================


def test_class_room_set_active_false(
    db_session,
):
    class_room = create_class_room(
        db_session
    )

    assert class_room.is_active is True

    service = ClassRoomService(db_session)

    updated_class_room = service.set_active(
        class_room.id,
        False,
    )

    assert updated_class_room.is_active is False


def test_class_room_set_active_true(
    db_session,
):
    class_room = create_class_room(
        db_session,
        is_active=False,
    )

    assert class_room.is_active is False

    service = ClassRoomService(db_session)

    updated_class_room = service.set_active(
        class_room.id,
        True,
    )

    assert updated_class_room.is_active is True


def test_class_room_set_active_not_found(
    db_session,
):
    service = ClassRoomService(db_session)

    with pytest.raises(
        ValueError,
        match="Kelas tidak ditemukan",
    ):
        service.set_active(
            99999,
            False,
        )


# ============================================================
# DELETE TESTS
# ============================================================


def test_class_room_delete(db_session):
    class_room = create_class_room(
        db_session
    )

    service = ClassRoomService(db_session)

    service.delete(class_room.id)

    deleted_class_room = db_session.get(
        ClassRoom,
        class_room.id,
    )

    assert deleted_class_room is None


def test_class_room_delete_not_found(
    db_session,
):
    service = ClassRoomService(db_session)

    with pytest.raises(
        ValueError,
        match="Kelas tidak ditemukan",
    ):
        service.delete(99999)