from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class DocumentUpload(BaseModel):
    doc_type: str
    content_text: str


class CaseCreate(BaseModel):
    insured_name: str = Field(..., description="出险人姓名")
    insurance_product: str = Field(..., description="险种")
    incident_desc: str = Field(..., description="出险描述")
    incident_date: str = Field(..., description="出险日期，格式 YYYY-MM-DD")
    total_amount: Optional[float] = Field(None, description="医疗总费用")
    documents: list[DocumentUpload] = []


class CaseResponse(BaseModel):
    id: int
    case_no: str
    insured_name: str
    insurance_product: str
    incident_desc: str
    incident_date: datetime
    status: str
    risk_level: str
    total_amount: Optional[float] = None
    calculated_amount: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
