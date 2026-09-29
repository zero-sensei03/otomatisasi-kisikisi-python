from sqlalchemy.orm import Session

from app.models import Teacher, User, UserRole
from app.repositories.teacher import TeacherRepository
from app.schemas.teacher import TeacherCreate


class TeacherService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = TeacherRepository(db)

    def get_all(self) -> list[Teacher]:
        return self.repository.get_all()

    def get_by_id(
        self,
        teacher_id: int,
    ) -> Teacher | None:
        return self.repository.get_by_id(
            teacher_id
        )

    def create(
        self,
        data: TeacherCreate,
    ) -> Teacher:
        user = self.db.get(
            User,
            data.user_id,
        )

        if not user:
            raise ValueError(
                "User tidak ditemukan."
            )

        if user.role != UserRole.GURU:
            raise ValueError(
                "User harus memiliki role GURU."
            )

        existing_teacher = (
            self.repository.get_by_user_id(
                data.user_id
            )
        )

        if existing_teacher:
            raise ValueError(
                "User tersebut sudah memiliki data guru."
            )

        if data.employee_number:
            existing_employee = (
                self.repository.get_by_employee_number(
                    data.employee_number
                )
            )

            if existing_employee:
                raise ValueError(
                    "Nomor pegawai sudah digunakan."
                )

        teacher = Teacher(
            user_id=data.user_id,
            employee_number=data.employee_number,
        )

        self.repository.create(teacher)

        self.db.commit()
        self.db.refresh(teacher)

        return teacher

    def delete(
        self,
        teacher_id: int,
    ) -> None:
        teacher = self.repository.get_by_id(
            teacher_id
        )

        if not teacher:
            raise ValueError(
                "Guru tidak ditemukan."
            )

        self.repository.delete(teacher)
        self.db.commit()
