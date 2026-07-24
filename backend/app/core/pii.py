"""PII 数据脱敏工具

支持：姓名、身份证号、银行卡号、手机号、发票号等敏感信息脱敏。
"""
import re


def mask_name(name: str | None) -> str | None:
    """姓名脱敏：张 → 张，张三 → 张*，张三丰 → 张**"""
    if not name:
        return name
    if len(name) == 1:
        return name
    return name[0] + "*" * (len(name) - 1)


def mask_id_card(id_card: str | None) -> str | None:
    """身份证号脱敏：110101199001011234 → 110101****1234"""
    if not id_card or len(id_card) < 8:
        return id_card
    return id_card[:6] + "****" + id_card[-4:]


def mask_phone(phone: str | None) -> str | None:
    """手机号脱敏：13800138000 → 138****8000"""
    if not phone or len(phone) < 7:
        return phone
    return phone[:3] + "****" + phone[-4:]


def mask_invoice_no(invoice_no: str | None) -> str | None:
    """发票号脱敏：INV202407001 → INV2024****"""
    if not invoice_no or len(invoice_no) < 6:
        return invoice_no
    return invoice_no[:-4] + "****"


def mask_text(text: str | None, keep_left: int = 0, keep_right: int = 4) -> str | None:
    """通用文本脱敏：保留首尾指定长度，中间用 **** 替代"""
    if not text:
        return text
    if len(text) <= keep_left + keep_right:
        return text
    return text[:keep_left] + "****" + text[-keep_right:]


def should_mask() -> bool:
    """根据配置判断是否需要脱敏"""
    try:
        from app.config import settings
        return settings.pii_mask_enabled
    except Exception:
        return True
