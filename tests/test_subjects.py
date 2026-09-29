import pytest

from app.models import Subject
from app.schemas.subject import SubjectCreate, SubjectUpdate
from app.services.subject import SubjectService


def create_subject(
    db_session,
    code="MAT",
    name="Matematika",
    description="Mata pelajaran matematika",
):
    subject = Subject(
        code=code,
        name=name,
        description=description,
        is_active=True,
    )

    db_session.add(subject)
    db_session.commit()
    db_session.refresh(subject)

    return subject


# ============================================================
# SCHEMA TESTS
# ============================================================


def test_subject_create_schema():
    subject = SubjectCreate(
        code="mat",
        name="Matematika",
        description="Mata pelajaran matematika",
    )

    assert subject.code == "mat"
    assert subject.name == "Matematika"
    assert subject.description == "Mata pelajaran matematika"


def test_subject_update_schema():
    subject = SubjectUpdate(
        code="IPA",
        name="Ilmu Pengetahuan Alam",
    )

    assert subject.code == "IPA"
    assert subject.name == "Ilmu Pengetahuan Alam"
    assert subject.description is None


# ============================================================
# CREATE TESTS
# ============================================================


def test_subject_service_create(db_session):
    service = SubjectService(db_session)

    data = SubjectCreate(
        code="mat",
        name="Matematika",
        description="Mata pelajaran matematika",
    )

    subject = service.create(data)

    assert subject.id is not None
    assert subject.code == "MAT"
    assert subject.name == "Matematika"
    assert subject.description == "Mata pelajaran matematika"
    assert subject.is_active is True


def test_subject_create_code_is_normalized(db_session):
    service = SubjectService(db_session)

    data = SubjectCreate(
        code="  ipa  ",
        name="Ilmu Pengetahuan Alam",
    )

    subject = service.create(data)

    assert subject.code == "IPA"


def test_subject_create_name_is_trimmed(db_session):
    service = SubjectService(db_session)

    data = SubjectCreate(
        code="IPS",
        name="  Ilmu Pengetahuan Sosial  ",
    )

    subject = service.create(data)

    assert subject.name == "Ilmu Pengetahuan Sosial"


def test_subject_create_duplicate_code(db_session):
    create_subject(db_session)

    service = SubjectService(db_session)

    data = SubjectCreate(
        code="MAT",
        name="Matematika Lanjutan",
    )

    with pytest.raises(
        ValueError,
        match="Kode mata pelajaran sudah digunakan",
    ):
        service.create(data)


def test_subject_create_duplicate_code_case_insensitive(
    db_session,
):
    create_subject(db_session)

    service = SubjectService(db_session)

    data = SubjectCreate(
        code="mat",
        name="Matematika Lanjutan",
    )

    with pytest.raises(
        ValueError,
        match="Kode mata pelajaran sudah digunakan",
    ):
        service.create(data)


def test_subject_create_duplicate_name(db_session):
    create_subject(db_session)

    service = SubjectService(db_session)

    data = SubjectCreate(
        code="MAT2",
        name="Matematika",
    )

    with pytest.raises(
        ValueError,
        match="Nama mata pelajaran sudah digunakan",
    ):
        service.create(data)


def test_subject_create_empty_code(db_session):
    service = SubjectService(db_session)

    data = SubjectCreate(
        code="   ",
        name="Matematika",
    )

    with pytest.raises(
        ValueError,
        match="Kode mata pelajaran wajib diisi",
    ):
        service.create(data)


def test_subject_create_empty_name(db_session):
    service = SubjectService(db_session)

    data = SubjectCreate(
        code="MAT",
        name="   ",
    )

    with pytest.raises(
        ValueError,
        match="Nama mata pelajaran wajib diisi",
    ):
        service.create(data)


# ============================================================
# READ TESTS
# ============================================================


def test_subject_get_all(db_session):
    create_subject(
        db_session,
        code="MAT",
        name="Matematika",
    )

    create_subject(
        db_session,
        code="IPA",
        name="Ilmu Pengetahuan Alam",
    )

    create_subject(
        db_session,
        code="IPS",
        name="Ilmu Pengetahuan Sosial",
    )

    service = SubjectService(db_session)

    subjects = service.get_all()

    assert len(subjects) == 3

    names = [subject.name for subject in subjects]

    assert "Matematika" in names
    assert "Ilmu Pengetahuan Alam" in names
    assert "Ilmu Pengetahuan Sosial" in names


