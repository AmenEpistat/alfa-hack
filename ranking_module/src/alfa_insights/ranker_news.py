"""News ranker: dense recall (FAISS) -> cross-encoder -> hard recall."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import AppConfig
from .embeddings import BiEncoder, CrossEncoder, company_text, news_text
from .features import CompanyProfile, news_signals

log = logging.getLogger(__name__)


@dataclass
class NewsCandidate:
    item_id: str
    score_dense: float = 0.0
    score_cross: float = 0.0
    score_hard: float = 0.0
    score_total: float = 0.0
    provenance: list[str] = field(default_factory=list)


def _load_faiss(cache_dir: Path):
    import faiss

    path = cache_dir / "faiss.index"
    if not path.exists():
        return None
    return faiss.read_index(str(path))


def _load_ids(cache_dir: Path) -> list[dict[str, Any]]:
    p = cache_dir / "ids.json"
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8")).get("ids", [])


def dense_recall(
    query_text: str,
    encoder: BiEncoder,
    cfg: AppConfig,
    top_k: int | None = None,
) -> list[tuple[str, float]]:
    """FAISS top-k over news index. Returns (item_id, score)."""

    index = _load_faiss(cfg.paths.news_cache)
    ids = _load_ids(cfg.paths.news_cache)
    if index is None or not ids:
        return []
    q = encoder.encode_queries([query_text])
    k = min(top_k or cfg.recall.top_k_dense, index.ntotal)
    scores, idxs = index.search(q, k)
    out: list[tuple[str, float]] = []
    for sc, ix in zip(scores[0], idxs[0]):
        if ix < 0:
            continue
        item_id = ids[int(ix)].get("item_id")
        if item_id:
            out.append((item_id, float(sc)))
    return out


def cross_rerank(
    query_text: str,
    candidates: list[NewsCandidate],
    news_by_id: dict[str, Any],
    cross: CrossEncoder,
    cfg: AppConfig,
    top_k: int | None = None,
) -> list[NewsCandidate]:
    pairs: list[tuple[str, str]] = []
    valid: list[NewsCandidate] = []
    for c in candidates:
        item = news_by_id.get(c.item_id)
        if item is None:
            continue
        pairs.append((query_text, news_text(item, cfg.embeddings.text_templates)))
        valid.append(c)
    scores = cross.score_pairs(pairs)
    scored = sorted(zip(valid, scores.tolist()), key=lambda x: -x[1])
    k = top_k or cfg.recall.top_k_cross
    out: list[NewsCandidate] = []
    for c, sc in scored[:k]:
        if sc < cfg.recall.min_cross_score:
            continue
        c.score_cross = float(sc)
        out.append(c)
    return out


def hard_recall(
    candidates: list[NewsCandidate],
    profile: CompanyProfile,
    watch_items: list[Any],
    news_by_id: dict[str, Any],
    cfg: AppConfig,
) -> list[NewsCandidate]:
    """Hard recall: primary name/alias/domain match, fallback by feature combo."""
    if not cfg.hard_recall.enabled:
        return candidates

    watch_names = {w.name.lower() for w in watch_items if w.name}
    watch_aliases = {a.lower() for w in watch_items for a in (w.aliases or [])}
    watch_domains = {(w.domain or "").lower() for w in watch_items if w.domain}
    if profile.name:
        watch_names.add(profile.name.lower())
    for a in profile.aliases or []:
        watch_aliases.add(a.lower())
    if profile.domain:
        watch_domains.add(profile.domain.lower())

    primary_cfg = cfg.hard_recall.primary
    fb_cfg = cfg.hard_recall.fallback

    for c in candidates:
        item = news_by_id.get(c.item_id)
        if item is None:
            continue
        sig = news_signals(item)
        text_lc = (
            (getattr(item, "title", "") or "") + " " + (getattr(item, "text", "") or "")
        ).lower()
        hard = 0.0
        prov: list[str] = []

        # primary
        if primary_cfg.use_company_profile or primary_cfg.use_watchlist:
            em_names = {n.lower() for n in sig.entity_names}
            em_domains = {d.lower() for d in sig.entity_domains}
            name_hit = bool(em_names & watch_names) or any(n in text_lc for n in watch_names if n)
            alias_hit = bool(em_names & watch_aliases) or any(
                a in text_lc for a in watch_aliases if a
            )
            domain_hit = bool(em_domains & watch_domains)
            if name_hit:
                hard += primary_cfg.score_boost
                prov.append("name_mention")
            elif alias_hit:
                hard += primary_cfg.score_boost
                prov.append("alias_mention")
            elif domain_hit:
                hard += primary_cfg.score_boost
                prov.append("domain_mention")

        # fallback
        if not prov and fb_cfg.enabled:
            w = fb_cfg.weights
            contrib = 0.0
            matched: list[str] = []
            if profile.okved_sector and sig.sectors:
                if profile.okved_sector in sig.sectors:
                    contrib += w.get("okved_sector", 0.0)
                    matched.append("okved_sector")
            if profile.region and sig.regions:
                if profile.region.lower() in sig.regions:
                    contrib += w.get("region", 0.0)
                    matched.append("region")
            if profile.city and profile.city.lower() in text_lc:
                contrib += w.get("city", 0.0)
                matched.append("city")
            if profile.worker_ord is not None and sig.worker_levels:
                if profile.worker_ord in sig.worker_levels:
                    contrib += w.get("worker_ord", 0.0)
                    matched.append("worker_ord")
            if profile.binary_sum_products is not None and sig.products:
                if profile.binary_sum_products >= 3:
                    contrib += w.get("binary_sum_products", 0.0)
                    matched.append("binary_sum_products")
            if profile.industry_freq is not None:
                # rare industry -> small boost
                contrib += w.get("industry_freq", 0.0) * (1.0 - profile.industry_freq)
                matched.append("industry_freq")
            if profile.revenue_rank_industry is not None:
                contrib += w.get("revenue_rank_industry", 0.0) * profile.revenue_rank_industry
                matched.append("revenue_rank_industry")

            ok_any = (
                any(m in matched for m in fb_cfg.require_any_of) if fb_cfg.require_any_of else True
            )
            if ok_any and contrib >= fb_cfg.min_score:
                hard += contrib
                prov.append("fallback")

        c.score_hard = min(hard, 2.0)
        c.provenance = prov

    # final score
    w = cfg.ranking.weights
    for c in candidates:
        c.score_total = w.dense * c.score_dense + w.cross * c.score_cross + w.hard * c.score_hard

    candidates.sort(key=lambda c: -c.score_total)
    if cfg.ranking.guarantee_hard_primary_in_top:
        primary = [
            c
            for c in candidates
            if any(p in {"name_mention", "alias_mention", "domain_mention"} for p in c.provenance)
        ]
        rest = [c for c in candidates if c not in primary]
        candidates = primary + rest
    return candidates


def rank_news(
    profile: CompanyProfile,
    news_pool: list[Any],
    watch_items: list[Any],
    cfg: AppConfig,
    encoder: BiEncoder | None = None,
    cross: CrossEncoder | None = None,
) -> list[NewsCandidate]:
    """Full news ranking pipeline for a single company profile."""
    news_by_id = {
        getattr(it, "item_id", None): it for it in news_pool if getattr(it, "item_id", None)
    }
    if not news_by_id:
        return []

    encoder = encoder or BiEncoder(cfg.embeddings, device=cfg.runtime.device)
    cross = cross or CrossEncoder(cfg.embeddings, device=cfg.runtime.device)

    query_text = company_text(profile, cfg.embeddings.text_templates)
    if not query_text.strip():
        return []

    dense = dense_recall(query_text, encoder, cfg)
    cands = [NewsCandidate(item_id=iid, score_dense=sc) for iid, sc in dense if iid in news_by_id]
    # if dense returned nothing (e.g. empty index) fallback to cross over all pool
    if not cands:
        cands = [NewsCandidate(item_id=iid, score_dense=0.0) for iid in news_by_id]

    cands = cross_rerank(query_text, cands, news_by_id, cross, cfg)
    cands = hard_recall(cands, profile, watch_items, news_by_id, cfg)
    return cands
