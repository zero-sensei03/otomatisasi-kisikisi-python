from typing import Optional
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from app.models import LearningOutcome


class LearningOutcomeRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self,
        search: Optional[str] = None,
        subject_id: Optional[int] = None,
        is_active: Optional[bool] = None,
    ) -> list[LearningOutcome]:
        statement = select(LearningOutcome)

        # 1. Filter Pencarian Teks (Cari berdasarkan kode CP/TP atau deskripsinya)
        if search:
            search_fmt = f"%{search.strip()}%"
            statement = statement.where(
                or_(
                    LearningOutcome.code.ilike(search_fmt),
                    LearningOutcome.description.ilike(search_fmt),
                )
            )

        # 2. Filter Spesifik berdasarkan Mata Pelajaran (subject_id)
        if subject_id is not None:
            statement = statement.where(LearningOutcome.subject_id == subject_id)

        # 3. Filter Berdasarkan Status Aktif (is_active: True / False)
        if is_active is not None:
            statement = statement.where(LearningOutcome.is_active == is_active)

        # Urutkan berdasarkan subject_id dan kode CP secara ascending
        statement = statement.order_by(
            LearningOutcome.subject_id.asc(),
            LearningOutcome.code.asc(),
        )

        return list(self.db.scalars(statement).all())

    def get_by_id(
        self,
        learning_outcome_id: int,
    ) -> LearningOutcome | None:
        return self.db.get(
            LearningOutcome,
            learning_outcome_id,
        )

    def get_by_subject_and_code(
        self,
        subject_id: int,
        code: str,
    ) -> LearningOutcome | None:
        statement = select(LearningOutcome).where(
            LearningOutcome.subject_id == subject_id,
            LearningOutcome.code == code,
        )

        return self.db.scalar(statement)

    def create(
        self,
        learning_outcome: LearningOutcome,
    ) -> LearningOutcome:
        self.db.add(learning_outcome)
        self.db.flush()
        self.db.refresh(learning_outcome)

        return learning_outcome

    def delete(
        self,
        learning_outcome: LearningOutcome,
    ) -> None:
        self.db.delete(learning_outcome)