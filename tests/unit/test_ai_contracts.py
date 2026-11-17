from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.integrations.ai.prompts.generation_prompt import build_generation_prompt
from app.integrations.ai.schemas import AIGenerationRequest, AIGenerationResponse, QuestionDistribution


@pytest.fixture
def response_payload():
    return {
        "summary": "Penjumlahan menggabungkan bilangan.",
        "questions": [{
            "number": 1,
            "type": "MULTIPLE_CHOICE",
            "cognitive_level": "C1",
            "question": "Berapakah 2 + 2?",
            "options": [
                {"label": "A", "text": "3", "is_correct": False},
                {"label": "B", "text": "4", "is_correct": True},
                {"label": "C", "text": "5", "is_correct": False},
                {"label": "D", "text": "6", "is_correct": False},
            ],
            "answer": "B",
            "explanation": "Dua ditambah dua adalah empat.",
        }],
        "blueprint": [{
            "number": 1,
            "question_number": 1,
            "material_topic": "Penjumlahan",
            "learning_objective": "Menghitung penjumlahan",
            "indicator": "Menghitung hasil penjumlahan",
            "question_type": "MULTIPLE_CHOICE",
            "cognitive_level": "C1",
            "difficulty": "EASY",
        }],
    }


def test_prompt_contains_only_selected_levels_and_source_restrictions():
    request = AIGenerationRequest(
        title="Bilangan",
        subject="Matematika",
        class_name="4",
        material="Sumber yang diberikan",
        cognitive_levels=["C1", "C4"],
        question_distribution=QuestionDistribution(multiple_choice=1, short_answer=0, essay=0),
    )
    prompt = build_generation_prompt(request)
    assert 'Cognitive levels yang diizinkan hanya: ["C1", "C4"]' in prompt
    assert "satu-satunya sumber fakta" in prompt
    assert "Sumber yang diberikan" in prompt


def test_ai_response_contract_accepts_matching_question_blueprint(response_payload):
    response = AIGenerationResponse.model_validate(response_payload)
    assert response.questions[0].answer == "B"
    assert response.blueprint[0].question_number == response.questions[0].number


@pytest.mark.parametrize("mutation", ["duplicate_number", "incorrect_answer", "level_mismatch", "missing_option"])
def test_ai_response_contract_rejects_invalid_question_consistency(response_payload, mutation):
    if mutation == "duplicate_number":
        response_payload["questions"].append(response_payload["questions"][0].copy())
    elif mutation == "incorrect_answer":
        response_payload["questions"][0]["answer"] = "A"
    elif mutation == "level_mismatch":
        response_payload["blueprint"][0]["cognitive_level"] = "C4"
    else:
        response_payload["questions"][0]["options"].pop()
    with pytest.raises((ValidationError, ValueError)):
        AIGenerationResponse.model_validate(response_payload)


def test_question_distribution_rejects_empty_question_request():
    with pytest.raises(ValidationError):
        QuestionDistribution(multiple_choice=0, short_answer=0, essay=0)
