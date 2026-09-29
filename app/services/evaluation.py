from math import ceil

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    ClassRoom,
    Evaluation,
    EvaluationStatus,
    Subject,
    Teacher,
    User,
    UserRole,
)
from app.repositories.evaluation import (
    EvaluationRepository,
)
from app.schemas.evaluation import (
    EvaluationCreate,
    EvaluationUpdate,
)


class EvaluationService:
    DEFAULT_PER_PAGE = 10
    MAX_PER_PAGE = 100

    def __init__(self, db: Session):
        self.db = db
        self.repository = EvaluationRepository(db)

    def _validate_teacher(
        self,
        teacher_id: int,
    ) -> Teacher:
        teacher = self.db.get(
            Teacher,
            teacher_id,
        )

        if not teacher:
            raise ValueError(
                "Guru tidak ditemukan."
            )

        return teacher

    def _validate_subject(
        self,
        subject_id: int,
    ) -> Subject:
        subject = self.db.get(
            Subject,
            subject_id,
        )

        if not subject:
            raise ValueError(
                "Mata pelajaran tidak ditemukan."
            )

        if not subject.is_active:
            raise ValueError(
                "Mata pelajaran tidak aktif."
            )

        return subject

    def _validate_class(
        self,
        class_id: int,
    ) -> ClassRoom:
        class_room = self.db.get(
            ClassRoom,
            class_id,
        )

        if not class_room:
            raise ValueError(
                "Kelas tidak ditemukan."
            )

        if not class_room.is_active:
            raise ValueError(
                "Kelas tidak aktif."
            )

        return class_room

    def _normalize_create_data(
        self,
        data: EvaluationCreate,
    ) -> EvaluationCreate:
        name = data.name.strip()
        description = (
            data.description.strip()
            if data.description
            else None
        )
        semester = data.semester.strip().upper()
        academic_year = data.academic_year.strip()

        if not name:
            raise ValueError(
                "Nama evaluasi wajib diisi."
            )

        if not semester:
            raise ValueError(
                "Semester wajib diisi."
            )

        if not academic_year:
            raise ValueError(
                "Tahun ajaran wajib diisi."
            )

        return EvaluationCreate(
            teacher_id=data.teacher_id,
            subject_id=data.subject_id,
            class_id=data.class_id,
            name=name,
            description=description,
            semester=semester,
            academic_year=academic_year,
            status=data.status,
        )

    def _normalize_update_data(
        self,
        data: EvaluationUpdate,
    ) -> EvaluationUpdate:
        name = data.name.strip()
        description = (
            data.description.strip()
            if data.description
            else None
        )
        semester = data.semester.strip().upper()
        academic_year = data.academic_year.strip()

        if not name:
            raise ValueError(
                "Nama evaluasi wajib diisi."
            )

        if not semester:
            raise ValueError(
                "Semester wajib diisi."
            )

        if not academic_year:
            raise ValueError(
                "Tahun ajaran wajib diisi."
            )

        return EvaluationUpdate(
            subject_id=data.subject_id,
            class_id=data.class_id,
            name=name,
            description=description,
            semester=semester,
            academic_year=academic_year,
            status=data.status,
        )

    def create(
        self,
        data: EvaluationCreate,
        current_user: User,
    ) -> Evaluation:
        data = self._normalize_create_data(data)

        teacher = self._validate_teacher(
            data.teacher_id
        )

        if (
            current_user.role != UserRole.ADMIN
            and teacher.user_id != current_user.id
        ):
            raise ValueError(
                "Guru tidak memiliki akses ke data tersebut."
            )

        self._validate_subject(
            data.subject_id
        )

        self._validate_class(
            data.class_id
        )

        evaluation = Evaluation(
            teacher_id=data.teacher_id,
            subject_id=data.subject_id,
            class_id=data.class_id,
            name=data.name,
            description=data.description,
            semester=data.semester,
            academic_year=data.academic_year,
            status=data.status,
        )

        try:
            self.repository.create(
                evaluation
            )

            self.db.commit()
            self.db.refresh(
                evaluation
            )

        except IntegrityError:
            self.db.rollback()

            raise ValueError(
                "Evaluasi tidak dapat disimpan."
            )

        return evaluation

    def update(
        self,
        evaluation_id: int,
        data: EvaluationUpdate,
        current_user: User,
    ) -> Evaluation:
        evaluation = self.repository.get_by_id(
            evaluation_id
        )

        if not evaluation:
            raise ValueError(
                "Evaluasi tidak ditemukan."
            )

        self._ensure_access(
            evaluation,
            current_user,
        )

        data = self._normalize_update_data(data)

        self._validate_subject(
            data.subject_id
        )

        self._validate_class(
            data.class_id
        )

        evaluation.subject_id = data.subject_id
        evaluation.class_id = data.class_id
        evaluation.name = data.name
        evaluation.description = data.description
        evaluation.semester = data.semester
        evaluation.academic_year = data.academic_year
        evaluation.status = data.status

        try:
            self.db.commit()
            self.db.refresh(
                evaluation
            )

        except IntegrityError:
            self.db.rollback()

            raise ValueError(
                "Evaluasi tidak dapat diperbarui."
            )

        return evaluation

    def get_by_id(
        self,
        evaluation_id: int,
        current_user: User,
    ) -> Evaluation:
        evaluation = self.repository.get_by_id(
            evaluation_id
        )

        if not evaluation:
            raise ValueError(
                "Evaluasi tidak ditemukan."
            )

        self._ensure_access(
            evaluation,
            current_user,
        )

        return evaluation

    def paginate(
        self,
        *,
        current_user: User,
        search: str | None = None,
        subject_id: int | None = None,
        class_id: int | None = None,
        semester: str | None = None,
        academic_year: str | None = None,
        status: EvaluationStatus | None = None,
        page: int = 1,
        per_page: int = DEFAULT_PER_PAGE,
    ) -> dict:
        page = max(page, 1)

        per_page = max(
            1,
            min(
                per_page,
                self.MAX_PER_PAGE,
            ),
        )

        teacher_id = None

        if current_user.role == UserRole.GURU:
            if not current_user.teacher:
                raise ValueError(
                    "Akun guru belum memiliki data guru."
                )

            teacher_id = (
                current_user.teacher.id
            )

        evaluations, total = (
            self.repository.paginate(
                teacher_id=teacher_id,
                is_admin=(
                    current_user.role
                    == UserRole.ADMIN
                ),
                search=search,
                subject_id=subject_id,
                class_id=class_id,
                semester=semester,
                academic_year=academic_year,
                status=status,
                page=page,
                per_page=per_page,
            )
        )

        total_pages = (
            ceil(total / per_page)
            if total
            else 1
        )

        if page > total_pages:
            page = total_pages

            evaluations, total = (
                self.repository.paginate(
                    teacher_id=teacher_id,
                    is_admin=(
                        current_user.role
                        == UserRole.ADMIN
                    ),
                    search=search,
                    subject_id=subject_id,
                    class_id=class_id,
                    semester=semester,
                    academic_year=academic_year,
                    status=status,
                    page=page,
                    per_page=per_page,
                )
            )

            total_pages = (
                ceil(total / per_page)
                if total
                else 1
            )

        return {
            "items": evaluations,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_previous": page > 1,
            "has_next": page < total_pages,
        }

    def set_status(
        self,
        evaluation_id: int,
        status: EvaluationStatus,
        current_user: User,
    ) -> Evaluation:
        evaluation = self.repository.get_by_id(
            evaluation_id
        )

        if not evaluation:
            raise ValueError(
                "Evaluasi tidak ditemukan."
            )

        self._ensure_access(
            evaluation,
            current_user,
        )

        evaluation.status = status

        self.db.commit()
        self.db.refresh(
            evaluation
        )

        return evaluation

    def delete(
        self,
        evaluation_id: int,
        current_user: User,
    ) -> None:
        evaluation = self.repository.get_by_id(
            evaluation_id
        )

        if not evaluation:
            raise ValueError(
                "Evaluasi tidak ditemukan."
            )

        self._ensure_access(
            evaluation,
            current_user,
        )

        self.repository.delete(
            evaluation
        )

        try:
            self.db.commit()

        except IntegrityError:
            self.db.rollback()

            raise ValueError(
                "Evaluasi tidak dapat dihapus "
                "karena masih digunakan oleh data lain."
            )

    def _ensure_access(
        self,
        evaluation: Evaluation,
        current_user: User,
    ) -> None:
        if current_user.role == UserRole.ADMIN:
            return

        if not current_user.teacher:
            raise ValueError(
                "Akun guru belum memiliki data guru."
            )

        if (
            evaluation.teacher_id
            != current_user.teacher.id
        ):
            raise ValueError(
                "Kamu tidak memiliki akses "
                "ke evaluasi tersebut."
            )