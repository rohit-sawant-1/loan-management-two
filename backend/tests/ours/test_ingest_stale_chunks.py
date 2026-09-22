"""
T-102: ingesting a shorter manual must not leave the old tail behind.

Chunks are stored under fixed ids (chunk_0, chunk_1, ...), which overwrite on
a second run but never delete. Before the fix, a manual that got shorter kept
its old last chunks in the collection, still searchable. For Piece 25 that
would have meant the old "cannot be modified after submission" text living on
for the chatbot to quote.

Runs fully offline: fake embeddings (random numbers, no Google call) and a
throwaway collection in a temporary folder, never the real `chroma_db/`.
"""

from langchain_core.embeddings import FakeEmbeddings

from rag import ingest


def _write_manual(folder, paragraphs: int) -> str:
    path = folder / f"manual_{paragraphs}.md"
    text = "\n\n".join(
        f"Paragraph {i}. " + "This sentence pads the paragraph to a realistic length. " * 6
        for i in range(paragraphs)
    )
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_a_shorter_manual_removes_the_old_chunks(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest, "get_embeddings", lambda: FakeEmbeddings(size=8))
    monkeypatch.setattr(ingest, "get_collection_name", lambda *a, **k: "test_stale_chunks")
    monkeypatch.setattr(ingest.settings, "chroma_persist_dir", str(tmp_path / "chroma"))

    long_count = ingest.ingest_manual(_write_manual(tmp_path, 30))
    short_count = ingest.ingest_manual(_write_manual(tmp_path, 10))

    assert short_count < long_count

    from langchain_chroma import Chroma
    store = Chroma(collection_name="test_stale_chunks", embedding_function=FakeEmbeddings(size=8),
                   persist_directory=str(tmp_path / "chroma"))
    ids = set(store._collection.get(include=[])["ids"])
    assert ids == {f"chunk_{i}" for i in range(short_count)}
    # Nothing from the longer manual's tail survived.
    documents = store._collection.get(include=["documents"])["documents"]
    assert not any("Paragraph 29." in d for d in documents)
