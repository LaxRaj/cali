from typing import Literal

from pydantic import BaseModel, Field

Relation = Literal[
    "founded",
    "cofounded",
    "works_at",
    "invested_in",
    "advises",
    "backed_by",
    "competitor_of",
    "previously_at",
    "partner_of",
    "customer_of",
    "acquired_by",
]


class StartupProfile(BaseModel):
    company_name: str
    core_product: str
    tech_stack: list[str] = Field(default_factory=list)
    likely_bottleneck: str
    value_prop_pitch: str
    is_relevant: bool
    funding_stage: str = ""
    funding_amount: str = Field(default="", description='e.g. "$5.75M"; "" if not stated')
    hq: str = Field(default="", description='headquarters city/country as stated, e.g. "Munich, Germany"')
    website: str = Field(default="", description="the company's OWN website URL, only if it appears on the page")
    source_url: str = ""
    discovered_at: str = ""


class Person(BaseModel):
    name: str
    role: str = ""
    org: str = ""
    evidence: str = Field(description="Verbatim quote from the page supporting this person/role")
    # Public profile URLs. Only kept when the URL itself appears on a page we crawled (see quality.py / enrich.py).
    linkedin: str = ""
    twitter: str = ""
    github: str = ""
    homepage: str = ""
    link_source: str = ""  # where the profile links were found (a page URL, or "search")


class Edge(BaseModel):
    src: str
    rel: Relation
    dst: str
    evidence: str = Field(description="Verbatim quote from the page supporting this relationship")


class Extraction(BaseModel):
    startup: StartupProfile
    people: list[Person] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)


# --- Enrichment (deterministic, first-party; never LLM-generated) ---------------------------------


class ContactItem(BaseModel):
    value: str
    kind: str = ""  # emails: general|sales|press|support|person|other; phones: main
    source_url: str


class Contact(BaseModel):
    website: str = ""
    emails: list[ContactItem] = Field(default_factory=list)
    phones: list[ContactItem] = Field(default_factory=list)
    socials: dict[str, str] = Field(default_factory=dict)  # linkedin, twitter, github, youtube, ...
    contact_page: str = ""
    pages_crawled: list[str] = Field(default_factory=list)
    enriched_at: str = ""
    status: str = ""  # ok | no_website | crawl_failed | disabled
