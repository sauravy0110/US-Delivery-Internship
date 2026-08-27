"""
RAG over the Markdown knowledge base.

Primary path: SentenceTransformers embeddings + a FAISS flat inner-product
index (embeddings L2-normalized, so inner product == cosine similarity).
This is the semantically-correct choice — it matches a paraphrased ticket
("everything is timing out") to a doc that never uses those exact words.

Fallback path: local TF-IDF (scikit-learn), used automatically — and
logged via app.observability — if the embedding model can't be loaded
(e.g. no network access to the model hub). This matters in locked-down
CI runners or air-gapped environments where the embedding model can't be
downloaded on first run.

Chunking strategy: split on `---` horizontal rules, keep the nearest
preceding heading as metadata so retrieved chunks can cite "which doc /
which section".

Set KB_RETRIEVAL_MODE=tfidf in .env to force the fallback path deliberately
(e.g. for a fully offline demo).
"""
import re
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from app import config, observability


@dataclass
class Chunk:
    doc_path: str
    heading: str
    text: str


def _iter_kb_files():
    if not config.KB_DIR.exists():
        return
    for path in sorted(config.KB_DIR.rglob("*.md")):
        yield path


def _chunk_markdown(path) -> list[Chunk]:
    text = path.read_text(encoding="utf-8")
    raw_chunks = re.split(r"\n-{3,}\n", text)
    chunks = []
    current_heading = path.stem
    for raw in raw_chunks:
        raw = raw.strip()
        if not raw:
            continue
        heading_match = re.search(r"^#{1,6}\s+(.+)$", raw, re.MULTILINE)
        if heading_match:
            current_heading = heading_match.group(1).strip()
        rel_path = str(path.relative_to(config.KB_DIR))
        chunks.append(Chunk(doc_path=rel_path, heading=current_heading, text=raw))
    return chunks


def _load_all_chunks() -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in _iter_kb_files():
        chunks.extend(_chunk_markdown(path))
    return chunks


# --------------------------------------------------------------------------
# TF-IDF backend (fallback)
# --------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _tfidf_index():
    from sklearn.feature_extraction.text import TfidfVectorizer

    chunks = _load_all_chunks()
    if not chunks:
        return [], None, None
    vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
    matrix = vectorizer.fit_transform([c.text for c in chunks])
    return chunks, vectorizer, matrix


def _search_tfidf(query: str, top_k: int, min_score: float) -> list[dict]:
    from sklearn.metrics.pairwise import cosine_similarity

    chunks, vectorizer, matrix = _tfidf_index()
    if not chunks:
        return []
    query_vec = vectorizer.transform([query])
    scores = cosine_similarity(query_vec, matrix).flatten()
    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    results = []
    for i in ranked[:top_k]:
        if scores[i] < min_score:
            continue
        c = chunks[i]
        results.append({
            "doc_path": c.doc_path, "heading": c.heading,
            "score": round(float(scores[i]), 4), "excerpt": c.text[:400],
        })
    return results


# --------------------------------------------------------------------------
# Embeddings + FAISS backend (primary)
# --------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _embedding_index():
    """Returns (chunks, faiss_index, model) or raises if the model can't be
    loaded — caller is responsible for catching and falling back."""
    import faiss
    from sentence_transformers import SentenceTransformer

    chunks = _load_all_chunks()
    if not chunks:
        return [], None, None

    model = SentenceTransformer(config.EMBEDDING_MODEL)
    embeddings = model.encode([c.text for c in chunks], normalize_embeddings=True)
    embeddings = np.asarray(embeddings, dtype="float32")

    index = faiss.IndexFlatIP(embeddings.shape[1])  # inner product on normalized vecs = cosine
    index.add(embeddings)
    return chunks, index, model


def _search_embeddings(query: str, top_k: int, min_score: float) -> list[dict]:
    chunks, index, model = _embedding_index()
    if not chunks:
        return []
    query_vec = np.asarray(model.encode([query], normalize_embeddings=True), dtype="float32")
    scores, indices = index.search(query_vec, min(top_k, len(chunks)))
    results = []
    for score, i in zip(scores[0], indices[0]):
        if i < 0 or score < min_score:
            continue
        c = chunks[i]
        results.append({
            "doc_path": c.doc_path, "heading": c.heading,
            "score": round(float(score), 4), "excerpt": c.text[:400],
        })
    return results


# --------------------------------------------------------------------------
# Public interface — picks a backend and falls back on failure, once, with
# the decision cached (and logged) for the life of the process.
# --------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _resolve_backend() -> str:
    """Decides which backend to actually use, tries to warm the embedding
    index if requested, and logs the outcome exactly once per process."""
    if config.KB_RETRIEVAL_MODE != "embeddings":
        observability.log_event("kb.backend_selected", backend="tfidf",
                                 reason="KB_RETRIEVAL_MODE=tfidf (explicit)")
        return "tfidf"
    try:
        _embedding_index()  # eagerly attempt to load — surfaces failures now, not mid-query
        observability.log_event("kb.backend_selected", backend="embeddings",
                                 model=config.EMBEDDING_MODEL)
        return "embeddings"
    except Exception as exc:  # noqa: BLE001 — network/model-hub errors, missing deps, etc.
        observability.log_event("kb.backend_fallback", requested="embeddings", used="tfidf",
                                 reason=str(exc)[:300])
        return "tfidf"


def search(query: str, top_k: int = 3, min_score: float = 0.08) -> list[dict]:
    """Returns up to top_k relevant KB chunks above a minimum similarity
    threshold. Backend (embeddings vs TF-IDF) is resolved once per process
    and logged; callers never need to know which one served the request."""
    backend = _resolve_backend()
    with observability.log_call("kb.search", backend=backend) as ev:
        if backend == "embeddings":
            # min_score is tuned per-backend: cosine similarity from sentence
            # embeddings sits in a different numeric range than TF-IDF cosine.
            results = _search_embeddings(query, top_k, min_score=max(min_score, 0.25))
        else:
            results = _search_tfidf(query, top_k, min_score)
        ev["results_returned"] = len(results)
        return results
