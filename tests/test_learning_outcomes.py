import pytest

from app.core.security import hash_password
from app.models import LearningOutcome, Subject, User, UserRole
from app.schemas.learning_outcome import (
    LearningOutcomeCreate,
    LearningOutcomeUpdate,
)
from app.services.learning_outcome import (
    LearningOutcomeService,
)


def create_subject(
    db_session,
    code="MAT",
    name="Matematika",
    is_active=True,
):
    subject = Subject(
        code=code,
        name=name,
        description="Mata pelajaran",
        is_active=is_active,
    )

    db_session.add(subject)
    db_session.commit()
    db_session.refresh(subject)

    return subject


def create_admin(db_session):
    admin = User(
        username="admin",
        email="admin@example.com",
        password_hash=hash_password(
            "Password@123"
        ),
        full_name="Administrator",
        role=UserRole.ADMIN,
        is_active=True,
    )

    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)

    return admin


def create_learning_outcome(
    db_session,
    subject_id,
    code="CP-01",
    description="Peserta didik mampu memahami konsep.",
    is_active=True,
):
    learning_outcome = LearningOutcome(
        subject_id=subject_id,
        code=code,
        description=description,
        is_active=is_active,
    )

    db_session.add(learning_outcome)
    db_session.commit()
    db_session.refresh(learning_outcome)

    return learning_outcome


# ============================================================
# SCHEMA TESTS
# ============================================================


def test_learning_outcome_create_schema():
    learning_outcome = LearningOutcomeCreate(
        subject_id=1,
        code="CP-01",
        description="Peserta didik mampu memahami konsep.",
    )

    assert learning_outcome.subject_id == 1
    assert learning_outcome.code == "CP-01"
    assert (
        learning_outcome.description
        == "Peserta didik mampu memahami konsep."
    )


def test_learning_outcome_update_schema():
    learning_outcome = LearningOutcomeUpdate(
        subject_id=2,
        code="CP-02",
        description="Peserta didik mampu menerapkan konsep.",
    )

    assert learning_outcome.subject_id == 2
    assert learning_outcome.code == "CP-02"
    assert (
        learning_outcome.description
        == "Peserta didik mampu menerapkan konsep."
    )


# ============================================================
# CREATE TESTS
# ============================================================


def test_learning_outcome_create(db_session):
    subject = create_subject(db_session)

    service = LearningOutcomeService(
        db_session
    )

    data = LearningOutcomeCreate(
        subject_id=subject.id,
        code="CP-01",
        description="Peserta didik mampu memahami konsep.",
    )

    learning_outcome = service.create(data)

    assert learning_outcome.id is not None
    assert learning_outcome.subject_id == subject.id
    assert learning_outcome.code == "CP-01"
    assert (
        learning_outcome.description
        == "Peserta didik mampu memahami konsep."
    )
    assert learning_outcome.is_active is True


def test_learning_outcome_create_normalizes_code(
    db_session,
):
    subject = create_subject(db_session)

    service = LearningOutcomeService(
        db_session
    )

    data = LearningOutcomeCreate(
        subject_id=subject.id,
        code="  cp-01  ",
        description="Deskripsi CP.",
    )

    learning_outcome = service.create(data)

    assert learning_outcome.code == "CP-01"


def test_learning_outcome_create_trims_description(
    db_session,
):
    subject = create_subject(db_session)

    service = LearningOutcomeService(
        db_session
    )

    data = LearningOutcomeCreate(
        subject_id=subject.id,
        code="CP-01",
        description="  Deskripsi CP.  ",
    )

    learning_outcome = service.create(data)

    assert learning_outcome.description == "Deskripsi CP."


def test_learning_outcome_create_duplicate_code_same_subject(
    db_session,
):
    subject = create_subject(db_session)

    create_learning_outcome(
        db_session,
        subject_id=subject.id,
        code="CP-01",
    )

    service = LearningOutcomeService(
        db_session
    )

    data = LearningOutcomeCreate(
        subject_id=subject.id,
        code="CP-01",
        description="CP kedua.",
    )

    with pytest.raises(
        ValueError,
        match="Kode capaian pembelajaran sudah digunakan",
    ):
        service.create(data)


def test_learning_outcome_same_code_different_subject(
    db_session,
):
    first_subject = create_subject(
        db_session,
        code="MAT",
        name="Matematika",
    )

    second_subject = create_subject(
        db_session,
        code="IPA",
        name="IPA",
    )

    service = LearningOutcomeService(
        db_session
    )

    first = service.create(
        LearningOutcomeCreate(
            subject_id=first_subject.id,
            code="CP-01",
            description="CP Matematika.",
        )
    )

    second = service.create(
        LearningOutcomeCreate(
            subject_id=second_subject.id,
            code="CP-01",
            description="CP IPA.",
        )
    )

    assert first.code == "CP-01"
    assert second.code == "CP-01"
    assert first.subject_id != second.subject_id


