"""日志配置：基于 loguru 的双输出（控制台 + 滚动文件）。

参考 grid-qa 的 logging.py 模式。
"""
import sys
from pathlib import Path

from loguru import logger

from app.config import settings


def setup_logging():
    """初始化 loguru 日志：控制台 INFO + 滚动文件"""
    logger.remove()

    # 控制台输出
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <7}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        enqueue=True,
    )

    # 滚动文件输出
    log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        str(log_dir / "app.log"),
        rotation=settings.log_rotation,
        retention=settings.log_retention,
        level=settings.log_level,
        encoding="utf-8",
        enqueue=True,
    )

    logger.info("日志初始化完成", rotation=settings.log_rotation, retention=settings.log_retention)
