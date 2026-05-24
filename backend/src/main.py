"""FastAPI 应用入口：CORS、路由注册、异常处理、启动事件"""

import time
from contextlib import asynccontextmanager

import jwt
from bson import ObjectId
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .core.config import settings
from .core.database import close_database, get_mongodb
from .core.llm import set_current_llm_config
from .utils.logger import get_logger, log_request, log_response

logger = get_logger(__name__)
secret_key = settings.secret_key


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("AI小说生成系统启动")

    # 启动时加载 Skills 校验模块，确认可用
    try:
        from .validators.skill_loader import load_all_skills
        import os
        skills_dir = os.path.join(os.path.dirname(__file__), "validators", "skills")
        skills = load_all_skills(skills_dir)
        logger.info(f"[Skills] 加载 {len(skills)} 个校验 Skill:")
        for s in skills:
            logger.info(
                f"  [{s.priority}] {s.name} | check_method={s.check_method} "
                f"| failure={s.failure} | items={len(s.check_items)}"
            )
    except Exception as e:
        logger.warning(f"[Skills] 校验 Skill 加载失败，将回退到旧审计: {e}")

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
from .api.model_config import router as model_config_router  # noqa: E402
from .api.novel import router as novel_router  # noqa: E402
from .api.prompt import router as prompt_router  # noqa: E402

app.include_router(auth_router, prefix="/api/auth", tags=["认证"])
app.include_router(novel_router, prefix="/api/novel", tags=["小说项目"])
app.include_router(creation_router, prefix="/api/novel", tags=["创作控制"])
app.include_router(chapter_router, prefix="/api/chapter", tags=["章节管理"])
app.include_router(export_router, prefix="/api/novel", tags=["导出"])
app.include_router(model_config_router, prefix="/api/model-configs", tags=["模型配置"])
app.include_router(prompt_router, prefix="/api/prompts", tags=["Prompt管理"])


@app.middleware("http")
async def llm_config_middleware(request: Request, call_next):
    """从 JWT 提取用户活跃模型配置，注入 context var"""
    if request.url.path in ("/", "/docs", "/openapi.json", "/redoc"):
        return await call_next(request)

    try:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                payload = jwt.decode(token, secret_key, algorithms=["HS256"])
            except Exception:
                payload = None

            if payload:
                user_id = payload["sub"]
                db = await get_mongodb()
                user_doc = await db["users"].find_one({"_id": ObjectId(user_id)})
                if user_doc and user_doc.get("active_model_config_id"):
                    config = await db["model_configs"].find_one({
                        "_id": ObjectId(user_doc["active_model_config_id"]),
                        "user_id": user_id,
                    })
                    if config and config.get("api_key"):
                        set_current_llm_config({
                            "provider": config.get("provider", "openai"),
                            "model": config["model"],
                            "api_key": config["api_key"],
                            "base_url": config.get("base_url", ""),
                            "max_tokens": config.get("max_tokens", 8192),
                        })
    except Exception:
        pass  # 回退到全局配置

    response = await call_next(request)
    return response


@app.get("/")
async def root():
    return {"message": "AI长篇小说自动生成系统 API"}
