"""结构化日志工具：JSON 格式业务日志，支持文件输出"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path


# 日志目录配置
LOG_DIR = Path("/var/log/novel")
if not LOG_DIR.exists():
    # 如果 /var/log/novel 不存在，使用项目目录下的 logs
    LOG_DIR = Path(__file__).parent.parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


class JSONFormatter(logging.Formatter):
    """JSON 格式化器，输出结构化日志"""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            log_data["exception"] = str(record.exc_info[1])
            log_data["traceback"] = self.formatException(record.exc_info)
        # 支持附加字段
        if hasattr(record, "extra_data"):
            log_data["data"] = record.extra_data
        return json.dumps(log_data, ensure_ascii=False)


class ConsoleFormatter(logging.Formatter):
    """控制台格式化器，输出可读日志"""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        level = record.levelname
        name = record.name
        message = record.getMessage()
        return f"[{timestamp}] [{level}] [{name}] {message}"


def get_logger(name: str) -> logging.Logger:
    """获取结构化日志器，同时输出到控制台和文件"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(ConsoleFormatter())
        console_handler.setLevel(logging.INFO)

        # 应用日志文件处理器（按大小轮转）
        app_log_file = LOG_DIR / "app.log"
        file_handler = RotatingFileHandler(
            app_log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(JSONFormatter())
        file_handler.setLevel(logging.INFO)

        # 错误日志文件处理器
        error_log_file = LOG_DIR / "error.log"
        error_handler = RotatingFileHandler(
            error_log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8",
        )
        error_handler.setFormatter(JSONFormatter())
        error_handler.setLevel(logging.ERROR)

        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        logger.addHandler(error_handler)
        logger.setLevel(logging.INFO)

    return logger


def log_business(logger: logging.Logger, message: str, **kwargs):
    """记录业务日志，支持附加数据"""
    extra = {"extra_data": kwargs} if kwargs else {}
    logger.info(message, extra=extra)


def log_request(logger: logging.Logger, method: str, path: str, **kwargs):
    """记录请求日志"""
    extra = {"extra_data": {"method": method, "path": path, **kwargs}} if kwargs else {"extra_data": {"method": method, "path": path}}
    logger.info(f"请求 {method} {path}", extra=extra)


def log_response(logger: logging.Logger, method: str, path: str, status_code: int, duration: float, **kwargs):
    """记录响应日志"""
    extra = {"extra_data": {"method": method, "path": path, "status_code": status_code, "duration_ms": round(duration * 1000, 2), **kwargs}}
    logger.info(f"响应 {method} {path} {status_code} ({duration:.3f}s)", extra=extra)
