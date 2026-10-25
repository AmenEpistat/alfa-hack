"""Build embeddings for news and analytics (pdf) topics."""

from __future__ import annotations

import argparse
import logging

from alfa_insights.config import load_config
from alfa_insights.data import load_ranking_input
from alfa_insights.embeddings import BiEncoder, EmbeddingStore, analytics_text, news_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("build_embeddings")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--input", required=True, help="ranking_input json path")
    ap.add_argument("--topics", default="news,analytics")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    cfg = load_config(args.config)
    payload = load_ranking_input(args.input)
    topics = {t.strip() for t in args.topics.split(",")}

    encoder = BiEncoder(cfg.embeddings, device=cfg.runtime.device)

    if "news" in topics:
        store = EmbeddingStore(cfg.paths.news_cache, cfg.embeddings.bi_encoder.model_name, "news")
        items = list(payload.topics.news) + list(payload.topics.competitors)
        store.build_or_load(
            items,
            encoder,
            lambda it: news_text(it, cfg.embeddings.text_templates),
            force=args.force,
        )
        log.info("news embeddings ready: %d", len(items))

    if "analytics" in topics:
        store = EmbeddingStore(
            cfg.paths.analytics_cache, cfg.embeddings.bi_encoder.model_name, "analytics"
        )
        items = list(payload.topics.pdf)
        store.build_or_load(
            items,
            encoder,
            lambda it: analytics_text(it, cfg.embeddings.text_templates),
            force=args.force,
        )
        log.info("analytics embeddings ready: %d", len(items))


if __name__ == "__main__":
    main()
