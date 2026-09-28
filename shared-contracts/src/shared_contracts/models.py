from __future__ import annotations
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, HttpUrl, constr, field_validator
from enum import Enum
from datetime import datetime


class Label(str, Enum):
    YES = "Yes"
    WEAK = "Weak"
    NO = "No"


class Topic(BaseModel):
    id: constr(strip_whitespace=True, min_length=1)
    name: str
    definition: str = Field(..., description="2–3 sentences explaining the topic’s scope")
    synonyms: List[str] = Field(default_factory=list, description="Alternative phrases/keywords")
    exclusions: List[str] = Field(default_factory=list, description="Negative keywords to exclude")


class Partner(BaseModel):
    id: constr(strip_whitespace=True, min_length=1)
    name: str
    domains: List[HttpUrl] = Field(default_factory=list)
    aliases: List[str] = Field(default_factory=list)

    @field_validator("aliases")
    @classmethod
    def unique_aliases(cls, v: List[str]) -> List[str]:
        return sorted(set([a.strip() for a in v if a.strip()]))


class Chunk(BaseModel):
    id: constr(strip_whitespace=True, min_length=1)
    partner_id: str
    url: HttpUrl
    title: str | None = None
    date: datetime | None = None
    text: str = Field(..., min_length=10)
    embedding: Optional[List[float]] = Field(default=None, description="Dense vector (optional)")


class Evidence(BaseModel):
    url: HttpUrl
    quote: str = Field(..., min_length=3)


class Verdict(BaseModel):
    partner_id: str
    topic_id: str
    label: Label
    score: float = Field(ge=0.0, le=1.0)
    evidence: List[Evidence] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
