"""Bi-encoder, cross-encoder, embedding cache."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np

from .config import EmbeddingsConfig, TextTemplatesConfig

log = logging.getLogger(__name__)

from functools import lru_cache


@lru_cache(maxsize=4)
def _load_bi(model_name: str, device: str):
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(model_name, device=device)


@lru_cache(maxsize=4)
def _load_cross(model_name: str, device: str):
    from sentence_transformers import CrossEncoder
    return CrossEncoder(model_name, device=device)


def _hash_texts(texts: Iterable[str]) -> str:
    h = hashlib.sha256()
    for t in texts:
        h.update(t.encode("utf-8", errors="ignore"))
        h.update(b"\x00")
    return h.hexdigest()


def _item_key(item: Any) -> str:
    return f"{getattr(item, 'item_id', '')}|{getattr(item, 'document_id', '')}|{getattr(item, 'chunk_id', '')}"


def news_text(item: Any, tpl: TextTemplatesConfig) -> str:
    return tpl.news.format(
        title=(getattr(item, "title", "") or ""), text=(getattr(item, "text", "") or "")
    )


def analytics_text(item: Any, tpl: TextTemplatesConfig) -> str:
    return tpl.analytics.format(
        title=(getattr(item, "title", "") or ""), text=(getattr(item, "text", "") or "")
    )


def company_text(profile: Any, tpl: TextTemplatesConfig) -> str:
    return tpl.company.format(
        name=profile.name or "",
        okved_name=profile.okved_name or "",
        region=profile.region or "",
        city=profile.city or "",
        specialization=profile.specialization or "",
    )


class BiEncoder:
    def __init__(self, cfg: EmbeddingsConfig, device: str = "cpu") -> None:
        self.cfg = cfg.bi_encoder
        self.model = _load_bi(self.cfg.model_name, device) 

        self.cfg = cfg.bi_encoder
        self.model = SentenceTransformer(self.cfg.model_name, device=device)

    def encode_docs(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        prefixed = [self.cfg.doc_prefix + t for t in texts]
        emb = self.model.encode(
            prefixed,
            batch_size=self.cfg.batch_size,
            normalize_embeddings=self.cfg.normalize,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return emb.astype(np.float32)

    def encode_queries(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        prefixed = [self.cfg.query_prefix + t for t in texts]
        emb = self.model.encode(
            prefixed,
            batch_size=self.cfg.batch_size,
            normalize_embeddings=self.cfg.normalize,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return emb.astype(np.float32)

    @property
    def dim(self) -> int:
        return int(self.model.get_sentence_embedding_dimension())


class CrossEncoder:
    def __init__(self, cfg: EmbeddingsConfig, device: str = "cpu") -> None:
        self.cfg = cfg.cross_encoder
        self.model = _load_cross(self.cfg.model_name, device)

        self.cfg = cfg.cross_encoder
        self.model = _CE(self.cfg.model_name, device=device)

    def score_pairs(self, pairs: list[tuple[str, str]]) -> np.ndarray:
        if not pairs:
            return np.zeros((0,), dtype=np.float32)
        scores = self.model.predict(pairs, batch_size=self.cfg.batch_size, show_progress_bar=False)
        return np.asarray(scores, dtype=np.float32)


class EmbeddingStore:
    """Persistent embedding cache for news or analytics."""

    def __init__(self, cache_dir: Path, model_name: str, kind: str) -> None:
        self.dir = cache_dir
        self.model_name = model_name
        self.kind = kind
        self.dir.mkdir(parents=True, exist_ok=True)
        self.emb_path = self.dir / "emb.npy"
        self.ids_path = self.dir / "ids.json"
        self._emb: np.ndarray | None = None
        self._ids: list[dict[str, Any]] | None = None
        self._id_index: dict[str, int] | None = None

    def load(self) -> tuple[np.ndarray, list[dict[str, Any]]] | None:
        if not (self.emb_path.exists() and self.ids_path.exists()):
            return None
        with self.ids_path.open("r", encoding="utf-8") as f:
            meta = json.load(f)
        if meta.get("model") != self.model_name:
            log.warning(
                "Embedding cache model mismatch (%s != %s). Rebuild required.",
                meta.get("model"),
                self.model_name,
            )
            return None
        self._emb = np.load(self.emb_path).astype(np.float32)
        self._ids = meta.get("ids", [])
        return self._emb, self._ids

    def save(self, emb: np.ndarray, ids: list[dict[str, Any]], text_hash: str) -> None:
        np.save(self.emb_path, emb.astype(np.float32))
        with self.ids_path.open("w", encoding="utf-8") as f:
            json.dump(
                {"model": self.model_name, "kind": self.kind, "text_hash": text_hash, "ids": ids},
                f,
                ensure_ascii=False,
            )

    def build_or_load(
        self,
        items: list[Any],
        encoder: BiEncoder,
        text_builder,
        force: bool = False,
    ) -> tuple[np.ndarray, list[dict[str, Any]]]:
        texts = [text_builder(it) for it in items]
        th = _hash_texts(texts)
        if not force:
            loaded = self.load()
            if loaded is not None:
                _, ids = loaded
                with self.ids_path.open("r", encoding="utf-8") as f:
                    meta = json.load(f)
                if meta.get("text_hash") == th and len(ids) == len(items):
                    log.info("Embedding cache hit for %s (%d items)", self.kind, len(items))
                    return self._emb, ids  # type: ignore[return-value]
        log.info("Building embeddings for %s (%d items)", self.kind, len(items))
        emb = encoder.encode_docs(texts)
        ids: list[dict[str, Any]] = [
            {
                "key": _item_key(it),
                "item_id": getattr(it, "item_id", None),
                "document_id": getattr(it, "document_id", None),
                "chunk_id": getattr(it, "chunk_id", None),
            }
            for it in items
        ]
        self.save(emb, ids, th)
        self._emb = emb
        self._ids = ids
        return emb, ids

    def index_by_item_id(self) -> dict[str, int]:
        if self._ids is None or self._id_index is None:
            if self._ids is None:
                loaded = self.load()
                if loaded is None:
                    raise RuntimeError(f"Embeddings not built for {self.kind}")
            self._id_index = {d["item_id"]: i for i, d in enumerate(self._ids) if d.get("item_id")}
        return self._id_index
