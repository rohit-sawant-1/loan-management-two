"""
Ingestion: read the user manual once, cut it into chunks, turn each chunk into
numbers, and store them in ChromaDB so questions can be answered from it later.

Run it from the backend/ folder:

    venv\\Scripts\\python.exe -m rag.ingest

What "ingestion" means, in plain words
--------------------------------------
An AI model cannot search a document. What it can do is compare *meanings*
expressed as long lists of numbers. So we cut the manual into small pieces,
ask the embedding model to turn each piece into a list of numbers that stands
for its meaning, and keep those lists in a database built for finding the
closest matches. Later, a question gets turned into numbers the same way, and
the database hands back the pieces of manual that mean something similar.

Why chunks overlap by 50 characters
-----------------------------------
A 512-character cut lands wherever it lands, quite possibly through the middle
of the sentence that holds the answer. Overlapping consecutive chunks by 50
characters means such a sentence still appears whole in one of them.

Why every chunk has a fixed id
------------------------------
Chunks are stored as `chunk_0`, `chunk_1` and so on. ChromaDB treats an
existing id as an overwrite, so running ingestion twice updates the manual in
place instead of storing a second copy of it. Without this you would slowly
fill the database with duplicates and retrieval would return the same paragraph
four times.
"""

from __future__ import annotations

import hashlib
import sys
import time
from pathlib import Path

import structlog
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings
from app.utils.logging_config import configure_logging
from app.utils.otel_config import get_tracer, setup_telemetry
from llm_provider import describe, get_collection_name, get_embeddings

logger = structlog.get_logger()

DEFAULT_MANUAL = "rag/user_manual.md"


def load_manual(path: str = DEFAULT_MANUAL):
    """Read the manual off disk. One Document comes back, holding the whole file."""
    tracer = get_tracer()
    with tracer.start_as_current_span("rag.document_load") as span:
        span.set_attribute("rag.source", path)
        if not Path(path).exists():
            raise FileNotFoundError(
                f"Cannot find {path}. Run this from the backend/ folder — every "
                f"Phase 2 path is relative to it."
            )
        documents = TextLoader(path, encoding="utf-8").load()
        characters = sum(len(d.page_content) for d in documents)
        span.set_attribute("rag.documents", len(documents))
        span.set_attribute("rag.characters", characters)
        logger.info("rag_document_loaded", operation="document_load",
                    source=path, documents=len(documents), characters=characters)
        return documents


def chunk_documents(documents):
    """
    Cut the manual into overlapping pieces.

    The splitter tries paragraph breaks first, then line breaks, then sentence
    ends, then spaces — so it cuts at the most natural boundary available rather
    than blindly at 512 characters.
    """
    tracer = get_tracer()
    with tracer.start_as_current_span("rag.chunk") as span:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        chunks = splitter.split_documents(documents)
        sizes = [len(c.page_content) for c in chunks]
        span.set_attribute("rag.chunks", len(chunks))
        span.set_attribute("rag.chunk_size", settings.chunk_size)
        span.set_attribute("rag.chunk_overlap", settings.chunk_overlap)
        span.set_attribute("rag.largest_chunk", max(sizes) if sizes else 0)
        logger.info("rag_chunks_created", operation="chunk",
                    chunks=len(chunks), chunk_size=settings.chunk_size,
                    chunk_overlap=settings.chunk_overlap,
                    largest=max(sizes) if sizes else 0)
        return chunks


def _manual_fingerprint(documents, chunks) -> str:
    """A short hash of the manual's exact content and how it was cut up."""
    text = "".join(d.page_content for d in documents)
    stamp = f"{text}|{settings.chunk_size}|{settings.chunk_overlap}|{len(chunks)}"
    return hashlib.sha256(stamp.encode("utf-8")).hexdigest()[:16]


