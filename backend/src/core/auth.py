"""JWT 认证中间件：Token 生成、验证、用户提取"""

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings

security = HTTPBearer()


def create_access_token(user_id: str, username: str) -> str:
    """生成 JWT 访问令牌"""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {
        "sub": user_id,
        "username": username,
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    """解码并验证 JWT 令牌，返回 payload"""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌已过期",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌",
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """从请求中提取当前用户信息"""
    payload = decode_access_token(credentials.credentials)
    return {"user_id": payload["sub"], "username": payload["username"]}


async def get_current_user_flexible(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False)),
    token: str = None,
) -> dict:
    """从请求中提取当前用户信息，支持 Authorization header 和 query parameter token 两种方式"""
    raw_token = None
    if credentials and credentials.credentials:
        raw_token = credentials.credentials
    elif token:
        raw_token = token
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证信息",
        )
    payload = decode_access_token(raw_token)
    return {"user_id": payload["sub"], "username": payload["username"]}
