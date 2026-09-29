from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Teacher, User, UserRole
from app.repositories.user import UserRepository
from app.schemas.user import UserCreate


class UserService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = UserRepository(db)

    def get_all(self) -> list[User]:
        return self.repository.get_all(role=UserRole.GURU)

    def get_by_id(
        self,
        user_id: int,
    ) -> User | None:
        return self.repository.get_by_id(user_id)

    def create_guru(
        self,
        data: UserCreate,
        employee_number: str | None = None,
    ) -> User:
        existing_username = (
            self.repository.get_by_username(
                data.username
            )
        )

        if existing_username:
            raise ValueError(
                "Username sudah digunakan."
            )

        existing_email = (
            self.repository.get_by_email(
                data.email
            )
        )

        if existing_email:
            raise ValueError(
                "Email sudah digunakan."
            )

        user = User(
            username=data.username,
            email=data.email,
            password_hash=hash_password(
                data.password
            ),
            full_name=data.full_name,
            role=UserRole.GURU,
            is_active=True,
        )

        self.repository.create(user)

        teacher = Teacher(
            user_id=user.id,
            employee_number=employee_number,
        )

        self.db.add(teacher)

        self.db.commit()
        self.db.refresh(user)

        return user

    def update_guru(
        self,
        user_id: int,
        username: str,
        email: str,
        full_name: str,
        employee_number: str | None = None,
        password: str | None = None,
    ) -> User:
        user = self.repository.get_by_id(user_id)

        if not user:
            raise ValueError(
                "User tidak ditemukan."
            )

        if user.role != UserRole.GURU:
            raise ValueError(
                "Hanya akun GURU yang dapat diedit melalui menu ini."
            )

        username = username.strip()
        email = email.strip()
        full_name = full_name.strip()

        existing_username = (
            self.repository.get_by_username(username)
        )

        if (
            existing_username
            and existing_username.id != user.id
        ):
            raise ValueError(
                "Username sudah digunakan."
            )

        existing_email = (
            self.repository.get_by_email(email)
        )

        if (
            existing_email
            and existing_email.id != user.id
        ):
            raise ValueError(
                "Email sudah digunakan."
            )

        user.username = username
        user.email = email
        user.full_name = full_name

        if password and password.strip():
            user.password_hash = hash_password(
                password
            )

        teacher = user.teacher

        if not teacher:
            teacher = Teacher(
                user_id=user.id,
            )
            self.db.add(teacher)

        teacher.employee_number = (
            employee_number.strip()
            if employee_number
            else None
        )

        self.db.commit()
        self.db.refresh(user)

        return user

    def set_active(
        self,
        user_id: int,
        is_active: bool,
    ) -> User:
        user = self.repository.get_by_id(user_id)

        if not user:
            raise ValueError(
                "User tidak ditemukan."
            )

        user.is_active = is_active

        self.db.commit()
        self.db.refresh(user)

        return user

    def delete(
        self,
        user_id: int,
        current_user_id: int,
    ) -> None:
        if user_id == current_user_id:
            raise ValueError(
                "Akun yang sedang digunakan tidak dapat dihapus."
            )

        user = self.repository.get_by_id(user_id)

        if not user:
            raise ValueError(
                "User tidak ditemukan."
            )

        self.repository.delete(user)

        self.db.commit()
