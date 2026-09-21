from pydantic import BaseModel, Field
from typing import Literal

RuleSetStatus = Literal['draft','in_review','published','retired']

class RuleSetCreate(BaseModel):
    university_id: int
    faculty_id: int | None = None
    document_type_id: int | None = None
    version: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    source_metadata: dict = {}

class RuleSetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    faculty_id: int | None = None
    document_type_id: int | None = None
    source_metadata: dict | None = None

class RuleCreate(BaseModel):
    rule_id: str = Field(pattern=r'^[A-Z0-9_-]{2,50}$')
    category: str = Field(min_length=1, max_length=100)
    requirement: str = Field(min_length=1, max_length=5000)
    validation_method: str = Field(min_length=1, max_length=50)
    severity: Literal['Major','Minor','Review','major','minor','review']
    auto_fix_allowed: bool = False
    source_reference: str | None = Field(default=None, max_length=300)
    active: bool = True

class RuleUpdate(BaseModel):
    category: str | None = Field(default=None, min_length=1, max_length=100)
    requirement: str | None = Field(default=None, min_length=1, max_length=5000)
    validation_method: str | None = Field(default=None, min_length=1, max_length=50)
    severity: Literal['Major','Minor','Review','major','minor','review'] | None = None
    auto_fix_allowed: bool | None = None
    source_reference: str | None = Field(default=None, max_length=300)
    active: bool | None = None

class StatusChange(BaseModel):
    comment: str = Field(min_length=3, max_length=2000)

class CloneRequest(BaseModel):
    version: str = Field(min_length=1, max_length=50)
    name: str | None = Field(default=None, max_length=200)

class GuidelineSourceOut(BaseModel):
    id: int
    original_filename: str
    sha256: str
    size_bytes: int
    mime_type: str | None
