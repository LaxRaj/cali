from pydantic import BaseModel, Field


class StartupProfile(BaseModel):
    company_name: str
    core_product: str
    tech_stack: list[str] = Field(default_factory=list)
    likely_bottleneck: str
    value_prop_pitch: str
    is_relevant: bool
