"""应用配置管理"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置，从环境变量加载"""

    # MongoDB
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_database: str = "novel_db"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # JWT
    secret_key: str = "change-this-to-a-random-secret-key"
    access_token_expire_minutes: int = 1440

    # LLM - 支持多个 provider
    # provider: vllm / deepseek / minimax / minimax2.7 / openai
    llm_provider: str = "vllm"
    llm_api_key: str = "EMPTY"
    llm_model: str = "Qwen/Qwen2.5-72B-Instruct"
    llm_base_url: str = "http://localhost:8000/v1"

    # FAISS
    faiss_index_path: str = "./faiss_indexes"

    # LangSmith
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""

    # 服务端口（避免与 vLLM 8000 冲突）
    server_port: int = 8080

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
