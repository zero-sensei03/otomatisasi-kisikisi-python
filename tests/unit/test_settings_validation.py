from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models.generation import GenerationSetting
from app.routers import generation as generation_router
from app.schemas.generation import GenerationSettingsSchema


@pytest.mark.parametrize("maximum", [10_000, 100_000, 1_000_000, 100_000_000, 1_000_000_000])
def test_material_character_setting_accepts_and_persists_requested_maximum(maximum):
    engine = create_engine("sqlite:///:memory:")
    GenerationSetting.__table__.create(engine)
    keys = (
        "generation.free_limit",
        "generation.cost_per_generate",
        "generation.enabled",
        "generation.max_questions_per_generate",
        "generation.max_material_characters",
        "generation.max_reference_characters",
    )
    payload = {
        "generation_free_limit": "20",
        "generation_cost_per_generate": "1.25",
        "generation_enabled": "true",
        "generation_max_questions_per_generate": "20",
        "generation_max_material_characters": str(maximum),
        "generation_max_reference_characters": "5000",
    }
    schema = GenerationSettingsSchema.model_validate(payload)
    assert schema.generation_max_material_characters == maximum

    with Session(engine) as db:
        db.add_all(GenerationSetting(key=key, value="1") for key in keys)
        db.commit()
        response = generation_router.update_generation_settings(
            SimpleNamespace(headers={"accept": "application/json"}),
            **payload,
            db=db,
            user=SimpleNamespace(id=uuid4()),
        )
        persisted = db.scalar(select(GenerationSetting).where(GenerationSetting.key == "generation.max_material_characters"))
        saved = json.loads(response.body)["settings"]["generation.max_material_characters"]

        assert response.status_code == 200
        assert saved == str(maximum)
        assert persisted.value == str(maximum)
        assert persisted.is_active
    engine.dispose()


@pytest.mark.parametrize("invalid", ["0", "-1", "1000000001", "not-a-number", "1.5", ""])
def test_material_character_setting_rejects_invalid_values(invalid):
    with pytest.raises(ValidationError):
        GenerationSettingsSchema(
            generation_free_limit=10,
            generation_cost_per_generate=0,
            generation_enabled="true",
            generation_max_questions_per_generate=10,
            generation_max_material_characters=invalid,
            generation_max_reference_characters=100,
        )


def test_generation_setting_database_value_can_hold_one_billion_as_decimal_text():
    setting = GenerationSetting(key="generation.max_material_characters", value="1000000000")
    assert len(setting.value) <= 255
    assert int(setting.value) == 1_000_000_000
