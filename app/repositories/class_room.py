from typing import Optional
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from app.models import ClassRoom


class ClassRoomRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self,
        search: Optional[str] = None,
        grade_level: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> list[ClassRoom]:
        statement = select(ClassRoom)

        # 1. Filter Pencarian Teks (Cari berdasarkan nama, grade_level, atau deskripsi)
        if search:
            search_fmt = f"%{search.strip()}%"
            statement = statement.where(
                or_(
                    ClassRoom.name.ilike(search_fmt),
                    ClassRoom.grade_level.ilike(search_fmt),
                    ClassRoom.description.ilike(search_fmt),
                )
            )

        # 2. Filter Spesifik berdasarkan Grade Level (Misal: "X", "XI", "10", dll.)
        if grade_level:
            statement = statement.where(ClassRoom.grade_level == grade_level)

        # 3. Filter Berdasarkan Status Aktif (is_active: True / False)
        if is_active is not None:
            statement = statement.where(ClassRoom.is_active == is_active)

        # Pengurutan bawaan
        statement = statement.order_by(
            ClassRoom.grade_level.asc(),
            ClassRoom.name.asc(),
        )

        return list(self.db.scalars(statement).all())

    def get_by_id(
        self,
        class_room_id: int,
    ) -> ClassRoom | None:
        return self.db.get(
            ClassRoom,
            class_room_id,
        )

    def get_by_name(
        self,
        name: str,
    ) -> ClassRoom | None:
        statement = select(ClassRoom).where(
            ClassRoom.name == name
        )

        return self.db.scalar(statement)

    def create(
        self,
        class_room: ClassRoom,
    ) -> ClassRoom:
        self.db.add(class_room)
        self.db.flush()
        self.db.refresh(class_room)

        return class_room

    def delete(
        self,
        class_room: ClassRoom,
    ) -> None:
        self.db.delete(class_room)