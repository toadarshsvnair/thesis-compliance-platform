from pydantic import BaseModel, Field
from datetime import datetime

class SubmissionCreate(BaseModel):
    university_id: int
    faculty_id: int | None = None
    document_type_id: int | None = None
    rule_set_id: int
    student_name: str = Field(min_length=1, max_length=250)
    registration_number: str = Field(min_length=1, max_length=100)
    programme: str | None = None
    supervisor: str | None = None

class SubmissionOut(BaseModel):
    id: int
    status: str
    student_name: str
    registration_number: str
    current_version_id: int | None = None
    findings_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class FixRequest(BaseModel):
    finding_ids: list[int] = Field(min_length=1, max_length=100)
    confirm: bool = False

class FixPreviewItem(BaseModel):
    finding_id: int
    rule_id: str
    location: str
    operation: str
    risk_note: str

class FixPreviewOut(BaseModel):
    submission_id: int
    source_version_id: int
    items: list[FixPreviewItem]
    blocked_finding_ids: list[int] = []

class FixApplyOut(BaseModel):
    submission_id: int
    source_version_id: int
    target_version_id: int
    target_version_number: int
    applied_finding_ids: list[int]
    revalidation_finding_count: int
    revalidation_status: str
