"""Indexa los runbooks, postmortems y guías de data/docs en ChromaDB.

Uso:  uv run python -m scripts.indexar
      uv run python -m scripts.indexar --max-tokens 200 --overlap 0
"""

import argparse
import time

from core.logger import setup_logger
from rag.embeddings import get_embedder
from rag.ingestion import chunk_document, load_directory
from rag.vectorstore import VectorStore

DOCS = "data/docs"


def main() -> None:
    parser = argparse.ArgumentParser(description="Indexa los documentos en ChromaDB.")
    parser.add_argument("--max-tokens", type=int, default=300)
    parser.add_argument("--overlap", type=int, default=1, help="párrafos repetidos entre chunks")
    args = parser.parse_args()
    setup_logger("INFO")

    embedder = get_embedder()
    store = VectorStore(embedder=embedder)
    started = time.perf_counter()
    docs = load_directory(DOCS)
    total, largest = 0, 0
    for doc in docs:
        # Contamos con el tokenizador del modelo de EMBEDDINGS: su límite es el que importa aquí.
        chunks = chunk_document(doc, args.max_tokens, args.overlap, count=embedder.count_tokens)
        total += store.index_document(doc.doc_id, chunks)
        if not chunks:
            print(f"  {doc.doc_id:<50} vacío, no se indexó")
            continue
        sizes = [embedder.count_tokens(c.text) for c in chunks]
        largest = max(largest, *sizes)
        print(f"  {doc.doc_id:<50} {len(chunks):>2} chunks · máx {max(sizes)} tokens")

    # Un archivo borrado de data/docs no pasa por el bucle: sus chunks hay que borrarlos aparte.
    for doc_id in store.remove_missing({d.doc_id for d in docs}):
        print(f"  🗑️  {doc_id}: ya no existe, sus chunks se borraron del índice")

    elapsed = time.perf_counter() - started
    print(f"\n{total} chunks indexados en {elapsed:.1f} s · colección con {store.count()} chunks")
    print(f"Chunk más largo: {largest} tokens (el modelo lee hasta {embedder.max_tokens})")
    if largest > embedder.max_tokens:
        print("⚠️  Hay chunks más largos que lo que lee el modelo: su final no se está indexando.")


if __name__ == "__main__":
    main()
