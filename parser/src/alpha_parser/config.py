from pathlib import Path
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ALPHA_", env_file=".env", env_ignore_empty=True, extra="ignore")
    data_dir: Path = Path("../output/runs")
    input_dir: Path = Path("inputs")
    config_dir: Path = Path("config")
    llm_base_url: str = ""
    llm_fallback_base_url: str = ""
    llm_api_key: str = Field("", repr=False, exclude=True)
    llm_model: str = ""
    llm_family: str = "GLM-5.3-Flash"
    llm_timeout: float = Field(45, gt=0, le=180)
    llm_connect_timeout: float = Field(5, gt=0, le=30)
    llm_max_output_tokens: int = Field(1536, ge=512, le=4096)
    llm_reasoning_effort: Literal["low", "high", "max"] = "low"
    llm_thinking_protocol: Literal["legacy", "openrouter"] = "legacy"
    llm_thinking_mode: Literal["default", "instant", "minimal"] = "default"
    llm_length_retries: int = Field(1, ge=0, le=1)
    llm_extra_body: dict = Field(default_factory=dict)
    searxng_url: str = ""
    input_rub_per_million: float | None = Field(None, ge=0)
    output_rub_per_million: float | None = Field(None, ge=0)
    daily_budget_rub: float = Field(500, gt=0)
    allow_unknown_cost: bool = False
    max_steps: int = Field(8, ge=1, le=30)
    max_pages: int = Field(6, ge=1, le=30)
    max_requests: int = Field(18, ge=1, le=100)
    max_tokens: int = Field(12000, ge=512, le=50000)
    browser_fallback: bool = False
    search_cache_ttl: int = Field(3600, ge=0, le=86400)
    article_cache_ttl: int = Field(86400, ge=0, le=604800)
    peer_cache_ttl: int = Field(604800, ge=0, le=2592000)
    insight_cache_ttl: int = Field(86400, ge=0, le=604800)
    http_timeout: float = 20
    max_response_bytes: int = 8_000_000
    request_delay: float = 0.5
    ocr_enabled: bool = True
    tessdata: Path = Path("data/tessdata")
    ocr_language: str = "rus+eng"
    ocr_dpi: int = Field(200, ge=100, le=300)

