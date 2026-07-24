import datetime
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, JSON, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from app.database.session import Base
import enum


class CaseStatus(str, enum.Enum):
    DRAFT = "draft"
    PROCESSING = "processing"
    AGENTS_COMPLETED = "agents_completed"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AgentName(str, enum.Enum):
    A_INTAKE = "agent_a_intake"
    B_DOC_PARSER = "agent_b_doc_parser"
    C_LIABILITY = "agent_c_liability"
    D_CALCULATION = "agent_d_calculation"
    E_RISK = "agent_e_risk"
    F_SUMMARY = "agent_f_summary"


class AgentStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    case_no = Column(String(32), unique=True, nullable=False, index=True)
    insured_name = Column(String(64), nullable=False)
    insurance_product = Column(String(128), nullable=False)
    incident_desc = Column(Text, nullable=False)
    incident_date = Column(DateTime, nullable=False)
    status = Column(SAEnum(CaseStatus), default=CaseStatus.DRAFT, nullable=False)
    risk_level = Column(SAEnum(RiskLevel), default=RiskLevel.LOW, nullable=False)
    total_amount = Column(Float, nullable=True)
    calculated_amount = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    traces = relationship("AgentTrace", back_populates="case", order_by="AgentTrace.id")
    reviews = relationship("AuditLog", back_populates="case", order_by="AuditLog.created_at")


class AgentTrace(Base):
    __tablename__ = "agent_traces"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    agent_name = Column(SAEnum(AgentName), nullable=False)
    agent_label = Column(String(64), nullable=False)
    status = Column(SAEnum(AgentStatus), default=AgentStatus.PENDING, nullable=False)
    input_data = Column(JSON, default=dict)
    output_data = Column(JSON, default=dict)
    confidence = Column(Float, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    case = relationship("Case", back_populates="traces")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    action = Column(String(32), nullable=False)
    comment = Column(Text, default="")
    operator = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    case = relationship("Case", back_populates="reviews")
