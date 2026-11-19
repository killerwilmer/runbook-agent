"""Vector store: guarda los chunks con sus embeddings en ChromaDB y busca por similitud."""

from dataclasses import dataclass

import chromadb

from core.config import get_settings
from core.logger import get_logger
from rag.embeddings import Embedder, get_embedder
from rag.ingestion import Chunk

logger = get_logger(__name__)


@dataclass(frozen=True)
class SearchResult:
    chunk_id: str
    text: str
    metadata: dict
    score: float  # similitud coseno: 1.0 = idéntico


class VectorStore:
    def __init__(
        self,
        collection: str = "runbooks",
        path: str | None = None,
        embedder: Embedder | None = None,
    ) -> None:
        self.embedder = embedder or get_embedder()
        # PersistentClient guarda en disco: el índice sobrevive entre ejecuciones.
        client = chromadb.PersistentClient(path=path or get_settings().chroma_path)
        self._collection = client.get_or_create_collection(
            name=collection,
            # cosine: comparamos dirección (significado), no largo del vector.
            metadata={"hnsw:space": "cosine"},
            # None: los embeddings los calculamos nosotros. Así Chroma no usa en silencio
            # su modelo por defecto (solo inglés) si algún día llamas a query(query_texts=...).
            embedding_function=None,
        )

    def count(self) -> int:
        return self._collection.count()

    def index_document(self, doc_id: str, chunks: list[Chunk]) -> int:
        """Reemplaza TODOS los chunks de un documento. Idempotente: correrlo dos veces da lo mismo."""
        # ¿Por qué borrar primero? Si el documento se acortó de 5 a 3 chunks, upsert actualizaría
        # #0..#2 pero dejaría #3 y #4 viejos en el índice, respondiendo con información obsoleta.
        self._collection.delete(where={"doc_id": doc_id})
        if not chunks:
            return 0
        self._collection.upsert(
            ids=[c.chunk_id for c in chunks],
            documents=[c.text for c in chunks],
            embeddings=self.embedder.embed_documents([c.text for c in chunks]),
            metadatas=[c.metadata for c in chunks],
        )
        return len(chunks)

    def remove_missing(self, keep: set[str]) -> list[str]:
        """Borra los chunks de documentos que ya no existen. Devuelve los doc_id borrados."""
        stored = self._collection.get(include=["metadatas"])["metadatas"]
        missing = sorted({m["doc_id"] for m in stored} - keep)
        if missing:
            self._collection.delete(where={"doc_id": {"$in": missing}})
        return missing

    def search(self, query: str, k: int = 4, where: dict | None = None) -> list[SearchResult]:
        """Los k chunks más parecidos a la query. `where` filtra por metadatos ANTES de rankear."""
        if not query.strip():
            raise ValueError("La query está vacía.")
        result = self._collection.query(
            query_embeddings=[self.embedder.embed_query(query)],
            n_results=k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        # Chroma devuelve una lista por cada query enviada; mandamos una, así que tomamos [0].
        return [
            SearchResult(chunk_id, text, meta, score=1 - distance)  # distancia coseno -> similitud
            for chunk_id, text, meta, distance in zip(
                result["ids"][0],
                result["documents"][0],
                result["metadatas"][0],
                result["distances"][0],
                strict=True,
            )
        ]
