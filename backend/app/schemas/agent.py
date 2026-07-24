from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel


class AgentTraceResponse(BaseModel):
    id: int
    case_id: int
    agent_name: str
    agent_label: str
    status: str
    input_data: dict[str, Any]
    output_data: dict[str, Any]
    confidence: Optional[float] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True
