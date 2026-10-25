"""Build FAISS indexes from cached embeddings."""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np

from alfa_insights.config import FaissConfig, load_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
log = logging.getLogger("build_index")


def build_index(emb: np.ndarray, cfg: FaissConfig):
    import faiss
    dim = emb.shape[1]
    if cfg.index_type == "flat":
        index = faiss.IndexFlatIP(dim)
        index.add(emb)
        return index
    if cfg.index_type == "ivf":
        quantizer = faiss.IndexFlatIP(dim)
        index = faiss.IndexIVFFlat(quantizer, dim, cfg.ivf.nlist, faiss.METRIC_INNER_PRODUCT)
        index.train(emb)
        index.add(emb)
        index.nprobe = cfg.ivf.nprobe
        return index
    if cfg.index_type == "hnsw":
        index = faiss.IndexHNSWFlat(dim, cfg.hnsw.M)
        index.hnsw.efConstruction = cfg.hnsw.efConstruction
        index.hnsw.efSearch = cfg.hnsw.efSearch
        index.metric_type = faiss.METRIC_INNER_PRODUCT
        index.add(emb)
        return index
    raise ValueError(cfg.index_type)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--which", default="both", choices=["news", "analytics", "both"])
    args = ap.parse_args()

    cfg = load_config(args.config)
    targets = []
    if args.which in ("news", "both"):
        targets.append(cfg.paths.news_cache)
    if args.which in ("analytics", "both"):
        targets.append(cfg.paths.analytics_cache)

    for cache in targets:
        emb_path = cache / "emb.npy"
        ids_path = cache / "ids.json"
        if not emb_path.exists():
            log.warning("no embeddings in %s, skip", cache)
            continue
        emb = np.load(emb_path).astype(np.float32)
        index = build_index(emb, cfg.faiss)
        import faiss
        faiss.write_index(index, str(cache / "faiss.index"))
        meta = json.loads(ids_path.read_text(encoding="utf-8")) if ids_path.exists() else {}
        meta["dim"] = int(emb.shape[1])
        meta["size"] = int(emb.shape[0])
        ids_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        log.info("index built: %s (%d vectors, dim=%d, type=%s)", cache, emb.shape[0], emb.shape[1], cfg.faiss.index_type)


if __name__ == "__main__":
    main()