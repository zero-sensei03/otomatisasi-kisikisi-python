from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from app.models.generation import Generation, GenerationQuestion, GenerationBlueprint, GenerationReference, GenerationSetting

class GenerationRepository:
    def __init__(self, db: Session): self.db = db
    def add(self, generation): self.db.add(generation); self.db.flush(); return generation
    def get_owned(self, generation_id, user_id):
        return self.db.scalar(select(Generation).options(selectinload(Generation.questions).selectinload(GenerationQuestion.options), selectinload(Generation.blueprints), selectinload(Generation.references)).where(Generation.id == generation_id, Generation.user_id == user_id))
    def list_owned(self, user_id, *, page, per_page, search=None, status=None):
        query = select(Generation)
        if user_id is not None: query = query.where(Generation.user_id == user_id)
        if search: query = query.where(Generation.title.ilike(f"%{search}%"))
        if status: query = query.where(Generation.status == status)
        total = self.db.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = self.db.scalars(query.order_by(Generation.created_at.desc()).offset((page - 1) * per_page).limit(per_page)).all()
        return rows, total
    def get_any(self, generation_id):
        return self.db.scalar(select(Generation).options(selectinload(Generation.questions).selectinload(GenerationQuestion.options), selectinload(Generation.blueprints), selectinload(Generation.references)).where(Generation.id == generation_id))

class GenerationQuestionRepository:
    def __init__(self, db): self.db = db
    def add_all(self, items): self.db.add_all(items)

class GenerationBlueprintRepository:
    def __init__(self, db): self.db = db
    def add_all(self, items): self.db.add_all(items)

class GenerationReferenceRepository:
    def __init__(self, db): self.db = db
    def add_all(self, items): self.db.add_all(items)

class GenerationSettingRepository:
    def __init__(self, db): self.db = db
    def get(self, key, default=None):
        setting = self.db.scalar(select(GenerationSetting).where(GenerationSetting.key == key, GenerationSetting.is_active.is_(True)))
        return setting.value if setting else default