def ingest_manual(path: str = DEFAULT_MANUAL, force: bool = False) -> int:
    """
    The whole pipeline: load, chunk, embed, store. Returns how many chunks are
    in the collection afterwards.

    **Unchanged manuals are not re-embedded.** Turning 42 chunks into numbers
    costs 42 calls to Google, and the free tier allows 100 embedding calls a
    minute. Running the test suite re-ingested four times over and blew through
    that limit, which is how this was found. So the manual's content is
    fingerprinted and stored on the collection; if the fingerprint still matches
    and the collection is populated, the embedding step is skipped.

    Pass `force=True` to embed regardless, which is what you want after changing
    the embedding model or the provider.

    The trainer's `TC-01-P2-OBS-02` imports this function by this exact name and
    checks that the span names appear on the console while it runs, so all three
    spans are opened either way — the embed span simply records that it skipped.
    """
    configure_logging()
    setup_telemetry()
    tracer = get_tracer()

    started = time.perf_counter()
    info = describe()
    logger.info("rag_ingestion_started", operation="ingestion_started", **info)

    documents = load_manual(path)
    chunks = chunk_documents(documents)

    # Fixed ids, so re-running overwrites rather than duplicating.
    ids = [f"chunk_{i}" for i in range(len(chunks))]
    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_id"] = ids[i]
        chunk.metadata["source"] = path

    fingerprint = _manual_fingerprint(documents, chunks)

    with tracer.start_as_current_span("rag.embed") as span:
        # Imported here rather than at the top so that merely importing this
        # module does not require chromadb to be installed.
        from langchain_chroma import Chroma

        collection = get_collection_name()
        span.set_attribute("rag.collection", collection)
        span.set_attribute("rag.chunks", len(chunks))
        span.set_attribute("rag.provider", info["provider"])
        span.set_attribute("rag.embed_model", info["embed_model"])
        span.set_attribute("rag.fingerprint", fingerprint)

        store = Chroma(
            collection_name=collection,
            embedding_function=get_embeddings(),
            persist_directory=settings.chroma_persist_dir,
        )
        raw = store._collection
        existing = raw.count()
        stored_fingerprint = (raw.metadata or {}).get("manual_fingerprint")
        unchanged = (
            not force
            and existing == len(chunks)
            and stored_fingerprint == fingerprint
        )

        if unchanged:
            total = existing
            span.set_attribute("rag.skipped", True)
            logger.info("rag_embeddings_unchanged", operation="embed",
                        collection=collection, chunks=len(chunks),
                        collection_count=total, skipped=True,
                        reason="manual unchanged since last ingestion")
        else:
            store.add_documents(documents=chunks, ids=ids)
            # Fixed ids overwrite, but they never delete (T-102). If the manual
            # got shorter, the old chunks past the new end would stay in the
            # collection, and a question could still find text that is no longer
            # in the manual. So anything not in today's set of ids is removed.
            stale = sorted(set(raw.get(include=[])["ids"]) - set(ids))
            if stale:
                raw.delete(ids=stale)
                logger.info("rag_stale_chunks_removed", operation="embed",
                            collection=collection, removed=len(stale))
            raw.modify(metadata={"manual_fingerprint": fingerprint,
                                 "embed_model": info["embed_model"]})
            total = raw.count()
            span.set_attribute("rag.skipped", False)
            span.set_attribute("rag.collection_count", total)
            logger.info("rag_embeddings_stored", operation="embed",
                        collection=collection, chunks=len(chunks),
                        collection_count=total, skipped=False,
                        embed_model=info["embed_model"])

    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    logger.info("rag_ingestion_completed", operation="ingestion_completed",
                collection=get_collection_name(), chunks=len(chunks),
                duration_ms=duration_ms)
    return total


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--force"]
    force = "--force" in sys.argv
    path = args[0] if args else DEFAULT_MANUAL
    info = describe()
    print(f"Provider   : {info['provider']}")
    print(f"Embeddings : {info['embed_model']}")
    print(f"Collection : {info['collection']}")
    print(f"Manual     : {path}")
    print()
    try:
        total = ingest_manual(path, force=force)
    except Exception as e:                                       # noqa: BLE001
        print(f"\nIngestion failed: {type(e).__name__}: {e}")
        return 1
    print(f"\nDone. The collection now holds {total} chunks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