def test_learning_outcome_create_subject_not_found(
    db_session,
):
    service = LearningOutcomeService(
        db_session
    )

    data = LearningOutcomeCreate(
        subject_id=99999,
        code="CP-01",
        description="Deskripsi CP.",
    )

    with pytest.raises(
        ValueError,
        match="Mata pelajaran tidak ditemukan",
    ):
        service.create(data)


def test_learning_outcome_create_inactive_subject(
    db_session,
):
    subject = create_subject(
        db_session,
        is_active=False,
    )

    service = LearningOutcomeService(
        db_session
    )

    data = LearningOutcomeCreate(
        subject_id=subject.id,
        code="CP-01",
        description="Deskripsi CP.",
    )

    with pytest.raises(
        ValueError,
        match="Mata pelajaran tidak aktif",
    ):
        service.create(data)


def test_learning_outcome_create_empty_code(
    db_session,
):
    subject = create_subject(db_session)

    service = LearningOutcomeService(
        db_session
    )

    data = LearningOutcomeCreate(
        subject_id=subject.id,
        code="   ",
        description="Deskripsi CP.",
    )

    with pytest.raises(
        ValueError,
        match="Kode capaian pembelajaran wajib diisi",
    ):
        service.create(data)


def test_learning_outcome_create_empty_description(
    db_session,
):
    subject = create_subject(db_session)

    service = LearningOutcomeService(
        db_session
    )

    data = LearningOutcomeCreate(
        subject_id=subject.id,
        code="CP-01",
        description="   ",
    )

    with pytest.raises(
        ValueError,
        match="Deskripsi capaian pembelajaran wajib diisi",
    ):
        service.create(data)


# ============================================================
# READ TESTS
# ============================================================


def test_learning_outcome_get_all(db_session):
    subject = create_subject(db_session)

    create_learning_outcome(
        db_session,
        subject_id=subject.id,
        code="CP-01",
    )

    create_learning_outcome(
        db_session,
        subject_id=subject.id,
        code="CP-02",
        description="CP kedua.",
    )

    service = LearningOutcomeService(
        db_session
    )

    learning_outcomes = service.get_all()

    assert len(learning_outcomes) == 2

    codes = [
        item.code
        for item in learning_outcomes
    ]

    assert "CP-01" in codes
    assert "CP-02" in codes


def test_learning_outcome_get_all_empty(
    db_session,
):
    service = LearningOutcomeService(
        db_session
    )

    learning_outcomes = service.get_all()

    assert learning_outcomes == []


def test_learning_outcome_get_by_id(
    db_session,
):
    subject = create_subject(db_session)

    learning_outcome = create_learning_outcome(
        db_session,
        subject_id=subject.id,
    )

    service = LearningOutcomeService(
        db_session
    )

    result = service.get_by_id(
        learning_outcome.id
    )

    assert result is not None
    assert result.id == learning_outcome.id
    assert result.subject_id == subject.id
    assert result.code == "CP-01"


def test_learning_outcome_get_by_id_not_found(
    db_session,
):
    service = LearningOutcomeService(
        db_session
    )

    result = service.get_by_id(99999)

    assert result is None


# ============================================================
# UPDATE TESTS
# ============================================================


def test_learning_outcome_update(db_session):
    subject = create_subject(db_session)

    learning_outcome = create_learning_outcome(
        db_session,
        subject_id=subject.id,
    )

    service = LearningOutcomeService(
        db_session
    )

    data = LearningOutcomeUpdate(
        subject_id=subject.id,
        code="CP-02",
        description="Deskripsi yang diperbarui.",
    )

    updated = service.update(
        learning_outcome.id,
        data,
    )

    assert updated.id == learning_outcome.id
    assert updated.subject_id == subject.id
    assert updated.code == "CP-02"
    assert (
        updated.description
        == "Deskripsi yang diperbarui."
    )


def test_learning_outcome_update_changes_subject(
    db_session,
):
    first_subject = create_subject(
        db_session,
        code="MAT",
        name="Matematika",
    )

    second_subject = create_subject(
        db_session,
        code="IPA",
        name="IPA",
    )

    learning_outcome = create_learning_outcome(
        db_session,
        subject_id=first_subject.id,
        code="CP-01",
    )

    service = LearningOutcomeService(
        db_session
    )

    data = LearningOutcomeUpdate(
        subject_id=second_subject.id,
        code="CP-01",
        description="Dipindahkan ke IPA.",
    )

    updated = service.update(
        learning_outcome.id,
        data,
    )

    assert updated.subject_id == second_subject.id
    assert updated.code == "CP-01"


def test_learning_outcome_update_normalizes_code(
    db_session,
):
    subject = create_subject(db_session)

    learning_outcome = create_learning_outcome(
        db_session,
        subject_id=subject.id,
    )

    service = LearningOutcomeService(
        db_session
    )

    data = LearningOutcomeUpdate(
        subject_id=subject.id,
        code="  cp-02  ",
        description="Updated.",
    )

    updated = service.update(
        learning_outcome.id,
        data,
    )

    assert updated.code == "CP-02"


