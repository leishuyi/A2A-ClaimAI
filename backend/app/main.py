"""A2A 智能理赔助手 — 应用入口

参考 grid-qa 的架构模式：
- async lifespan 生命周期管理
- BizError 统一异常处理（HTTP 200 + 业务码）
- loguru 结构化日志
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.config import settings
from app.core.log import setup_logging
from app.core.response import ApiResponse, BizError
from app.database.session import engine, Base
from app.routers import cases, agents, human_gate, documents


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化 DB 和子系统，关闭时清理资源。"""
    # ---- Startup ----
    setup_logging()
    logger.info("应用启动", app_name=settings.app_name, env=settings.app_env)

    Base.metadata.create_all(bind=engine)
    logger.info("数据库表初始化完成")

    if settings.feature_event_bus:
        from app.events import event_bus
        logger.info("事件总线已就绪")

    yield

    # ---- Shutdown ----
    logger.info("应用关闭")


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
)

# ---- 中间件 ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- 全局异常处理器 ----
@app.exception_handler(BizError)
async def biz_error_handler(request: Request, exc: BizError):
    """业务异常：始终返回 HTTP 200，错误信息在 code/message 中。"""
    return JSONResponse(
        status_code=200,
        content=ApiResponse(code=exc.code, message=exc.message, data=exc.data).model_dump(),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """未预期的异常兜底。"""
    logger.opt(exception=exc).error("未捕获异常", url=str(request.url))
    return JSONResponse(
        status_code=200,
        content=ApiResponse(code=50000, message="服务器内部错误").model_dump(),
    )


# ---- 静态文件服务（上传的影像材料） ----
import os
os.makedirs(settings.upload_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")

# ---- 路由 ----
app.include_router(cases.router, prefix=f"{settings.api_prefix}/cases", tags=["cases"])
app.include_router(agents.router, prefix=f"{settings.api_prefix}/cases", tags=["agents"])
app.include_router(human_gate.router, prefix=f"{settings.api_prefix}/cases", tags=["human_gate"])
app.include_router(documents.router, prefix=f"{settings.api_prefix}/cases", tags=["documents"])


@app.get(f"{settings.api_prefix}/health")
def health():
    return {"status": "ok", "service": settings.app_name, "env": settings.app_env}
