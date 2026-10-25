"""Multi-source insight inference and deterministic Markdown export."""
from .categories import CATEGORIES, get_category
from .audiences import AUDIENCES, get_audience
from .products import load_product_catalog
from .generation import generate_insights
from .evidence import prepare_input
from .schemas import GenerationResult, SynthesisInsightDraft
from .markdown import render_insight_markdown, render_markdown_articles, render_sources_markdown
from .export import article_outputs, save_articles

__all__ = [
    "generate_insights", "prepare_input", "GenerationResult", "SynthesisInsightDraft",
    "render_insight_markdown", "render_markdown_articles", "render_sources_markdown",
    "article_outputs", "save_articles", "CATEGORIES", "get_category",
    "AUDIENCES", "get_audience", "load_product_catalog",
]
