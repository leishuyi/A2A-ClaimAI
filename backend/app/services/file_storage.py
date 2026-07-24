"""文件存储服务

参考 grid-qa 模式：
- 抽象 StorageBackend 接口，支持本地文件系统/MinIO 切换
- 路径组织: {upload_dir}/{case_id}/{filename}
"""
import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from urllib.parse import quote

from app.config import settings


class StorageBackend(ABC):
    """存储后端抽象接口"""

    @abstractmethod
    def save(self, file_content: bytes, relative_path: str) -> str:
        """保存文件，返回存储路径"""

    @abstractmethod
    def get(self, relative_path: str) -> bytes | None:
        """读取文件内容"""

    @abstractmethod
    def delete(self, relative_path: str) -> bool:
        """删除文件"""

    @abstractmethod
    def get_url(self, relative_path: str) -> str:
        """获取文件访问 URL"""


class LocalStorage(StorageBackend):
    """本地文件系统存储"""

    def __init__(self, base_dir: str = ""):
        self.base_dir = Path(base_dir or settings.upload_dir).resolve()

    def _full_path(self, relative_path: str) -> Path:
        # 防止路径穿越
        safe = Path(relative_path).as_posix().lstrip("/")
        full = self.base_dir / safe
        full = full.resolve()
        if not str(full).startswith(str(self.base_dir)):
            raise ValueError("非法路径访问")
        return full

    def save(self, file_content: bytes, relative_path: str) -> str:
        full = self._full_path(relative_path)
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(file_content)
        return relative_path

    def get(self, relative_path: str) -> bytes | None:
        full = self._full_path(relative_path)
        if not full.exists():
            return None
        return full.read_bytes()

    def delete(self, relative_path: str) -> bool:
        full = self._full_path(relative_path)
        if not full.exists():
            return False
        full.unlink(missing_ok=True)
        return True

    def get_url(self, relative_path: str) -> str:
        return f"/uploads/{quote(relative_path)}"


def get_storage_backend() -> StorageBackend:
    """工厂函数：根据配置返回对应的存储后端"""
    return LocalStorage()
