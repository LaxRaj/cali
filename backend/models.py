from typing import Literal

from pydantic import BaseModel, Field

Relation = Literal[
    "founded", "cofounded", "works_at", "invested_in", "advises", "backed_by", "competitor_of"
]


class StartupProfile(BaseModel):
    company_name: str
    core_product: str
    tech_stack: list[str] = Field(default_factory=list)
    likely_bottleneck: str
    value_prop_pitch: str
    is_relevant: bool
    funding_stage: str = ""
    source_url: str = ""
    discovered_at: str = ""


class Person(BaseModel):
    name: str
    role: str = ""
    org: str = ""
    evidence: str = Field(description="Verbatim quote from the page supporting this person/role")


class Edge(BaseModel):
    src: str
    rel: Relation
    dst: str
    evidence: str = Field(description="Verbatim quote from the page supporting this relationship")


class Extraction(BaseModel):
    startup: StartupProfile
    people: list[Person] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
