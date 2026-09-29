from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Evaluation,
    EvaluationStatus,
)


class EvaluationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(
        self,
        evaluation_id: int,
    ) -> Evaluation | None:
        statement = (
            select(Evaluation)
            .options(
                joinedload(Evaluation.teacher),
                joinedload(Evaluation.subject),
                joinedload(Evaluation.class_room),
            )
            .where(
                Evaluation.id == evaluation_id
            )
        )

        return self.db.scalar(statement)

    def paginate(
        self,
        *,
        teacher_id: int | None = None,
        is_admin: bool = False,
        search: str | None = None,
        subject_id: int | None = None,
        class_id: int | None = None,
        semester: str | None = None,
        academic_year: str | None = None,
        status: EvaluationStatus | None = None,
        page: int = 1,
        per_page: int = 10,
    ) -> tuple[list[Evaluation], int]:
        statement = (
            select(Evaluation)
            .options(
                joinedload(Evaluation.teacher),
                joinedload(Evaluation.subject),
                joinedload(Evaluation.class_room),
            )
        )

        count_statement = select(
            func.count(Evaluation.id)
        )

        if not is_admin and teacher_id is not None:
            statement = statement.where(
                Evaluation.teacher_id == teacher_id
            )

            count_statement = count_statement.where(
                Evaluation.teacher_id == teacher_id
            )

        if search:
            search_value = (
                f"%{search.strip()}%"
            )

            search_condition = or_(
                Evaluation.name.ilike(
                    search_value
                ),
                Evaluation.description.ilike(
                    search_value
                ),
                Evaluation.academic_year.ilike(
                    search_value
                ),
            )

            statement = statement.where(
                search_condition
            )

            count_statement = count_statement.where(
                search_condition
            )

        if subject_id is not None:
            statement = statement.where(
                Evaluation.subject_id == subject_id
            )

            count_statement = count_statement.where(
                Evaluation.subject_id == subject_id
            )

        if class_id is not None:
            statement = statement.where(
                Evaluation.class_id == class_id
            )

            count_statement = count_statement.where(
                Evaluation.class_id == class_id
            )

        if semester:
            statement = statement.where(
                Evaluation.semester == semester
            )

            count_statement = count_statement.where(
                Evaluation.semester == semester
            )

        if academic_year:
            statement = statement.where(
                Evaluation.academic_year
                == academic_year
            )

            count_statement = count_statement.where(
                Evaluation.academic_year
                == academic_year
            )

        if status:
            statement = statement.where(
                Evaluation.status == status
            )

            count_statement = count_statement.where(
                Evaluation.status == status
            )

        total = self.db.scalar(
            count_statement
        ) or 0

        offset = (
            (page - 1) * per_page
        )

        statement = (
            statement
            .order_by(
                Evaluation.created_at.desc(),
                Evaluation.id.desc(),
            )
            .offset(offset)
            .limit(per_page)
        )

        evaluations = list(
            self.db.scalars(statement).unique().all()
        )

        return evaluations, total

    def create(
        self,
        evaluation: Evaluation,
    ) -> Evaluation:
        self.db.add(evaluation)
        self.db.flush()
        self.db.refresh(evaluation)

        return evaluation

    def delete(
        self,
        evaluation: Evaluation,
    ) -> None:
        self.db.delete(evaluation)