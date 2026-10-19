import pytest
from pydantic import ValidationError
from app.schemas.assessments import AptitudeQuestionCreate, AssessmentCreate


def test_aptitude_question_requires_answer_key_to_match_option():
    with pytest.raises(ValidationError):
        AptitudeQuestionCreate(
            category="Reasoning", difficulty="EASY", prompt="Choose the correct answer.",
            options=[{"id": "A", "text": "First"}, {"id": "B", "text": "Second"}],
            answer_key="C",
        )


def test_aptitude_question_rejects_extra_option_fields():
    with pytest.raises(ValidationError):
        AptitudeQuestionCreate(
            category="Reasoning", difficulty="EASY", prompt="Choose the correct answer.",
            options=[
                {"id": "A", "text": "First", "is_correct": True},
                {"id": "B", "text": "Second"},
            ],
            answer_key="A",
        )


def test_assessment_requires_questions_for_selected_type():
    with pytest.raises(ValidationError):
        AssessmentCreate(
            job_id="d3b07384-d9a0-4c8f-8c36-0f3f1e4e9f11",
            title="Aptitude round", assessment_type="APTITUDE", duration_minutes=30,
        )


def test_assessment_rejects_duplicate_question_ids():
    question_id = "d3b07384-d9a0-4c8f-8c36-0f3f1e4e9f11"
    with pytest.raises(ValidationError):
        AssessmentCreate(
            job_id="d3b07384-d9a0-4c8f-8c36-0f3f1e4e9f12",
            title="Aptitude round", assessment_type="APTITUDE", duration_minutes=30,
            aptitude_question_ids=[question_id, question_id],
        )


def test_valid_aptitude_question_schema():
    question = AptitudeQuestionCreate(
        category="Reasoning", difficulty="MEDIUM", prompt="Which number is even?",
        options=[{"id": "A", "text": "3"}, {"id": "B", "text": "8"}],
        answer_key="B", marks=2, negative_marks=0.5,
    )
    assert question.answer_key == "B"
    assert len(question.options) == 2
