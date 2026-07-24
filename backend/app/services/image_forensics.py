"""图片取证 — 检测 P 图/伪造/篡改

检测手段：
1. ELA (Error Level Analysis) — 重压缩差异分析，发现局部修改区域
2. EXIF 元数据分析 — 检测编辑软件痕迹、元数据缺失
3. 统计异常检测 — 颜色分布、噪点一致性
"""
import io
import struct
from io import BytesIO
from typing import Optional

from loguru import logger
from PIL import Image, ImageChops, ImageStat


def analyze_image(file_content: bytes, filename: str = "") -> list[dict]:
    """对图片进行全面的篡改检测，返回风险标记列表"""
    findings = []
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if ext not in ("jpg", "jpeg", "png", "bmp", "tiff"):
        return []  # 非图片不检测

    try:
        img = Image.open(BytesIO(file_content))
    except Exception as e:
        logger.warning("图片解析失败", filename=filename, error=str(e))
        return [{"rule": "图片解析", "risk": "medium", "detail": "无法解析图片文件，可能已损坏或格式异常"}]

    # 1. ELA 检测
    ela_findings = _ela_analysis(img, file_content)
    findings.extend(ela_findings)

    # 2. EXIF 元数据检测
    exif_findings = _exif_analysis(img, file_content)
    findings.extend(exif_findings)

    # 3. 统计异常检测
    stat_findings = _statistical_analysis(img)
    findings.extend(stat_findings)

    img.close()
    return findings


def _ela_analysis(img: Image.Image, original: bytes, quality: int = 85) -> list[dict]:
    """ELA (Error Level Analysis) — 重压缩差异分析

    原理：将图片以固定质量重新保存，与原图逐像素比较。
    P 图区域因为已经过一次压缩，重压缩后的损失会小于原始区域。
    """
    findings = []

    try:
        # 将图片转为 RGB（处理 RGBA/调色板模式）
        if img.mode != "RGB":
            rgb_img = img.convert("RGB")
        else:
            rgb_img = img.copy()

        # 以固定质量重新保存
        buffer = BytesIO()
        rgb_img.save(buffer, format="JPEG", quality=quality)
        buffer.seek(0)
        recompressed = Image.open(buffer)

        # 计算差异
        diff = ImageChops.difference(rgb_img, recompressed)
        stat = ImageStat.Stat(diff)
        avg_diff = sum(stat.mean) / 3  # RGB 三通道平均差异
        max_diff = max(stat.extrema[0][1], stat.extrema[1][1], stat.extrema[2][1])

        buffer.close()

        # 判断篡改可能性
        if avg_diff < 0.5:
            # 差异过小：可能经过了高压缩或二次保存
            findings.append({
                "rule": "ELA 重压缩检测",
                "risk": "medium",
                "detail": f"图片重压缩差异过低({avg_diff:.2f})，疑似经过二次压缩或编辑后导出",
            })
        elif avg_diff > 8:
            # 差异过大：可能经过了局部修改
            findings.append({
                "rule": "ELA 篡改检测",
                "risk": "high",
                "detail": f"图片重压缩差异异常({avg_diff:.2f})，存在局部修改痕迹，建议人工核查",
            })

        if max_diff > 40:
            findings.append({
                "rule": "ELA 局部修改检测",
                "risk": "medium",
                "detail": f"图片局部区域差异达{max_diff:.0f}，可能存在局部PS修改",
            })

    except Exception as e:
        logger.warning("ELA 分析失败", error=str(e))

    return findings


