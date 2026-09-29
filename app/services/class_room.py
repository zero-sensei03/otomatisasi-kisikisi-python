from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import ClassRoom
from app.repositories.class_room import ClassRoomRepository
from app.schemas.class_room import (
    ClassRoomCreate,
    ClassRoomUpdate,
)


class ClassRoomService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ClassRoomRepository(db)

    def get_all(self) -> list[ClassRoom]:
        return self.repository.get_all()

    def get_by_id(
        self,
        class_room_id: int,
    ) -> ClassRoom | None:
        return self.repository.get_by_id(
            class_room_id
        )

    def create(
        self,
        data: ClassRoomCreate,
    ) -> ClassRoom:
        name = data.name.strip()
        grade_level = data.grade_level.strip()
        description = (
            data.description.strip()
            if data.description
            else None
        )

        if not name:
            raise ValueError(
                "Nama kelas wajib diisi."
            )

        if not grade_level:
            raise ValueError(
                "Tingkat kelas wajib diisi."
            )

        existing_name = self.repository.get_by_name(
            name
        )

        if existing_name:
            raise ValueError(
                "Nama kelas sudah digunakan."
            )

        class_room = ClassRoom(
            name=name,
            grade_level=grade_level,
            description=description,
            is_active=True,
        )

        try:
            self.repository.create(class_room)
            self.db.commit()
            self.db.refresh(class_room)

        except IntegrityError:
            self.db.rollback()

            raise ValueError(
                "Nama kelas sudah digunakan."
            )

        return class_room

    def update(
        self,
        class_room_id: int,
        data: ClassRoomUpdate,
    ) -> ClassRoom:
        class_room = self.repository.get_by_id(
            class_room_id
        )

        if not class_room:
            raise ValueError(
                "Kelas tidak ditemukan."
            )

        name = data.name.strip()
        grade_level = data.grade_level.strip()
        description = (
            data.description.strip()
            if data.description
            else None
        )

        if not name:
            raise ValueError(
                "Nama kelas wajib diisi."
            )

        if not grade_level:
            raise ValueError(
                "Tingkat kelas wajib diisi."
            )

        existing_name = self.repository.get_by_name(
            name
        )

        if (
            existing_name
            and existing_name.id != class_room.id
        ):
            raise ValueError(
                "Nama kelas sudah digunakan."
            )

        class_room.name = name
        class_room.grade_level = grade_level
        class_room.description = description

        try:
            self.db.commit()
            self.db.refresh(class_room)

        except IntegrityError:
            self.db.rollback()

            raise ValueError(
                "Nama kelas sudah digunakan."
            )

        return class_room

    def set_active(
        self,
        class_room_id: int,
        is_active: bool,
    ) -> ClassRoom:
        class_room = self.repository.get_by_id(
            class_room_id
        )

        if not class_room:
            raise ValueError(
                "Kelas tidak ditemukan."
            )

        class_room.is_active = is_active

        self.db.commit()
        self.db.refresh(class_room)

        return class_room

    def delete(
        self,
        class_room_id: int,
    ) -> None:
        class_room = self.repository.get_by_id(
            class_room_id
        )

        if not class_room:
            raise ValueError(
                "Kelas tidak ditemukan."
            )

        self.repository.delete(class_room)

        try:
            self.db.commit()

        except IntegrityError:
            self.db.rollback()

            raise ValueError(
                "Kelas tidak dapat dihapus "
                "karena masih digunakan oleh data lain."
            )