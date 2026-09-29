from typing import Optional
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from app.models import Subject


class SubjectRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> list[Subject]:
        statement = select(Subject)

        # 1. Filter Pencarian Teks (Cari berdasarkan kode, nama, atau deskripsi)
        if search:
            search_fmt = f"%{search.strip()}%"
            statement = statement.where(
                or_(
                    Subject.code.ilike(search_fmt),
                    Subject.name.ilike(search_fmt),
                    Subject.description.ilike(search_fmt),
                )
            )

        # 2. Filter Status Aktif (is_active: True / False)
        if is_active is not None:
            statement = statement.where(Subject.is_active == is_active)

        # Urutkan secara alfabetis berdasarkan nama mata pelajaran
        statement = statement.order_by(Subject.name.asc())

        return list(self.db.scalars(statement).all())

    def get_by_id(
        self,
        subject_id: int,
    ) -> Subject | None:
        return self.db.get(
            Subject,
            subject_id,
        )

    def get_by_code(
        self,
        code: str,
    ) -> Subject | None:
        statement = select(Subject).where(
            Subject.code == code
        )

        return self.db.scalar(statement)

    def get_by_name(
        self,
        name: str,
    ) -> Subject | None:
        statement = select(Subject).where(
            Subject.name == name
        )

        return self.db.scalar(statement)

    def create(
        self,
        subject: Subject,
    ) -> Subject:
        self.db.add(subject)
        self.db.flush()
        self.db.refresh(subject)

        return subject

    def delete(
        self,
        subject: Subject,
    ) -> None:
        self.db.delete(subject)