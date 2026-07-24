from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ReviewRequest(BaseModel):
    action: str = Field(..., pattern="^(approve|reject|modify)$", description="通过/驳回/修改后通过")
    comment: str = Field(default="", description="审核意见")
    operator: str = Field(..., description="操作人姓名")
    modified_amount: Optional[float] = Field(None, description="修改后的金额（仅 modify 时使用）")


class ReviewResponse(BaseModel):
    id: int
    case_id: int
    action: str
    comment: str
    operator: str
    created_at: datetime

    class Config:
        from_attributes = True
