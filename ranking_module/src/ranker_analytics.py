"""Analytics ranker: match 2-5 news set against analytics (pdf) pool."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .config import AppConfig
from .embeddings import BiEncoder, CrossEncoder, analytics_text, news_text
from .features import news_signals
from .ranker_news import _load_faiss, _load_ids

log = logging.getLogger(__name__)


@dataclass
class AnalyticsCandidate:
    item_id: str
    score_dense: float = 0.0
    score_cross: float = 0.0
    score_profile: float = 0.0
    score_total: float = 0.0
    provenance: list[str] = field(default_factory=list)


def _build_set_query(news_set: list[Any], cfg: AppConfig) -> tuple[str, np.ndarray | None]:
    tpl = cfg.embeddings.text_templates
    texts = [news_text(n, tpl) for n in news_set]
    if cfg.analytics.aggregation == "concat":
        return tpl.news_set_concat_sep.join(texts), None
    return " ".join(texts), None


def _set_signals(news_set: list[Any]):
    sectors, regions, products = set(), set(), set()
    for n in news_set:
        s = news_signals(n)
        sectors |= s.sectors
        regions |= s.regions
        products |= s.products
    return sectors, regions, products


def rank_analytics(
    news_set: list[Any],
    analytics_pool: list[Any],
    cfg: AppConfig,
    encoder: BiEncoder | None = None,
    cross: CrossEncoder | None = None,
    top_k: int | None = None,
) -> list[AnalyticsCandidate]:
    if not news_set or not analytics_pool:
        return []
    enc = encoder or BiEncoder(cfg.embeddings, device=cfg.runtime.device)
    crs = cross or CrossEncoder(cfg.embeddings, device=cfg.runtime.device)

    analytics_by_id = {getattr(it, "item_id", None): it for it in analytics_pool if getattr(it, "item_id", None)}
    query_text, _ = _build_set_query(news_set, cfg)

    # dense
    import faiss
    index = _load_faiss(cfg.paths.analytics_cache)
    ids = _load_ids(cfg.paths.analytics_cache)
    cands: list[AnalyticsCandidate] = []
    if index is not None and ids:
        q = enc.encode_queries([query_text])
        k = min(top_k or cfg.recall.top_k_dense, index.ntotal)
        scores, idxs = index.search(q, k)
        for sc, ix in zip(scores[0], idxs[0]):
            if ix < 0:
                continue
            item_id = ids[int(ix)].get("item_id")
            if item_id:
                cands.append(AnalyticsCandidate(item_id=item_id, score_dense=float(sc)))
    if not cands:
        cands = [AnalyticsCandidate(item_id=iid) for iid in analytics_by_id]

    # cross
    tpl = cfg.embeddings.text_templates
    pairs, valid = [], []
    for c in cands:
        it = analytics_by_id.get(c.item_id)
        if it is None:
            continue
        pairs.append((query_text, analytics_text(it, tpl)))
        valid.append(c)
    if pairs:
        scores = crs.score_pairs(pairs)
        for c, sc in zip(valid, scores.tolist()):
            c.score_cross = float(sc)
        cands = sorted(valid, key=lambda c: -c.score_cross)[: cfg.recall.top_k_cross]

    # profile boost
    if cfg.analytics.profile_boost.enabled:
        sec, reg, prod = _set_signals(news_set)
        w = cfg.analytics.profile_boost.weights
        for c in cands:
            it = analytics_by_id.get(c.item_id)
            if it is None:
                continue
            s = news_signals(it)
            contrib = 0.0
            prov: list[str] = []
            if sec & s.sectors:
                contrib += w.get("okved_sector", 0.0)
                prov.append("sector")
            if reg & s.regions:
                contrib += w.get("region", 0.0)
                prov.append("region")
            if prod & s.products:
                contrib += w.get("products", 0.0)
                prov.append("products")
            c.score_profile = contrib
            c.provenance = prov

    for c in cands:
        c.score_total = 0.5 * c.score_dense + 0.5 * c.score_cross + c.score_profile

    cands.sort(key=lambda c: -c.score_total)
    return cands[: (top_k or cfg.analytics.max_count)]