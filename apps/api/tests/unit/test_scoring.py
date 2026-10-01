import pytest

from app.scoring import Content, evaluate, validate_publication


def assessment() -> Content:
    return Content.model_validate(
        {
            "questions": [
                {
                    "title": "Q1",
                    "options": [
                        {"key": "A", "text": "A", "property": "I"},
                        {"key": "B", "text": "B", "property": "E"},
                    ],
                },
                {
                    "title": "Q2",
                    "options": [
                        {"key": "A", "text": "A", "property": "E"},
                        {"key": "B", "text": "B", "property": "I"},
                    ],
                },
            ],
            "rules": [{"name": "E", "properties": ["E"]}, {"name": "I", "properties": ["I"]}],
        }
    )


def test_assessment_aligns_selected_option_to_its_question() -> None:
    # The original cross join ties E/I and incorrectly selects the first E rule.
    assert evaluate(assessment(), "assessment", ["A", "B"]).name == "I"
    assert evaluate(assessment(), "assessment", ["A", "A"]).name == "E"


@pytest.mark.parametrize("choices", [[], ["A"], ["Z", "A"], ["A", "A", "A"]])
def test_rejects_invalid_choices(choices: list[str]) -> None:
    with pytest.raises(ValueError):
        evaluate(assessment(), "assessment", choices)


def test_score_covers_negative_minimum_and_uses_highest_satisfied_threshold() -> None:
    content = Content.model_validate(
        {
            "questions": [
                {
                    "title": "Q",
                    "options": [
                        {"key": "A", "text": "A", "score": -2},
                        {"key": "B", "text": "B", "score": 5},
                    ],
                }
            ],
            "rules": [{"name": "high", "threshold": 4}, {"name": "low", "threshold": -2}],
        }
    )
    assert evaluate(content, "score", ["A"]).name == "low"
    assert evaluate(content, "score", ["B"]).name == "high"
    content.rules[1].threshold = 0
    with pytest.raises(ValueError, match="minimum"):
        validate_publication(content, "score", "rules")
