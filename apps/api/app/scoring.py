from collections import Counter
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Option(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=1, max_length=16)
    text: str = Field(min_length=1, max_length=500)
    score: int = Field(default=0, ge=-10000, le=10000)
    property: str = Field(default="", max_length=80)


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=1000)
    options: list[Option] = Field(min_length=2, max_length=6)

    @model_validator(mode="after")
    def distinct_keys(self) -> "Question":
        if len({option.key for option in self.options}) != len(self.options):
            raise ValueError("Option keys must be unique within a question")
        return self


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)
    threshold: int = Field(default=0, ge=-1000000, le=1000000)
    properties: list[str] = Field(default_factory=list, max_length=100)
    image_id: UUID | None = None

    @model_validator(mode="after")
    def distinct_properties(self) -> "Rule":
        if any(not value or len(value) > 80 for value in self.properties):
            raise ValueError("Invalid result property")
        if len(set(self.properties)) != len(self.properties):
            raise ValueError("Duplicate result properties")
        return self


class DraftContent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    questions: list[Question] = Field(default_factory=list, max_length=100)
    rules: list[Rule] = Field(default_factory=list, max_length=50)


class Content(DraftContent):
    model_config = ConfigDict(extra="forbid")
    questions: list[Question] = Field(min_length=1, max_length=100)
    rules: list[Rule] = Field(default_factory=list, max_length=50)


def validate_publication(content: Content, app_type: str, strategy: str) -> None:
    if strategy == "ai":
        if app_type != "assessment":
            raise ValueError("AI scoring supports assessments only")
        return
    if not content.rules:
        raise ValueError("Rule scoring requires at least one result")
    if app_type == "score":
        minimum = sum(
            min(option.score for option in question.options) for question in content.questions
        )
        if min(rule.threshold for rule in content.rules) > minimum:
            raise ValueError("Result thresholds do not cover the minimum possible score")
    elif any(not rule.properties for rule in content.rules):
        raise ValueError("Assessment results require properties")


def selected_options(content: Content, choices: list[str]) -> list[Option]:
    if len(choices) != len(content.questions):
        raise ValueError("Answer every question exactly once")
    selected = []
    for question, choice in zip(content.questions, choices, strict=True):
        option = next((option for option in question.options if option.key == choice), None)
        if option is None:
            raise ValueError("Invalid option for this question")
        selected.append(option)
    return selected


class Result(BaseModel):
    name: str
    description: str
    score: int | None
    image_id: UUID | None
    strategy: Literal["rules"] = "rules"


def evaluate(content: Content, app_type: str, choices: list[str]) -> Result:
    validate_publication(content, app_type, "rules")
    options = selected_options(content, choices)
    score: int | None
    if app_type == "score":
        score = sum(option.score for option in options)
        # Python's stable sort preserves immutable rule order for equal thresholds.
        rule = next(
            rule
            for rule in sorted(content.rules, key=lambda rule: -rule.threshold)
            if score >= rule.threshold
        )
    else:
        score = None
        counts = Counter(option.property for option in options)
        # max returns the first maximum: ties follow immutable UI rule order.
        rule = max(content.rules, key=lambda rule: sum(counts[prop] for prop in rule.properties))
    return Result(name=rule.name, description=rule.description, score=score, image_id=rule.image_id)
