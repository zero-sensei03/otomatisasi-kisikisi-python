from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import LearningOutcome, Subject
from app.repositories.learning_outcome import (
    LearningOutcomeRepository,
)
from app.schemas.learning_outcome import (
    LearningOutcomeCreate,
    LearningOutcomeUpdate,
)


class LearningOutcomeService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = LearningOutcomeRepository(db)

    def get_all(self) -> list[LearningOutcome]:
        return self.repository.get_all()

    def get_by_id(
        self,
        learning_outcome_id: int,
    ) -> LearningOutcome | None:
        return self.repository.get_by_id(
            learning_outcome_id
        )

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

    def create(
        self,
        data: LearningOutcomeCreate,
    ) -> LearningOutcome:
        code = data.code.strip().upper()
        description = data.description.strip()

        if not code:
            raise ValueError(
                "Kode capaian pembelajaran wajib diisi."
            )

        if not description:
            raise ValueError(
                "Deskripsi capaian pembelajaran wajib diisi."
            )

        self._validate_subject(
            data.subject_id
        )

        existing = (
            self.repository.get_by_subject_and_code(
                data.subject_id,
                code,
            )
        )

        if existing:
            raise ValueError(
                "Kode capaian pembelajaran sudah digunakan "
                "pada mata pelajaran tersebut."
            )

        learning_outcome = LearningOutcome(
            subject_id=data.subject_id,
            code=code,
            description=description,
            is_active=True,
        )

        try:
            self.repository.create(
                learning_outcome
            )

            self.db.commit()
            self.db.refresh(
                learning_outcome
            )

        except IntegrityError:
            self.db.rollback()

            raise ValueError(
                "Kode capaian pembelajaran sudah digunakan."
            )

        return learning_outcome

    def update(
        self,
        learning_outcome_id: int,
        data: LearningOutcomeUpdate,
    ) -> LearningOutcome:
        learning_outcome = self.repository.get_by_id(
            learning_outcome_id
        )

        if not learning_outcome:
            raise ValueError(
                "Capaian pembelajaran tidak ditemukan."
            )

        code = data.code.strip().upper()
        description = data.description.strip()

        if not code:
            raise ValueError(
                "Kode capaian pembelajaran wajib diisi."
            )

        if not description:
            raise ValueError(
                "Deskripsi capaian pembelajaran wajib diisi."
            )

        self._validate_subject(
            data.subject_id
        )

        existing = (
            self.repository.get_by_subject_and_code(
                data.subject_id,
                code,
            )
        )

        if (
            existing
            and existing.id != learning_outcome.id
        ):
            raise ValueError(
                "Kode capaian pembelajaran sudah digunakan "
                "pada mata pelajaran tersebut."
            )

        learning_outcome.subject_id = (
            data.subject_id
        )
        learning_outcome.code = code
        learning_outcome.description = description

        try:
            self.db.commit()
            self.db.refresh(
                learning_outcome
            )

        except IntegrityError:
            self.db.rollback()

            raise ValueError(
                "Kode capaian pembelajaran sudah digunakan."
            )

        return learning_outcome

    def set_active(
        self,
        learning_outcome_id: int,
        is_active: bool,
    ) -> LearningOutcome:
        learning_outcome = self.repository.get_by_id(
            learning_outcome_id
        )

        if not learning_outcome:
            raise ValueError(
                "Capaian pembelajaran tidak ditemukan."
            )

        learning_outcome.is_active = is_active

        self.db.commit()
        self.db.refresh(
            learning_outcome
        )

        return learning_outcome

    def delete(
        self,
        learning_outcome_id: int,
    ) -> None:
        learning_outcome = self.repository.get_by_id(
            learning_outcome_id
        )

        if not learning_outcome:
            raise ValueError(
                "Capaian pembelajaran tidak ditemukan."
            )

        self.repository.delete(
            learning_outcome
        )

        try:
            self.db.commit()

        except IntegrityError:
            self.db.rollback()

            raise ValueError(
                "Capaian pembelajaran tidak dapat dihapus "
                "karena masih digunakan oleh data lain."
            )