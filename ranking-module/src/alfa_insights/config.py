"""Configuration loading and validation."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class PathsConfig(BaseModel):
    root: Path = Path(".")
    data_dir: Path = Path("data")
    cache_dir: Path = Path("cache")
    runs_dir: Path = Path("runs")
    models_dir: Path = Path("models")
    companies: Path = Path("data/companies.csv")
    news_cache: Path = Path("cache/news")
    analytics_cache: Path = Path("cache/analytics")

    def resolve(self) -> "PathsConfig":
        root = self.root.resolve()
        def _p(p: Path) -> Path:
            return p if p.is_absolute() else (root / p)
        return PathsConfig(
            root=root,
            data_dir=_p(self.data_dir),
            cache_dir=_p(self.cache_dir),
            runs_dir=_p(self.runs_dir),
            models_dir=_p(self.models_dir),
            companies=_p(self.companies),
            news_cache=_p(self.news_cache),
            analytics_cache=_p(self.analytics_cache),
        )


class RuntimeConfig(BaseModel):
    device: str = "cpu"
    seed: int = 42
    deterministic: bool = True
    log_level: str = "INFO"
    log_json: bool = True


class BiEncoderConfig(BaseModel):
    model_name: str = "intfloat/multilingual-e5-small"
    normalize: bool = True
    batch_size: int = 64
    max_length: int = 512
    query_prefix: str = "query: "
    doc_prefix: str = "passage: "


class CrossEncoderConfig(BaseModel):
    model_name: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
    batch_size: int = 32
    max_length: int = 512


class TextTemplatesConfig(BaseModel):
    news: str = "{title}\n{text}"
    analytics: str = "{title}\n{text}"
    company: str = "{name} | {okved_name} | {region} | {city} | {specialization}"
    news_set_concat_sep: str = "\n\n---\n\n"


class EmbeddingsConfig(BaseModel):
    bi_encoder: BiEncoderConfig = Field(default_factory=BiEncoderConfig)
    cross_encoder: CrossEncoderConfig = Field(default_factory=CrossEncoderConfig)
    text_templates: TextTemplatesConfig = Field(default_factory=TextTemplatesConfig)


class IvfConfig(BaseModel):
    nlist: int = 256
    nprobe: int = 16


class HnswConfig(BaseModel):
    M: int = 32
    efConstruction: int = 200
    efSearch: int = 64


class FaissConfig(BaseModel):
    index_type: str = "flat"
    metric: str = "ip"
    ivf: IvfConfig = Field(default_factory=IvfConfig)
    hnsw: HnswConfig = Field(default_factory=HnswConfig)

    @field_validator("index_type")
    @classmethod
    def _check_index_type(cls, v: str) -> str:
        if v not in {"flat", "ivf", "hnsw"}:
            raise ValueError(f"unsupported index_type: {v}")
        return v


class RecallConfig(BaseModel):
    top_k_dense: int = 100
    top_k_cross: int = 20
    min_cross_score: float = 0.0


class PrimaryHardRecallConfig(BaseModel):
    score_boost: float = 1.0
    match_types: list[str] = Field(default_factory=lambda: ["name_mention", "alias_mention", "domain_mention"])
    use_watchlist: bool = True
    filter_enabled: bool = True
    use_company_profile: bool = True


class FallbackHardRecallConfig(BaseModel):
    enabled: bool = True
    min_score: float = 0.35
    weights: dict[str, float] = Field(
        default_factory=lambda: {
            "okved_sector": 0.30,
            "region": 0.20,
            "city": 0.05,
            "worker_ord": 0.10,
            "binary_sum_products": 0.10,
            "industry_freq": 0.10,
            "revenue_rank_industry": 0.15,
        }
    )
    require_any_of: list[str] = Field(default_factory=lambda: ["okved_sector", "region"])


class HardRecallConfig(BaseModel):
    enabled: bool = True
    primary: PrimaryHardRecallConfig = Field(default_factory=PrimaryHardRecallConfig)
    fallback: FallbackHardRecallConfig = Field(default_factory=FallbackHardRecallConfig)


class RankingWeightsConfig(BaseModel):
    dense: float = 0.4
    cross: float = 0.4
    hard: float = 0.2


class RankingConfig(BaseModel):
    weights: RankingWeightsConfig = Field(default_factory=RankingWeightsConfig)
    guarantee_hard_primary_in_top: bool = True


class AnalyticsProfileBoostConfig(BaseModel):
    enabled: bool = True
    weights: dict[str, float] = Field(
        default_factory=lambda: {"okved_sector": 0.5, "region": 0.3, "products": 0.2}
    )


class AnalyticsConfig(BaseModel):
    top_k: int = 3
    min_count: int = 1
    max_count: int = 3
    aggregation: str = "concat"
    profile_boost: AnalyticsProfileBoostConfig = Field(default_factory=AnalyticsProfileBoostConfig)

    @field_validator("aggregation")
    @classmethod
    def _check_agg(cls, v: str) -> str:
        if v not in {"concat", "mean_emb"}:
            raise ValueError(f"unsupported aggregation: {v}")
        return v


class SetsConfig(BaseModel):
    min_news: int = 2
    max_news: int = 5
    min_analytics: int = 1
    max_analytics: int = 3
    max_sets: int = 10
    min_set_score: float = 0.0
    strategy: str = "per_company_topk"
    dedup_by: list[str] = Field(default_factory=lambda: ["company_id", "news_ids"])
    roles_allowed: list[str] = Field(default_factory=lambda: ["primary", "competitor"])

    @model_validator(mode="after")
    def _check_ranges(self) -> "SetsConfig":
        if self.min_news > self.max_news:
            raise ValueError("sets.min_news > sets.max_news")
        if self.min_analytics > self.max_analytics:
            raise ValueError("sets.min_analytics > sets.max_analytics")
        if self.min_news > self.max_news:
            raise ValueError("invalid news range")
        return self


class IOConfig(BaseModel):
    strict_validation: bool = True
    drop_competitors_duplicates: bool = True
    result_schema_version: str = "1.0"


class FeaturesConfig(BaseModel):
    force_recompute: bool = False
    okved_sector_map: dict[str, list[int]] = Field(
        default_factory=lambda: {
            "trade": [45, 46, 47],
            "manufacturing": list(range(5, 34)),
            "construction": [41, 42, 43],
            "finance": [64, 65, 66],
            "real_estate": [68],
        }
    )
    age_ord_thresholds: list[int] = Field(default_factory=lambda: [3, 5, 10, 20])


class AppConfig(BaseModel):
    schema_version: str = "1.0"
    paths: PathsConfig = Field(default_factory=PathsConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    embeddings: EmbeddingsConfig = Field(default_factory=EmbeddingsConfig)
    faiss: FaissConfig = Field(default_factory=FaissConfig)
    recall: RecallConfig = Field(default_factory=RecallConfig)
    hard_recall: HardRecallConfig = Field(default_factory=HardRecallConfig)
    ranking: RankingConfig = Field(default_factory=RankingConfig)
    analytics: AnalyticsConfig = Field(default_factory=AnalyticsConfig)
    sets: SetsConfig = Field(default_factory=SetsConfig)
    io: IOConfig = Field(default_factory=IOConfig)
    features: FeaturesConfig = Field(default_factory=FeaturesConfig)

    def resolve_paths(self) -> "AppConfig":
        return self.model_copy(update={"paths": self.paths.resolve()})


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: str | Path = "config.yaml", overrides: dict[str, Any] | None = None) -> AppConfig:
    """Load config from YAML, apply overrides and environment variables."""
    cfg_path = Path(path)
    raw: dict[str, Any] = {}
    if cfg_path.exists():
        with cfg_path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

    env_overrides: dict[str, Any] = {}
    if os.getenv("ALFA_DEVICE"):
        env_overrides.setdefault("runtime", {})["device"] = os.environ["ALFA_DEVICE"]
    if os.getenv("ALFA_LOG_LEVEL"):
        env_overrides.setdefault("runtime", {})["log_level"] = os.environ["ALFA_LOG_LEVEL"]

    merged = _deep_merge(raw, env_overrides)
    if overrides:
        merged = _deep_merge(merged, overrides)

    cfg = AppConfig.model_validate(merged).resolve_paths()
    for d in (cfg.paths.cache_dir, cfg.paths.runs_dir, cfg.paths.news_cache, cfg.paths.analytics_cache):
        d.mkdir(parents=True, exist_ok=True)
    return cfg