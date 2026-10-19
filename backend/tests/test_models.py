from app.db.base import Base
from app import models  # noqa: F401


def test_core_recruitment_tables_are_registered():
    expected = {
        "users", "auth_identities", "refresh_tokens", "password_reset_tokens",
        "email_verifications", "students", "student_education", "student_experience",
        "student_projects", "student_skills", "integrations_accounts",
        "integration_snapshots", "resumes", "companies", "company_members",
        "invitations", "agencies", "agency_members", "agency_clients", "jobs",
        "job_requirements", "job_eval_config", "job_embeddings", "student_embeddings",
        "matches", "applications", "application_status_history", "assessments",
        "assessment_invites", "aptitude_questions", "coding_questions", "test_cases",
        "submissions", "submission_results", "scores", "score_breakdowns", "rankings",
        "shortlists", "interviews", "interview_feedback", "notifications",
        "notification_preferences", "audit_logs", "ai_usage_logs", "feature_flags",
        "settings", "candidate_comments", "consent_records",
    }
    assert expected.issubset(set(Base.metadata.tables))


def test_application_and_submission_idempotency_constraints_exist():
    application_constraints = {c.name for c in Base.metadata.tables["applications"].constraints}
    submission_constraints = {c.name for c in Base.metadata.tables["submissions"].constraints}
    assert "uq_application_idempotency" in application_constraints
    assert "uq_submission_idempotency" in submission_constraints
