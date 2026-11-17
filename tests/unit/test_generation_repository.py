from uuid import uuid4

from app.models.generation import (
    Generation,
    GenerationSetting,
    GenerationStatus,
    MaterialType,
)
from app.models.user import User
from app.repositories.generation_repository import (
    GenerationBlueprintRepository,
    GenerationQuestionRepository,
    GenerationReferenceRepository,
    GenerationRepository,
    GenerationSettingRepository,
)


def _generation(user_id, title, status=GenerationStatus.COMPLETED):
    return Generation(
        user_id=user_id,
        title=title,
        subject="IPA",
        class_name="VII",
        type_materi=MaterialType.TEXT,
        material_text="Materi uji",
        total_multiple_choice=0,
        total_short_answer=0,
        total_essay=0,
        total_questions=0,
        status=status,
    )


def test_generation_repository_crud_filters_search_and_pagination(db_session):
    user = User(email="repository@example.com", full_name="Repository", password_hash="hash")
    other_user = User(email="other@example.com", full_name="Other", password_hash="hash")
    db_session.add_all([user, other_user])
    db_session.flush()
    repo = GenerationRepository(db_session)
    first = repo.add(_generation(user.id, "Biologi Dasar"))
    repo.add(_generation(user.id, "Fisika", GenerationStatus.FAILED))
    repo.add(_generation(other_user.id, "Biologi Lain"))
    db_session.commit()

    assert repo.get_owned(first.id, user.id).id == first.id
    assert repo.get_owned(first.id, other_user.id) is None
    assert repo.get_any(first.id).title == "Biologi Dasar"
    filtered, total = repo.list_owned(user.id, page=1, per_page=10, search="biologi", status="COMPLETED")
    assert total == 1
    assert [item.id for item in filtered] == [first.id]
    page, total = repo.list_owned(None, page=2, per_page=1)
    assert total == 3
    assert len(page) == 1
    assert repo.get_any(uuid4()) is None


def test_generation_related_repositories_and_setting_defaults(db_session):
    setting_repo = GenerationSettingRepository(db_session)
    assert setting_repo.get("missing", "default") == "default"
    active = GenerationSetting(key="active", value="42", is_active=True)
    inactive = GenerationSetting(key="inactive", value="99", is_active=False)
    db_session.add_all([active, inactive])
    db_session.commit()
    assert setting_repo.get("active") == "42"
    assert setting_repo.get("inactive", "fallback") == "fallback"

    for repository_type in (
        GenerationQuestionRepository,
        GenerationBlueprintRepository,
        GenerationReferenceRepository,
    ):
        repository = repository_type(db_session)
        repository.add_all([])
    db_session.flush()
