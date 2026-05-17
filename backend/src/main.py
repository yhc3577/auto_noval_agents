"""FastAPI 应用入口：CORS、路由注册、异常处理、启动事件"""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .core.database import close_database
from .utils.logger import get_logger, log_request, log_response

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("AI小说生成系统启动")
    yield
    logger.info("AI小说生成系统关闭")
    await close_database()


app = FastAPI(
    title="AI长篇小说自动生成系统",
    description="基于LangGraph 6Agent的全自动小说创作系统",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """请求日志中间件：记录请求和响应"""
    # 跳过健康检查和文档
    if request.url.path in ("/", "/docs", "/openapi.json", "/redoc"):
        return await call_next(request)

    # 记录请求
    method = request.method
    path = request.url.path
    query_params = dict(request.query_params)
    client_ip = request.client.host if request.client else "unknown"

    # 获取请求体（仅对 POST/PUT）
    body = None
    if method in ("POST", "PUT", "PATCH"):
        try:
            body_bytes = await request.body()
            if body_bytes:
                body = body_bytes.decode("utf-8")[:1000]  # 限制长度
        except Exception:
            pass

    log_request(
        logger,
        method=method,
        path=path,
        query_params=query_params if query_params else None,
        client_ip=client_ip,
        body=body,
    )

    # 记录响应
    start_time = time.time()
    try:
        response = await call_next(request)
        duration = time.time() - start_time
        log_response(logger, method=method, path=path, status_code=response.status_code, duration=duration)
        return response
    except Exception as e:
        duration = time.time() - start_time
        log_response(logger, method=method, path=path, status_code=500, duration=duration, error=str(e))
        raise


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器"""
    logger.error(f"未处理的异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误，请稍后重试"},
    )


# 注册路由
from .api.auth import router as auth_router  # noqa: E402
from .api.chapter import router as chapter_router  # noqa: E402
from .api.creation import router as creation_router  # noqa: E402
from .api.export import router as export_router  # noqa: E402
from .api.novel import router as novel_router  # noqa: E402

app.include_router(auth_router, prefix="/api/auth", tags=["认证"])
app.include_router(novel_router, prefix="/api/novel", tags=["小说项目"])
app.include_router(creation_router, prefix="/api/novel", tags=["创作控制"])
app.include_router(chapter_router, prefix="/api/chapter", tags=["章节管理"])
app.include_router(export_router, prefix="/api/novel", tags=["导出"])


@app.get("/")
async def root():
    return {"message": "AI长篇小说自动生成系统 API"}
