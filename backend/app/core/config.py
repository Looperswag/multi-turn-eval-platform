"""集中配置：所有可调参数从环境变量读，避免散落在代码里。"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- DB / Cache ---
    database_url: str = "postgresql+psycopg://eval:eval@localhost:5432/eval_platform"
    redis_url: str = "redis://localhost:6379/0"

    # --- API ---
    api_key: str = "dev-key-change-me"
    cors_origins: list[str] = ["http://localhost:3000"]

    # --- Judge models ---
    ark_api_key: str = ""
    ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    ark_default_model: str = "doubao-seed-2-0-pro-260215"
    ark_timeout: int = 1800

    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # --- Eval engine defaults ---
    default_judge_temperature: float = 0.1
    default_max_concurrent_requests: int = 5
    default_request_interval_sec: float = 0.5
    default_max_retries: int = 3


settings = Settings()

# 维度权重默认值（可被 DB 中 judge_prompt_version.weight 覆盖）
DEFAULT_DIMENSION_WEIGHTS = {
    "dim1": 0.30,  # 改写忠实性
    "dim2": 0.30,  # 跨轮记忆保留
    "dim3": 0.10,  # 意图边界识别
    "dim4": 0.10,  # 指代消解准确性
    "dim5": 0.10,  # 重复请求处理
    "dim6": 0.10,  # 用户纠错响应
}

DIMENSION_NAMES = {
    "dim1": "改写忠实性",
    "dim2": "跨轮记忆保留",
    "dim3": "意图边界识别",
    "dim4": "指代消解准确性",
    "dim5": "重复请求处理",
    "dim6": "用户纠错响应",
}
