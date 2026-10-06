"""Narrative embeddings — ready for operator incident narratives in a pilot.

Public CER data has cause codes, not narratives, so nothing is embedded from it.
When an operator supplies free-text narratives (e.g. "what happened" / "why"),
this module embeds them locally with BAAI/bge-small-en-v1.5 (384 dims, no paid
API) into `incident_embeddings`, and searches them with the same
strictly-before-the-reference-date rule as core/similar.py.

sentence-transformers is imported lazily so the app runs without it.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from datetime import date
from typing import Any

import psycopg

MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384
BATCH_SIZE = 32
INSTALL_HINT = (
    "Narrative embeddings need sentence-transformers. CPU-only install: "
    "pip install torch --index-url https://download.pytorch.org/whl/cpu && "
    "pip install sentence-transformers"
)

Encoder = Callable[[Sequence[str]], list[list[float]]]


def clean_text(text: str | None) -> str:
    """Collapse whitespace and strip control characters."""
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", " ", str(text or ""))
    return re.sub(r"\s+", " ", text).strip()


def build_text(
    fields: dict[str, str | None], order: Sequence[str]
) -> tuple[str, list[str]]:
    """Concatenate the non-empty narrative fields in `order`; return text + fields used."""
    used, parts = [], []
    for name in order:
        value = clean_text(fields.get(name))
        if value:
            used.append(name)
            parts.append(value)
    return " ".join(parts), used


def load_encoder(model_name: str = MODEL_NAME) -> Encoder:
    """Local sentence-transformers encoder returning L2-normalised vectors."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:  # pragma: no cover - depends on optional install
        raise RuntimeError(INSTALL_HINT) from exc
    model = SentenceTransformer(model_name)

    def encode(texts: Sequence[str]) -> list[list[float]]:
        vecs = model.encode(
            list(texts), batch_size=BATCH_SIZE, normalize_embeddings=True
        )
        return [list(map(float, v)) for v in vecs]

    return encode


def embed_in_batches(texts: Sequence[str], encoder: Encoder) -> list[list[float]]:
    out: list[list[float]] = []
    for start in range(0, len(texts), BATCH_SIZE):
        batch = encoder(texts[start : start + BATCH_SIZE])
        for vec in batch:
            if len(vec) != EMBEDDING_DIM:
                raise ValueError(f"expected {EMBEDDING_DIM} dims, got {len(vec)}")
        out.extend(batch)
    return out


def _literal(vec: Sequence[float]) -> str:
    return "[" + ",".join(f"{v:.7f}" for v in vec) + "]"


def store_embeddings(
    conn: psycopg.Connection,
    rows: Sequence[tuple[str, str, Sequence[float]]],
    model: str = MODEL_NAME,
) -> int:
    """Upsert (incident_number, text_source, vector) rows."""
    conn.cursor().executemany(
        "INSERT INTO incident_embeddings (incident_number, text_source, model, embedding) "
        "VALUES (%s, %s, %s, %s::vector) "
        "ON CONFLICT (incident_number, text_source, model) "
        "DO UPDATE SET embedding = EXCLUDED.embedding, created_at = now()",
        [(n, src, model, _literal(v)) for n, src, v in rows],
    )
    return len(rows)


def search_narratives(
    conn: psycopg.Connection,
    query_vec: Sequence[float],
    before: date,
    k: int = 5,
    model: str = MODEL_NAME,
) -> list[dict[str, Any]]:
    """Top-k narratives by cosine similarity, from incidents strictly before `before`."""
    rows = conn.execute(
        "SELECT e.incident_number, e.text_source, i.event_date, i.hazard_group, "
        "1 - (e.embedding <=> %(q)s::vector) AS similarity "
        "FROM incident_embeddings e JOIN incidents i USING (incident_number) "
        "WHERE e.model = %(model)s AND i.event_date < %(before)s "
        "ORDER BY e.embedding <=> %(q)s::vector LIMIT %(k)s",
        {"q": _literal(query_vec), "model": model, "before": before, "k": k},
    ).fetchall()
    return [
        {
            **r,
            "event_date": r["event_date"].isoformat(),
            "similarity": round(float(r["similarity"]), 3),
        }
        for r in rows
    ]
