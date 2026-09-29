from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.security import hash_password
from app.models import (
    ClassRoom,
    Evaluation,
    EvaluationStatus,
    Subject,
    Teacher,
    User,
    UserRole,
)
from app.schemas.evaluation import (
    EvaluationCreate,
    EvaluationUpdate,
)
from app.services.evaluation import (
    EvaluationService,
)


engine = create_engine(
    "sqlite://",
    connect_args={
        "check_same_thread": False,
    },
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def setup_database():
    Base.metadata.create_all(
        bind=engine
    )


def teardown_database():
    Base.metadata.drop_all(
        bind=engine
    )


def create_test_data(
    db: Session,
):
    admin = User(
        username="admin",
        email="admin@example.com",
        password_hash=hash_password(
            "password"
        ),
        full_name="Administrator",
        role=UserRole.ADMIN,
        is_active=True,
    )

    guru_user = User(
        username="guru",
        email="guru@example.com",
        password_hash=hash_password(
            "password"
        ),
        full_name="Guru Test",
        role=UserRole.GURU,
        is_active=True,
    )

    guru_user_2 = User(
        username="guru2",
        email="guru2@example.com",
        password_hash=hash_password(
            "password"
        ),
        full_name="Guru Test 2",
        role=UserRole.GURU,
        is_active=True,
    )

    db.add_all(
        [
            admin,
            guru_user,
            guru_user_2,
        ]
    )

    db.flush()

    teacher = Teacher(
        user_id=guru_user.id,
        employee_number="G001",
    )

    teacher_2 = Teacher(
        user_id=guru_user_2.id,
        employee_number="G002",
    )

    subject = Subject(
        code="MTK",
        name="Matematika",
        description=None,
        is_active=True,
    )

    subject_2 = Subject(
        code="BIN",
        name="Bahasa Indonesia",
        description=None,
        is_active=True,
    )

    class_room = ClassRoom(
        name="VII-A",
        grade_level="VII",
        description=None,
        is_active=True,
    )

    class_room_2 = ClassRoom(
        name="VII-B",
        grade_level="VII",
        description=None,
        is_active=True,
    )

    db.add_all(
        [
            teacher,
            teacher_2,
            subject,
            subject_2,
            class_room,
            class_room_2,
        ]
    )

    db.commit()

    return {
        "admin": admin,
        "guru": guru_user,
        "guru2": guru_user_2,
        "teacher": teacher,
        "teacher2": teacher_2,
        "subject": subject,
        "subject2": subject_2,
        "class_room": class_room,
        "class_room2": class_room_2,
    }


def test_create_evaluation():
    setup_database()

    try:
        with TestingSessionLocal() as db:
            data = create_test_data(db)

            service = EvaluationService(db)

            evaluation = service.create(
                EvaluationCreate(
                    teacher_id=data["teacher"].id,
                    subject_id=data["subject"].id,
                    class_id=data["class_room"].id,
                    name="Penilaian Harian",
                    description="Bab 1",
                    semester="ganjil",
                    academic_year="2026/2027",
                ),
                current_user=data["guru"],
            )

            assert evaluation.id is not None
            assert evaluation.name == "Penilaian Harian"
            assert evaluation.semester == "GANJIL"
            assert evaluation.status == (
                EvaluationStatus.DRAFT
            )

    finally:
        teardown_database()


def test_create_evaluation_normalizes_values():
    setup_database()

    try:
        with TestingSessionLocal() as db:
            data = create_test_data(db)

            service = EvaluationService(db)

            evaluation = service.create(
                EvaluationCreate(
                    teacher_id=data["teacher"].id,
                    subject_id=data["subject"].id,
                    class_id=data["class_room"].id,
                    name="  Penilaian Harian  ",
                    description="  Bab 1  ",
                    semester="  ganjil  ",
                    academic_year=" 2026/2027 ",
                ),
                current_user=data["guru"],
            )

            assert evaluation.name == (
                "Penilaian Harian"
            )

            assert evaluation.description == "Bab 1"
            assert evaluation.semester == "GANJIL"
            assert evaluation.academic_year == (
                "2026/2027"
            )

    finally:
        teardown_database()


def test_guru_can_only_create_for_self():
    setup_database()

    try:
        with TestingSessionLocal() as db:
            data = create_test_data(db)

            service = EvaluationService(db)

            try:
                service.create(
                    EvaluationCreate(
                        teacher_id=data["teacher2"].id,
                        subject_id=data["subject"].id,
                        class_id=data["class_room"].id,
                        name="Evaluasi Guru 2",
                        description=None,
                        semester="GANJIL",
                        academic_year="2026/2027",
                    ),
                    current_user=data["guru"],
                )

                assert False

            except ValueError as exc:
                assert (
                    str(exc)
                    == "Guru tidak memiliki akses "
                    "ke data tersebut."
                )

    finally:
        teardown_database()


def test_admin_can_create_for_any_teacher():
    setup_database()

    try:
        with TestingSessionLocal() as db:
            data = create_test_data(db)

            service = EvaluationService(db)

            evaluation = service.create(
                EvaluationCreate(
                    teacher_id=data["teacher2"].id,
                    subject_id=data["subject"].id,
                    class_id=data["class_room"].id,
                    name="Evaluasi Guru 2",
                    description=None,
                    semester="GENAP",
                    academic_year="2026/2027",
                ),
                current_user=data["admin"],
            )

            assert evaluation.teacher_id == (
                data["teacher2"].id
            )

    finally:
        teardown_database()


def test_inactive_subject_cannot_be_used():
    setup_database()

    try:
        with TestingSessionLocal() as db:
            data = create_test_data(db)

            data["subject"].is_active = False
            db.commit()

            service = EvaluationService(db)

            try:
                service.create(
                    EvaluationCreate(
                        teacher_id=data["teacher"].id,
                        subject_id=data["subject"].id,
                        class_id=data["class_room"].id,
                        name="Evaluasi",
                        description=None,
                        semester="GANJIL",
                        academic_year="2026/2027",
                    ),
                    current_user=data["guru"],
                )

                assert False

            except ValueError as exc:
                assert (
                    str(exc)
                    == "Mata pelajaran tidak aktif."
                )

    finally:
        teardown_database()


def test_inactive_class_cannot_be_used():
    setup_database()

    try:
        with TestingSessionLocal() as db:
            data = create_test_data(db)

            data["class_room"].is_active = False
            db.commit()

            service = EvaluationService(db)

            try:
                service.create(
                    EvaluationCreate(
                        teacher_id=data["teacher"].id,
                        subject_id=data["subject"].id,
                        class_id=data["class_room"].id,
                        name="Evaluasi",
                        description=None,
                        semester="GANJIL",
                        academic_year="2026/2027",
                    ),
                    current_user=data["guru"],
                )

                assert False

            except ValueError as exc:
                assert (
                    str(exc)
                    == "Kelas tidak aktif."
                )

    finally:
        teardown_database()


def test_update_evaluation():
    setup_database()

    try:
        with TestingSessionLocal() as db:
            data = create_test_data(db)

            service = EvaluationService(db)

            evaluation = service.create(
                EvaluationCreate(
                    teacher_id=data["teacher"].id,
                    subject_id=data["subject"].id,
                    class_id=data["class_room"].id,
                    name="Evaluasi Lama",
                    description=None,
                    semester="GANJIL",
                    academic_year="2026/2027",
                ),
                current_user=data["guru"],
            )

            updated = service.update(
                evaluation.id,
                EvaluationUpdate(
                    subject_id=data["subject2"].id,
                    class_id=data["class_room2"].id,
                    name="Evaluasi Baru",
                    description="Deskripsi",
                    semester="GENAP",
                    academic_year="2027/2028",
                    status=EvaluationStatus.READY,
                ),
                current_user=data["guru"],
            )

            assert updated.name == "Evaluasi Baru"
            assert updated.subject_id == (
                data["subject2"].id
            )
            assert updated.class_id == (
                data["class_room2"].id
            )
            assert updated.semester == "GENAP"
            assert updated.academic_year == (
                "2027/2028"
            )
            assert updated.status == (
                EvaluationStatus.READY
            )

    finally:
        teardown_database()


def test_guru_cannot_access_other_teacher_evaluation():
    setup_database()

    try:
        with TestingSessionLocal() as db:
            data = create_test_data(db)

            service = EvaluationService(db)

            evaluation = service.create(
                EvaluationCreate(
                    teacher_id=data["teacher2"].id,
                    subject_id=data["subject"].id,
                    class_id=data["class_room"].id,
                    name="Evaluasi Guru 2",
                    description=None,
                    semester="GANJIL",
                    academic_year="2026/2027",
                ),
                current_user=data["admin"],
            )

            try:
                service.get_by_id(
                    evaluation.id,
                    current_user=data["guru"],
                )

                assert False

            except ValueError as exc:
                assert (
                    str(exc)
                    == "Kamu tidak memiliki akses "
                    "ke evaluasi tersebut."
                )

    finally:
        teardown_database()


def test_guru_pagination_only_returns_own_evaluations():
    setup_database()

    try:
        with TestingSessionLocal() as db:
            data = create_test_data(db)

            service = EvaluationService(db)

            for index in range(15):
                service.create(
                    EvaluationCreate(
                        teacher_id=data["teacher"].id,
                        subject_id=data["subject"].id,
                        class_id=data["class_room"].id,
                        name=f"Evaluasi {index + 1}",
                        description=None,
                        semester="GANJIL",
                        academic_year="2026/2027",
                    ),
                    current_user=data["guru"],
                )

            service.create(
                EvaluationCreate(
                    teacher_id=data["teacher2"].id,
                    subject_id=data["subject"].id,
                    class_id=data["class_room"].id,
                    name="Evaluasi Guru 2",
                    description=None,
                    semester="GANJIL",
                    academic_year="2026/2027",
                ),
                current_user=data["admin"],
            )

            result = service.paginate(
                current_user=data["guru"],
                page=1,
                per_page=10,
            )

            assert result["total"] == 15
            assert len(result["items"]) == 10
            assert result["total_pages"] == 2

    finally:
        teardown_database()


def test_admin_pagination_returns_all_evaluations():
    setup_database()

    try:
        with TestingSessionLocal() as db:
            data = create_test_data(db)

            service = EvaluationService(db)

            for index in range(12):
                service.create(
                    EvaluationCreate(
                        teacher_id=data["teacher"].id,
                        subject_id=data["subject"].id,
                        class_id=data["class_room"].id,
                        name=f"Evaluasi {index + 1}",
                        description=None,
                        semester="GANJIL",
                        academic_year="2026/2027",
                    ),
                    current_user=data["guru"],
                )

            service.create(
                EvaluationCreate(
                    teacher_id=data["teacher2"].id,
                    subject_id=data["subject"].id,
                    class_id=data["class_room"].id,
                    name="Evaluasi Guru 2",
                    description=None,
                    semester="GENAP",
                    academic_year="2027/2028",
                ),
                current_user=data["admin"],
            )

            result = service.paginate(
                current_user=data["admin"],
                page=1,
                per_page=10,
            )

            assert result["total"] == 13
            assert len(result["items"]) == 10
            assert result["total_pages"] == 2

    finally:
        teardown_database()


def test_filter_by_subject():
    setup_database()

    try:
        with TestingSessionLocal() as db:
            data = create_test_data(db)

            service = EvaluationService(db)

            service.create(
                EvaluationCreate(
                    teacher_id=data["teacher"].id,
                    subject_id=data["subject"].id,
                    class_id=data["class_room"].id,
                    name="Matematika",
                    description=None,
                    semester="GANJIL",
                    academic_year="2026/2027",
                ),
                current_user=data["guru"],
            )

            service.create(
                EvaluationCreate(
                    teacher_id=data["teacher"].id,
                    subject_id=data["subject2"].id,
                    class_id=data["class_room"].id,
                    name="Bahasa Indonesia",
                    description=None,
                    semester="GANJIL",
                    academic_year="2026/2027",
                ),
                current_user=data["guru"],
            )

            result = service.paginate(
                current_user=data["guru"],
                subject_id=data["subject"].id,
                page=1,
                per_page=10,
            )

            assert result["total"] == 1
            assert (
                result["items"][0].subject_id
                == data["subject"].id
            )

    finally:
        teardown_database()


def test_filter_by_class():
    setup_database()

    try:
        with TestingSessionLocal() as db:
            data = create_test_data(db)

            service = EvaluationService(db)

            service.create(
                EvaluationCreate(
                    teacher_id=data["teacher"].id,
                    subject_id=data["subject"].id,
                    class_id=data["class_room"].id,
                    name="Kelas A",
                    description=None,
                    semester="GANJIL",
                    academic_year="2026/2027",
                ),
                current_user=data["guru"],
            )

            service.create(
                EvaluationCreate(
                    teacher_id=data["teacher"].id,
                    subject_id=data["subject"].id,
                    class_id=data["class_room2"].id,
                    name="Kelas B",
                    description=None,
                    semester="GANJIL",
                    academic_year="2026/2027",
                ),
                current_user=data["guru"],
            )

            result = service.paginate(
                current_user=data["guru"],
                class_id=data["class_room2"].id,
                page=1,
                per_page=10,
            )

            assert result["total"] == 1
            assert (
                result["items"][0].class_id
                == data["class_room2"].id
            )

    finally:
        teardown_database()


def test_filter_by_semester():
    setup_database()

    try:
        with TestingSessionLocal() as db:
            data = create_test_data(db)

            service = EvaluationService(db)

            service.create(
                EvaluationCreate(
                    teacher_id=data["teacher"].id,
                    subject_id=data["subject"].id,
                    class_id=data["class_room"].id,
                    name="Ganjil",
                    description=None,
                    semester="GANJIL",
                    academic_year="2026/2027",
                ),
                current_user=data["guru"],
            )

            service.create(
                EvaluationCreate(
                    teacher_id=data["teacher"].id,
                    subject_id=data["subject"].id,
                    class_id=data["class_room"].id,
                    name="Genap",
                    description=None,
                    semester="GENAP",
                    academic_year="2026/2027",
                ),
                current_user=data["guru"],
            )

            result = service.paginate(
                current_user=data["guru"],
                semester="GENAP",
                page=1,
                per_page=10,
            )

            assert result["total"] == 1
            assert (
                result["items"][0].semester
                == "GENAP"
            )

    finally:
        teardown_database()


def test_filter_by_academic_year():
    setup_database()

    try:
        with TestingSessionLocal() as db:
            data = create_test_data(db)

            service = EvaluationService(db)

            service.create(
                EvaluationCreate(
                    teacher_id=data["teacher"].id,
                    subject_id=data["subject"].id,
                    class_id=data["class_room"].id,
                    name="Tahun 2026",
                    description=None,
                    semester="GANJIL",
                    academic_year="2026/2027",
                ),
                current_user=data["guru"],
            )

            service.create(
                EvaluationCreate(
                    teacher_id=data["teacher"].id,
                    subject_id=data["subject"].id,
                    class_id=data["class_room"].id,
                    name="Tahun 2027",
                    description=None,
                    semester="GANJIL",
                    academic_year="2027/2028",
                ),
                current_user=data["guru"],
            )

            result = service.paginate(
                current_user=data["guru"],
                academic_year="2027/2028",
                page=1,
                per_page=10,
            )

            assert result["total"] == 1
            assert (
                result["items"][0].academic_year
                == "2027/2028"
            )

    finally:
        teardown_database()


def test_filter_by_status():
    setup_database()

    try:
        with TestingSessionLocal() as db:
            data = create_test_data(db)

            service = EvaluationService(db)

            service.create(
                EvaluationCreate(
                    teacher_id=data["teacher"].id,
                    subject_id=data["subject"].id,
                    class_id=data["class_room"].id,
                    name="Draft",
                    description=None,
                    semester="GANJIL",
                    academic_year="2026/2027",
                    status=EvaluationStatus.DRAFT,
                ),
                current_user=data["guru"],
            )

            service.create(
                EvaluationCreate(
                    teacher_id=data["teacher"].id,
                    subject_id=data["subject"].id,
                    class_id=data["class_room"].id,
                    name="Ready",
                    description=None,
                    semester="GANJIL",
                    academic_year="2026/2027",
                    status=EvaluationStatus.READY,
                ),
                current_user=data["guru"],
            )

            result = service.paginate(
                current_user=data["guru"],
                status=EvaluationStatus.READY,
                page=1,
                per_page=10,
            )

            assert result["total"] == 1
            assert (
                result["items"][0].status
                == EvaluationStatus.READY
            )

    finally:
        teardown_database()


def test_search_filter():
    setup_database()

    try:
        with TestingSessionLocal() as db:
            data = create_test_data(db)

            service = EvaluationService(db)

            service.create(
                EvaluationCreate(
                    teacher_id=data["teacher"].id,
                    subject_id=data["subject"].id,
                    class_id=data["class_room"].id,
                    name="Penilaian Matematika",
                    description="Persamaan Linear",
                    semester="GANJIL",
                    academic_year="2026/2027",
                ),
                current_user=data["guru"],
            )

            service.create(
                EvaluationCreate(
                    teacher_id=data["teacher"].id,
                    subject_id=data["subject"].id,
                    class_id=data["class_room"].id,
                    name="Penilaian Geometri",
                    description="Bangun ruang",
                    semester="GANJIL",
                    academic_year="2026/2027",
                ),
                current_user=data["guru"],
            )

            result = service.paginate(
                current_user=data["guru"],
                search="Persamaan",
                page=1,
                per_page=10,
            )

            assert result["total"] == 1
            assert (
                result["items"][0].name
                == "Penilaian Matematika"
            )

    finally:
        teardown_database()


def test_set_status():
    setup_database()

    try:
        with TestingSessionLocal() as db:
            data = create_test_data(db)

            service = EvaluationService(db)

            evaluation = service.create(
                EvaluationCreate(
                    teacher_id=data["teacher"].id,
                    subject_id=data["subject"].id,
                    class_id=data["class_room"].id,
                    name="Evaluasi",
                    description=None,
                    semester="GANJIL",
                    academic_year="2026/2027",
                ),
                current_user=data["guru"],
            )

            updated = service.set_status(
                evaluation.id,
                EvaluationStatus.READY,
                current_user=data["guru"],
            )

            assert updated.status == (
                EvaluationStatus.READY
            )

    finally:
        teardown_database()


def test_delete_evaluation():
    setup_database()

    try:
        with TestingSessionLocal() as db:
            data = create_test_data(db)

            service = EvaluationService(db)

            evaluation = service.create(
                EvaluationCreate(
                    teacher_id=data["teacher"].id,
                    subject_id=data["subject"].id,
                    class_id=data["class_room"].id,
                    name="Evaluasi",
                    description=None,
                    semester="GANJIL",
                    academic_year="2026/2027",
                ),
                current_user=data["guru"],
            )

            service.delete(
                evaluation.id,
                current_user=data["guru"],
            )

            assert (
                service.repository.get_by_id(
                    evaluation.id
                )
                is None
            )

    finally:
        teardown_database()