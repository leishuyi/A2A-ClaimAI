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
    """理赔案件 — 核心实体

    参考 grid-qa 模式：
    - soft delete (deleted_at)
    - 高频查询字段加索引 (status)
    - 创建人/更新人追踪
    """
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    case_no = Column(String(32), unique=True, nullable=False, index=True)
    insured_name = Column(String(64), nullable=False)
    insurance_product = Column(String(128), nullable=False)
    incident_desc = Column(Text, nullable=False)
    incident_date = Column(DateTime, nullable=False)
    status = Column(SAEnum(CaseStatus), default=CaseStatus.DRAFT, nullable=False, index=True)
    risk_level = Column(SAEnum(RiskLevel), default=RiskLevel.LOW, nullable=False)
    total_amount = Column(Float, nullable=True)
    calculated_amount = Column(Float, nullable=True)
    created_by = Column(String(64), nullable=True)
    updated_by = Column(String(64), nullable=True)
    deleted_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    traces = relationship("AgentTrace", back_populates="case", order_by="AgentTrace.id")
    reviews = relationship("AuditLog", back_populates="case", order_by="AuditLog.created_at")
    documents = relationship("Document", back_populates="case", cascade="all, delete-orphan", order_by="Document.created_at")


class AgentTrace(Base):
    """Agent 执行追踪 — 全链路可追溯"""
    __tablename__ = "agent_traces"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False, index=True)
    agent_name = Column(SAEnum(AgentName), nullable=False)
    agent_label = Column(String(64), nullable=False)
    status = Column(SAEnum(AgentStatus), default=AgentStatus.PENDING, nullable=False)
    input_data = Column(JSON, default=dict)
    output_data = Column(JSON, default=dict)
    confidence = Column(Float, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    case = relationship("Case", back_populates="traces")


class DocumentType(str, enum.Enum):
    ID_CARD = "id_card"
    DIAGNOSIS = "diagnosis"
    INVOICE = "invoice"
    MEDICAL_RECORD = "medical_record"
    OTHER = "other"


class Document(Base):
    """影像材料 — 关联案件的文件记录"""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False, index=True)
    doc_type = Column(SAEnum(DocumentType), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False, default=0)
    mime_type = Column(String(100), nullable=True)
    extracted_name = Column(String(64), nullable=True)       # OCR提取/用户填写的姓名
    invoice_no = Column(String(128), nullable=True, index=True)  # 发票号码（查重用）
    document_date = Column(DateTime, nullable=True)           # 单据日期
    deleted_at = Column(DateTime, nullable=True, index=True)  # 软删除
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    case = relationship("Case", back_populates="documents")


class AuditLog(Base):
    """审计日志 — 全操作留痕，支持幂等防重"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False, index=True)
    action = Column(String(32), nullable=False)
    comment = Column(Text, default="")
    operator = Column(String(64), nullable=False)
    idempotency_key = Column(String(64), unique=True, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    case = relationship("Case", back_populates="reviews")