def test_learning_outcome_update_duplicate_code(
    db_session,
):
    subject = create_subject(db_session)

    first = create_learning_outcome(
        db_session,
        subject_id=subject.id,
        code="CP-01",
    )

    second = create_learning_outcome(
        db_session,
        subject_id=subject.id,
        code="CP-02",
    )

    service = LearningOutcomeService(
        db_session
    )

    data = LearningOutcomeUpdate(
        subject_id=subject.id,
        code="CP-01",
        description="Updated.",
    )

    with pytest.raises(
        ValueError,
        match="Kode capaian pembelajaran sudah digunakan",
    ):
        service.update(
            second.id,
            data,
        )

    assert first.code == "CP-01"


def test_learning_outcome_update_not_found(
    db_session,
):
    subject = create_subject(db_session)

    service = LearningOutcomeService(
        db_session
    )

    data = LearningOutcomeUpdate(
        subject_id=subject.id,
        code="CP-01",
        description="Deskripsi.",
    )

    with pytest.raises(
        ValueError,
        match="Capaian pembelajaran tidak ditemukan",
    ):
        service.update(
            99999,
            data,
        )


def test_learning_outcome_update_subject_not_found(
    db_session,
):
    subject = create_subject(db_session)

    learning_outcome = create_learning_outcome(
        db_session,
        subject_id=subject.id,
    )

    service = LearningOutcomeService(
        db_session
    )

    data = LearningOutcomeUpdate(
        subject_id=99999,
        code="CP-02",
        description="Updated.",
    )

    with pytest.raises(
        ValueError,
        match="Mata pelajaran tidak ditemukan",
    ):
        service.update(
            learning_outcome.id,
            data,
        )


def test_learning_outcome_update_inactive_subject(
    db_session,
):
    active_subject = create_subject(
        db_session,
        code="MAT",
        name="Matematika",
    )

    inactive_subject = create_subject(
        db_session,
        code="IPA",
        name="IPA",
        is_active=False,
    )

    learning_outcome = create_learning_outcome(
        db_session,
        subject_id=active_subject.id,
    )

    service = LearningOutcomeService(
        db_session
    )

    data = LearningOutcomeUpdate(
        subject_id=inactive_subject.id,
        code="CP-02",
        description="Updated.",
    )

    with pytest.raises(
        ValueError,
        match="Mata pelajaran tidak aktif",
    ):
        service.update(
            learning_outcome.id,
            data,
        )


# ============================================================
# ACTIVE / INACTIVE TESTS
# ============================================================


def test_learning_outcome_set_active_false(
    db_session,
):
    subject = create_subject(db_session)

    learning_outcome = create_learning_outcome(
        db_session,
        subject_id=subject.id,
    )

    service = LearningOutcomeService(
        db_session
    )

    updated = service.set_active(
        learning_outcome.id,
        False,
    )

    assert updated.is_active is False


def test_learning_outcome_set_active_true(
    db_session,
):
    subject = create_subject(db_session)

    learning_outcome = create_learning_outcome(
        db_session,
        subject_id=subject.id,
        is_active=False,
    )

    service = LearningOutcomeService(
        db_session
    )

    updated = service.set_active(
        learning_outcome.id,
        True,
    )

    assert updated.is_active is True


def test_learning_outcome_set_active_not_found(
    db_session,
):
    service = LearningOutcomeService(
        db_session
    )

    with pytest.raises(
        ValueError,
        match="Capaian pembelajaran tidak ditemukan",
    ):
        service.set_active(
            99999,
            False,
        )


# ============================================================
# DELETE TESTS
# ============================================================


def test_learning_outcome_delete(
    db_session,
):
    subject = create_subject(db_session)

    learning_outcome = create_learning_outcome(
        db_session,
        subject_id=subject.id,
    )

    service = LearningOutcomeService(
        db_session
    )

    service.delete(
        learning_outcome.id
    )

    deleted = db_session.get(
        LearningOutcome,
        learning_outcome.id,
    )

    assert deleted is None


def test_learning_outcome_delete_not_found(
    db_session,
):
    service = LearningOutcomeService(
        db_session
    )

    with pytest.raises(
        ValueError,
        match="Capaian pembelajaran tidak ditemukan",
    ):
        service.delete(99999)


def test_subject_relationship_to_learning_outcomes(
    db_session,
):
    subject = create_subject(db_session)

    first = create_learning_outcome(
        db_session,
        subject_id=subject.id,
        code="CP-01",
    )

    second = create_learning_outcome(
        db_session,
        subject_id=subject.id,
        code="CP-02",
    )

    db_session.refresh(subject)

    assert len(subject.learning_outcomes) == 2

    ids = [
        item.id
        for item in subject.learning_outcomes
    ]

    assert first.id in ids
    assert second.id in ids