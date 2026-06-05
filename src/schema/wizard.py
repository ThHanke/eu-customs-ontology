from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator


class AnswerOption(BaseModel):
    model_config = ConfigDict(frozen=True)

    answer_text: str
    next_node_id: str | None = None


class ClassificationNode(BaseModel):
    model_config = ConfigDict(frozen=True)

    node_id: str
    question_text: str
    answer_options: list[AnswerOption]
    is_terminal: bool
    cn_code: str | None = None
    path_from_root: list[str]

    @model_validator(mode="after")
    def _check_cn_code_only_on_terminal(self) -> ClassificationNode:
        if self.cn_code is not None and not self.is_terminal:
            raise ValueError("cn_code may only be set on terminal nodes")
        return self


class WizardTree(BaseModel):
    chapter: int
    nodes: dict[str, ClassificationNode]
    root_node_id: str
