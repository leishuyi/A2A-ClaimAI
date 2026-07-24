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
from app.database.session import get_db
from app.database.models import Case, Document, DocumentType
from app.schemas.case import DocumentResponse
from app.services.file_storage import get_storage_backend

router = APIRouter()

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
        raise BizError(
            code=ErrCode.VALIDATION,
            message=f"不支持的文件类型: {ext}，允许: {settings.allowed_extensions}",
        )


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
        raise BizError(
            code=ErrCode.VALIDATION,
            message=f"文件大小超过限制 ({settings.max_file_size / 1024 / 1024:.0f}MB)",
        )

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

    doc = db.query(Document).filter(Document.id == doc_id, Document.case_id == case_id).first()
    if not doc:
        raise BizError(code=ErrCode.CASE_NOT_FOUND, message="文档不存在")

    return ApiResponse(data=_doc_to_response(doc))


@router.delete("/{case_id}/documents/{doc_id}", response_model=ApiResponse)
def delete_document(case_id: int, doc_id: int, db: Session = Depends(get_db)):
    """删除影像材料"""
    _check_case_exists(case_id, db)

    doc = db.query(Document).filter(Document.id == doc_id, Document.case_id == case_id).first()
    if not doc:
        raise BizError(code=ErrCode.CASE_NOT_FOUND, message="文档不存在")

    storage = get_storage_backend()
    storage.delete(doc.file_path)

    db.delete(doc)
    db.commit()

    return ApiResponse(message="删除成功")
