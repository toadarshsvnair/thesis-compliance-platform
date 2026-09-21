from pydantic import BaseModel, Field

class FindingReviewRequest(BaseModel):
    action: str = Field(pattern="^(reviewed|rejected|waived)$")
    comment: str = Field(min_length=1, max_length=2000)

class ComplianceDecisionRequest(BaseModel):
    decision: str = Field(pattern="^(compliant|returned)$")
    comment: str = Field(min_length=1, max_length=4000)