def _exif_analysis(img: Image.Image, file_content: bytes) -> list[dict]:
    """EXIF 元数据分析 — 检测编辑软件和元数据异常"""
    findings = []
    exif_data = img._getexif() if hasattr(img, "_getexif") else None

    # EXIF 标签
    EXIF_TAGS = {
        0x010F: "相机型号",
        0x0110: "拍摄设备",
        0x0131: "拍摄软件",
        0x0132: "修改时间",
        0x9003: "拍摄日期",
        0xA002: "像素宽度",
        0xA003: "像素高度",
        0x010E: "图片描述",
        0x010D: "文档名称",
        0x0201: "缩略图偏移",
        0x0202: "缩略图长度",
    }

    SOFTWARE_EDIT_INDICATORS = [
        "photoshop", "lightroom", "gimp", "pixlr", "美图", "meitu",
        "snapseed", "picsart", "adobe", "pixelmator", "affinity",
        "canva", "fotor", "sketch", "coreldraw", "inpaint",
    ]

    if exif_data is None:
        # 无 EXIF 数据：可能是截图或经过处理
        findings.append({
            "rule": "EXIF 元数据",
            "risk": "medium",
            "detail": "图片无 EXIF 元数据，可能是截图、微信转发或经过处理",
        })
        return findings

    # 检查编辑软件
    for tag_id, tag_name in EXIF_TAGS.items():
        value = exif_data.get(tag_id)
        if value and isinstance(value, str):
            value_lower = value.lower()
            for editor in SOFTWARE_EDIT_INDICATORS:
                if editor in value_lower:
                    findings.append({
                        "rule": "EXIF 编辑痕迹",
                        "risk": "high",
                        "detail": f"图片曾使用{editor}编辑（{tag_name}: {value}），可能经过修改",
                    })
                    break

    # 检查关键 EXIF 字段
    has_camera = bool(exif_data.get(0x010F))
    has_datetime = bool(exif_data.get(0x9003) or exif_data.get(0x0132))

    if not has_camera and not has_datetime:
        findings.append({
            "rule": "EXIF 信息缺失",
            "risk": "medium",
            "detail": "图片缺少拍摄设备和拍摄时间信息，可能经过处理或非原始拍摄",
        })

    # 检测缩略图偏移异常（可能暗示缩略图被替换）
    thumbnail_offset = exif_data.get(0x0201)
    if thumbnail_offset and thumbnail_offset < 100:
        findings.append({
            "rule": "EXIF 缩略图异常",
            "risk": "medium",
            "detail": "图片缩略图偏移异常，可能经过编辑软件处理",
        })

    return findings


def _statistical_analysis(img: Image.Image) -> list[dict]:
    """统计异常检测 — 颜色分布、噪点一致性"""
    findings = []

    try:
        if img.mode != "RGB":
            rgb_img = img.convert("RGB")
        else:
            rgb_img = img

        stat = ImageStat.Stat(rgb_img)
        width, height = rgb_img.size

        # 1. 颜色通道一致性检测
        r, g, b = stat.mean
        # 如果 RGB 完全相等说明是灰度图
        color_diff = max(abs(r - g), abs(g - b), abs(b - r))
        if color_diff < 2 and width > 100 and height > 100:
            findings.append({
                "rule": "颜色异常",
                "risk": "medium",
                "detail": "图片颜色通道几乎一致，可能是黑白扫描件或经过滤镜处理",
            })

        # 2. 尺寸异常检测
        if width > 5000 or height > 5000:
            findings.append({
                "rule": "图片超大",
                "risk": "low",
                "detail": f"图片分辨率({width}×{height})超出常规扫描件范围",
            })

        # 3. 纯色背景检测（可能为截图）
        pixels = rgb_img.getdata()
        total = len(pixels)
        # 检查是否有大量完全相同的像素（纯色区域）
        if total > 1000:
            from collections import Counter
            color_counts = Counter(pixels)
            most_common_count = color_counts.most_common(1)[0][1]
            bg_ratio = most_common_count / total
            if bg_ratio > 0.4:
                findings.append({
                    "rule": "纯色背景",
                    "risk": "low",
                    "detail": f"图片纯色区域占比{bg_ratio:.0%}，可能是截图或电子文档翻拍",
                })

    except Exception as e:
        logger.warning("统计分析失败", error=str(e))

    return findings


def has_tampering_risk(findings: list[dict]) -> tuple[bool, str, str]:
    """综合判断是否存在篡改风险"""
    high_risk = [f for f in findings if f["risk"] == "high"]
    medium_risk = [f for f in findings if f["risk"] == "medium"]

    if high_risk:
        return True, "high", f"发现{len(high_risk)}项高风险篡改迹象: {'; '.join(f['detail'][:30] for f in high_risk)}"
    if medium_risk and len(medium_risk) >= 2:
        return True, "medium", f"发现{len(medium_risk)}项中风险异常: {'; '.join(f['detail'][:30] for f in medium_risk)}"
    return False, "low", "图片未发现明显篡改痕迹"
