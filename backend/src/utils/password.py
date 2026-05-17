"""密码哈希工具：bcrypt 加密和验证"""

import bcrypt


def hash_password(password: str) -> str:
    """对密码进行 bcrypt 哈希"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """验证密码是否匹配哈希值"""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
