import pytest
from pydantic import ValidationError

from app.models import IssueCategory
from app.schemas import HelpRequestCreate


@pytest.fixture
def submission():
    return {
        "student_name": "Taylor Example",
        "assignment": "Lab 3",
        "issue_category": "debugging",
        "description": "My loop never terminates.",
    }


def test_submission_trims_surrounding_whitespace(submission):
    submission.update(
        student_name="  Taylor Example  ",
        assignment=" Lab 3 ",
        description="\n My loop never terminates. \t",
    )

    request = HelpRequestCreate.model_validate(submission)

    assert request.student_name == "Taylor Example"
    assert request.assignment == "Lab 3"
    assert request.description == "My loop never terminates."
    assert request.issue_category == IssueCategory.DEBUGGING


@pytest.mark.parametrize("field", ["student_name", "assignment", "description"])
@pytest.mark.parametrize("value", ["", " \t\n "])
def test_submission_rejects_blank_text(submission, field, value):
    submission[field] = value

    with pytest.raises(ValidationError):
        HelpRequestCreate.model_validate(submission)


@pytest.mark.parametrize(
    "field,maximum", [("student_name", 100), ("assignment", 120), ("description", 1000)]
)
def test_submission_enforces_text_length_limits(submission, field, maximum):
    submission[field] = "a" * maximum
    HelpRequestCreate.model_validate(submission)
    submission[field] += "a"

    with pytest.raises(ValidationError):
        HelpRequestCreate.model_validate(submission)


def test_submission_rejects_unknown_categories(submission):
    submission["issue_category"] = "unknown"

    with pytest.raises(ValidationError):
        HelpRequestCreate.model_validate(submission)


def test_submission_cannot_set_server_controlled_fields(submission):
    server_fields = {
        "id": 1,
        "status": "resolved",
        "assigned_ta": "Example TA",
        "created_at": "2026-11-19T12:00:00Z",
    }
    submission.update(server_fields)

    with pytest.raises(ValidationError) as error:
        HelpRequestCreate.model_validate(submission)

    assert {item["loc"][0] for item in error.value.errors()} == set(server_fields)


def test_submission_requires_a_description(submission):
    del submission["description"]

    with pytest.raises(ValidationError):
        HelpRequestCreate.model_validate(submission)


def test_submission_rejects_non_text_names(submission):
    submission["student_name"] = 123

    with pytest.raises(ValidationError):
        HelpRequestCreate.model_validate(submission)


@pytest.mark.parametrize("field", ["student_name", "assignment", "description"])
@pytest.mark.parametrize("value", ["text\x00with NUL", "text\ud800with an unpaired surrogate"])
def test_submission_rejects_text_that_cannot_be_stored(submission, field, value):
    submission[field] = value

    with pytest.raises(ValidationError) as error:
        HelpRequestCreate.model_validate(submission)

    assert error.value.errors()[0]["loc"] == (field,)


def test_submission_preserves_unicode_and_description_formatting(submission):
    description = "print('café')\n\t# Check λ here"
    submission.update(student_name="Zoë Example", description=description)

    request = HelpRequestCreate.model_validate(submission)

    assert request.student_name == "Zoë Example"
    assert request.description == description
