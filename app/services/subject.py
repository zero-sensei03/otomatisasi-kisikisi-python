from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Subject
from app.repositories.subject import SubjectRepository
from app.schemas.subject import SubjectCreate, SubjectUpdate


class SubjectService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = SubjectRepository(db)

    def get_all(self) -> list[Subject]:
        return self.repository.get_all()

    def get_by_id(
        self,
        subject_id: int,
    ) -> Subject | None:
        return self.repository.get_by_id(subject_id)

    def create(
        self,
        data: SubjectCreate,
    ) -> Subject:
        code = data.code.strip().upper()
        name = data.name.strip()
        description = (
            data.description.strip()
            if data.description
            else None
        )

        if not code:
            raise ValueError(
                "Kode mata pelajaran wajib diisi."
            )

        if not name:
            raise ValueError(
                "Nama mata pelajaran wajib diisi."
            )

        existing_code = self.repository.get_by_code(code)

        if existing_code:
            raise ValueError(
                "Kode mata pelajaran sudah digunakan."
            )

        existing_name = self.repository.get_by_name(name)

        if existing_name:
            raise ValueError(
                "Nama mata pelajaran sudah digunakan."
            )

        subject = Subject(
            code=code,
            name=name,
            description=description,
            is_active=True,
        )

        try:
            self.repository.create(subject)
            self.db.commit()
            self.db.refresh(subject)

        except IntegrityError:
            self.db.rollback()

            raise ValueError(
                "Data mata pelajaran sudah digunakan."
            )

        return subject

    def update(
        self,
        subject_id: int,
        data: SubjectUpdate,
    ) -> Subject:
        subject = self.repository.get_by_id(subject_id)

        if not subject:
            raise ValueError(
                "Mata pelajaran tidak ditemukan."
            )

        code = data.code.strip().upper()
        name = data.name.strip()
        description = (
            data.description.strip()
            if data.description
            else None
        )

        if not code:
            raise ValueError(
                "Kode mata pelajaran wajib diisi."
            )

        if not name:
            raise ValueError(
                "Nama mata pelajaran wajib diisi."
            )

        existing_code = self.repository.get_by_code(code)

        if (
            existing_code
            and existing_code.id != subject.id
        ):
            raise ValueError(
                "Kode mata pelajaran sudah digunakan."
            )

        existing_name = self.repository.get_by_name(name)

        if (
            existing_name
            and existing_name.id != subject.id
        ):
            raise ValueError(
                "Nama mata pelajaran sudah digunakan."
            )

        subject.code = code
        subject.name = name
        subject.description = description

        try:
            self.db.commit()
            self.db.refresh(subject)

        except IntegrityError:
            self.db.rollback()

            raise ValueError(
                "Data mata pelajaran sudah digunakan."
            )

        return subject

    def set_active(
        self,
        subject_id: int,
        is_active: bool,
    ) -> Subject:
        subject = self.repository.get_by_id(subject_id)

        if not subject:
            raise ValueError(
                "Mata pelajaran tidak ditemukan."
            )

        subject.is_active = is_active

        self.db.commit()
        self.db.refresh(subject)

        return subject

    def delete(
        self,
        subject_id: int,
    ) -> None:
        subject = self.repository.get_by_id(subject_id)

        if not subject:
            raise ValueError(
                "Mata pelajaran tidak ditemukan."
            )

        self.repository.delete(subject)

        try:
            self.db.commit()

        except IntegrityError:
            self.db.rollback()

            raise ValueError(
                "Mata pelajaran tidak dapat dihapus "
                "karena masih digunakan oleh data lain."
            )