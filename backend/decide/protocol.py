"""System One-shaped decisions: typed questions about some `state`, typed answers with probabilities.

Mirrors TypeSafe's Jev API (POST /v1/systemone) so providers are interchangeable:
  choice -> pick one of several named options        (probabilities per option + confidence)
  score  -> place the state on an ordered scale      (probability-weighted score + confidence)
  noul   -> yes/no                                   (probability of yes)
"""

from dataclasses import dataclass, field
from typing import Literal, Protocol

QType = Literal["choice", "score", "noul"]


@dataclass
class Question:
    name: str
    type: QType
    instructions: str
    criteria: dict[str, str] | list[str] | None = None  # choice: {name: description}; score: [level texts]; noul: {"true": .., "false": ..}


@dataclass
class Answer:
    type: QType
    choice: str = ""
    score: float = 0.0
    noul: float = 0.0  # probability of "yes"
    confidence: float = 0.0
    probabilities: dict[str, float] = field(default_factory=dict)


def choice(name: str, instructions: str, criteria: dict[str, str]) -> Question:
    return Question(name, "choice", instructions, criteria)


def score(name: str, instructions: str, levels: list[str]) -> Question:
    return Question(name, "score", instructions, levels)


def noul(name: str, instructions: str, true: str, false: str) -> Question:
    return Question(name, "noul", instructions, {"true": true, "false": false})


class DecisionProvider(Protocol):
    name: str

    def decide(self, state: str, questions: list[Question]) -> dict[str, Answer]: ...