def test_subject_get_by_id(db_session):
    subject = create_subject(db_session)

    service = SubjectService(db_session)

    result = service.get_by_id(subject.id)

    assert result is not None
    assert result.id == subject.id
    assert result.code == "MAT"
    assert result.name == "Matematika"


def test_subject_get_by_id_not_found(db_session):
    service = SubjectService(db_session)

    result = service.get_by_id(99999)

    assert result is None


# ============================================================
# UPDATE TESTS
# ============================================================


def test_subject_update(db_session):
    subject = create_subject(db_session)

    service = SubjectService(db_session)

    data = SubjectUpdate(
        code="MTK",
        name="Matematika SMP",
        description="Matematika tingkat SMP",
    )

    updated_subject = service.update(
        subject.id,
        data,
    )

    assert updated_subject.id == subject.id
    assert updated_subject.code == "MTK"
    assert updated_subject.name == "Matematika SMP"
    assert (
        updated_subject.description
        == "Matematika tingkat SMP"
    )


def test_subject_update_without_description(db_session):
    subject = create_subject(db_session)

    service = SubjectService(db_session)

    data = SubjectUpdate(
        code="MTK",
        name="Matematika SMP",
    )

    updated_subject = service.update(
        subject.id,
        data,
    )

    assert updated_subject.code == "MTK"
    assert updated_subject.name == "Matematika SMP"
    assert updated_subject.description is None


def test_subject_update_normalizes_code(db_session):
    subject = create_subject(db_session)

    service = SubjectService(db_session)

    data = SubjectUpdate(
        code="  mtk  ",
        name="Matematika SMP",
    )

    updated_subject = service.update(
        subject.id,
        data,
    )

    assert updated_subject.code == "MTK"


def test_subject_update_duplicate_code(db_session):
    create_subject(
        db_session,
        code="MAT",
        name="Matematika",
    )

    second_subject = create_subject(
        db_session,
        code="IPA",
        name="Ilmu Pengetahuan Alam",
    )

    service = SubjectService(db_session)

    data = SubjectUpdate(
        code="MAT",
        name="Ilmu Pengetahuan Alam",
    )

    with pytest.raises(
        ValueError,
        match="Kode mata pelajaran sudah digunakan",
    ):
        service.update(
            second_subject.id,
            data,
        )


def test_subject_update_duplicate_name(db_session):
    create_subject(
        db_session,
        code="MAT",
        name="Matematika",
    )

    second_subject = create_subject(
        db_session,
        code="IPA",
        name="Ilmu Pengetahuan Alam",
    )

    service = SubjectService(db_session)

    data = SubjectUpdate(
        code="IPA2",
        name="Matematika",
    )

    with pytest.raises(
        ValueError,
        match="Nama mata pelajaran sudah digunakan",
    ):
        service.update(
            second_subject.id,
            data,
        )


def test_subject_update_not_found(db_session):
    service = SubjectService(db_session)

    data = SubjectUpdate(
        code="MAT",
        name="Matematika",
    )

    with pytest.raises(
        ValueError,
        match="Mata pelajaran tidak ditemukan",
    ):
        service.update(
            99999,
            data,
        )


# ============================================================
# ACTIVE / INACTIVE TESTS
# ============================================================


def test_subject_set_active_false(db_session):
    subject = create_subject(db_session)

    assert subject.is_active is True

    service = SubjectService(db_session)

    updated_subject = service.set_active(
        subject.id,
        False,
    )

    assert updated_subject.is_active is False


def test_subject_set_active_true(db_session):
    subject = create_subject(db_session)

    subject.is_active = False
    db_session.commit()

    service = SubjectService(db_session)

    updated_subject = service.set_active(
        subject.id,
        True,
    )

    assert updated_subject.is_active is True


def test_subject_set_active_not_found(db_session):
    service = SubjectService(db_session)

    with pytest.raises(
        ValueError,
        match="Mata pelajaran tidak ditemukan",
    ):
        service.set_active(
            99999,
            False,
        )


# ============================================================
# DELETE TESTS
# ============================================================


def test_subject_delete(db_session):
    subject = create_subject(db_session)

    service = SubjectService(db_session)

    service.delete(subject.id)

    deleted_subject = db_session.get(
        Subject,
        subject.id,
    )

    assert deleted_subject is None


def test_subject_delete_not_found(db_session):
    service = SubjectService(db_session)

    with pytest.raises(
        ValueError,
        match="Mata pelajaran tidak ditemukan",
    ):
        service.delete(99999)