"""影像材料上传/下载/管理路由

参考 grid-qa 模式：
- multipart/form-data 文件上传
- 文件类型/大小白名单校验
- BizError 统一业务异常
"""
import os
import uuid
from typing import Optional

from dateutil import parser as dateparser
from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.config import settings
from app.core.response import ApiResponse, BizError, ErrCode
from app.database.models import AuditLog
from app.database.session import get_db
from app.database.models import Case, Document, DocumentType
from app.schemas.case import DocumentResponse
from app.services.file_storage import get_storage_backend
from app.services.image_forensics import analyze_image, has_tampering_risk

router = APIRouter()

# 文件魔数签名
MAGIC_SIGNATURES = {".jpg": b"\xff\xd8\xff", ".jpeg": b"\xff\xd8\xff", ".png": b"\x89PNG", ".bmp": b"BM", ".tiff": b"II*\x00", ".pdf": b"%PDF"}

ALLOWED_EXTENSIONS = {ext.strip().lower() for ext in settings.allowed_extensions.split(",")}
DOC_TYPE_MAP = {
    "id_card": DocumentType.ID_CARD,
    "diagnosis": DocumentType.DIAGNOSIS,
    "invoice": DocumentType.INVOICE,
    "medical_record": DocumentType.MEDICAL_RECORD,
    "other": DocumentType.OTHER,
}


def _check_case_exists(case_id: int, db: Session) -> Case:
    case = db.query(Case).filter(Case.id == case_id, Case.deleted_at.is_(None)).first()
    if not case:
        raise BizError(code=ErrCode.CASE_NOT_FOUND, message="案件不存在")
    return case


def _validate_file(file: UploadFile):
    ext = os.path.splitext(file.filename or "")[1].lower() if file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise BizError(code=ErrCode.VALIDATION, message=f"不支持的文件类型: {ext}，允许: {settings.allowed_extensions}")
    if file.size is not None and file.size > settings.max_file_size:
        raise BizError(code=ErrCode.VALIDATION, message=f"文件大小超过限制 ({settings.max_file_size // 1024 // 1024}MB)")


def _verify_magic_bytes(content: bytes, ext: str):
    expected = MAGIC_SIGNATURES.get(ext)
    if expected and not content.startswith(expected):
        raise BizError(code=ErrCode.VALIDATION, message=f"文件内容与扩展名 {ext} 不匹配，疑似伪造文件")


def _doc_to_response(doc: Document) -> DocumentResponse:
    """将 Document ORM 转换为响应模型，自动填充访问 URL"""
    resp = DocumentResponse.model_validate(doc)
    storage = get_storage_backend()
    resp.url = storage.get_url(doc.file_path)
    return resp


@router.post("/{case_id}/documents", response_model=ApiResponse)
async def upload_document(
    case_id: int,
    file: UploadFile = File(...),
    doc_type: str = Form("other"),
    extracted_name: Optional[str] = Form(None),
    invoice_no: Optional[str] = Form(None),
    document_date: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """上传影像材料（multipart/form-data），支持风控字段"""
    case = _check_case_exists(case_id, db)

    if doc_type not in DOC_TYPE_MAP:
        raise BizError(code=ErrCode.VALIDATION, message=f"无效文档类型: {doc_type}")

    _validate_file(file)

    content = await file.read()
    if len(content) > settings.max_file_size:
        raise BizError(code=ErrCode.VALIDATION, message=f"文件大小超过限制 ({settings.max_file_size // 1024 // 1024}MB)")
    _verify_magic_bytes(content, ext)

    # 图片篡改检测（仅对图片文件）
    if ext in (".jpg", ".jpeg", ".png", ".bmp", ".tiff"):
        forensics_findings = analyze_image(content, file.filename or "")
        is_risky, risk_level, risk_detail = has_tampering_risk(forensics_findings)
        for f in forensics_findings:
            fraud_flags.append(f"图片{f['rule']}: [{f['risk']}] {f['detail'][:60]}")
        if is_risky:
            logger.warning("图片篡改检测告警", filename=file.filename, risk=risk_level, detail=risk_detail)

    # 发票号全局查重
    fraud_flags: list[str] = []
    if invoice_no:
        existing = db.query(Document).filter(
            Document.invoice_no == invoice_no,
            Document.case_id != case_id,
        ).first()
        if existing:
            fraud_flags.append(f"发票号重复: 案件 {existing.case_id} 已使用此发票号")

    # 解析单据日期
    parsed_date = None
    if document_date:
        try:
            parsed_date = dateparser.parse(document_date)
        except Exception:
            raise BizError(code=ErrCode.VALIDATION, message="单据日期格式无效")

    # 生成存储路径
    ext = os.path.splitext(file.filename or "unknown")[1]
    unique_name = f"{uuid.uuid4().hex}{ext}"
    relative_path = f"{case_id}/{unique_name}"

    storage = get_storage_backend()
    storage.save(content, relative_path)

    doc = Document(
        case_id=case_id,
        doc_type=DOC_TYPE_MAP[doc_type],
        file_name=file.filename or unique_name,
        file_path=relative_path,
        file_size=len(content),
        mime_type=file.content_type,
        extracted_name=extracted_name,
        invoice_no=invoice_no,
        document_date=parsed_date,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    resp = _doc_to_response(doc)
    if settings.feature_audit_log:
        db.add(AuditLog(case_id=case_id, action="document_upload", comment=f"上传文档: {file.filename}", operator="system"))
        db.commit()

    return ApiResponse(data={"document": resp.model_dump(), "fraud_flags": fraud_flags})


@router.get("/{case_id}/documents", response_model=ApiResponse)
def list_documents(case_id: int, db: Session = Depends(get_db)):
    """查询案件的所有影像材料"""
    _check_case_exists(case_id, db)

    docs = db.query(Document).filter(Document.case_id == case_id).all()
    return ApiResponse(data=[_doc_to_response(d) for d in docs])


@router.get("/{case_id}/documents/{doc_id}", response_model=ApiResponse)
def get_document(case_id: int, doc_id: int, db: Session = Depends(get_db)):
    """获取单个文档元信息"""
    _check_case_exists(case_id, db)

    doc = db.query(Document).filter(Document.id == doc_id, Document.case_id == case_id, Document.deleted_at.is_(None)).first()
    if not doc:
        raise BizError(code=ErrCode.CASE_NOT_FOUND, message="文档不存在")

    return ApiResponse(data=_doc_to_response(doc))


@router.delete("/{case_id}/documents/{doc_id}", response_model=ApiResponse)
def delete_document(case_id: int, doc_id: int, db: Session = Depends(get_db)):
    """删除影像材料"""
    _check_case_exists(case_id, db)

    doc = db.query(Document).filter(Document.id == doc_id, Document.case_id == case_id, Document.deleted_at.is_(None)).first()
    if not doc:
        raise BizError(code=ErrCode.CASE_NOT_FOUND, message="文档不存在")

    storage = get_storage_backend()
    storage.delete(doc.file_path)

    from datetime import datetime as _dt
    doc.deleted_at = _dt.utcnow()
    if settings.feature_audit_log:
        db.add(AuditLog(case_id=case_id, action="document_delete", comment=f"删除文档: {doc.file_name}", operator="system"))
    db.commit()
    return ApiResponse(message="删除成功")
