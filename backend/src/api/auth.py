"""认证接口：用户注册和登录"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ..core.auth import create_access_token
from ..core.database import get_mongodb
from ..utils.logger import get_logger
from ..utils.password import hash_password, verify_password

logger = get_logger(__name__)
router = APIRouter()


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=20)
    password: str = Field(..., min_length=6, max_length=50)


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    id: str
    username: str
    token: str


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(req: RegisterRequest):
    """注册新用户"""
    db = await get_mongodb()
    users = db["users"]

    # 检查用户名是否已存在
    existing = await users.find_one({"username": req.username})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名已存在",
        )

    # 创建用户
    user_doc = {
        "username": req.username,
        "password_hash": hash_password(req.password),
    }
    result = await users.insert_one(user_doc)

    user_id = str(result.inserted_id)
    token = create_access_token(user_id, req.username)
    logger.info(f"用户注册成功: {req.username}")

    return AuthResponse(id=user_id, username=req.username, token=token)


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    """用户登录"""
    db = await get_mongodb()
    users = db["users"]

    user = await users.find_one({"username": req.username})
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    user_id = str(user["_id"])
    token = create_access_token(user_id, req.username)
    logger.info(f"用户登录成功: {req.username}")

    return AuthResponse(id=user_id, username=req.username, token=token)
