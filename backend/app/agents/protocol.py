from dataclasses import dataclass, field
from typing import Any, Optional
from datetime import datetime


@dataclass
class A2AMessage:
    message_id: str
    source_agent: str
    target_agent: str
    case_id: int
    message_type: str  # "request" | "result_forward" | "rollback" | "terminate"
    payload: dict[str, Any]
    context: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    confidence: Optional[float] = None
    error: Optional[str] = None
