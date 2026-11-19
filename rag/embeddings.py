"""Embeddings: convierten texto en vectores para poder buscar por significado."""

from functools import cached_property, lru_cache

import numpy as np
from sentence_transformers import SentenceTransformer

from core.config import get_settings
from core.logger import get_logger

logger = get_logger(__name__)

# Los modelos e5 se entrenaron con prefijos: "query: " para lo que se busca y "passage: " para
# lo que se guarda. Sin ellos la calidad baja. Si cambias de modelo, revisa qué prefijos usa.
QUERY_PREFIX = "query: "
PASSAGE_PREFIX = "passage: "


class Embedder:
    """Un modelo de embeddings local. Se carga la primera vez que se usa, no al importarlo."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    @cached_property
    def _model(self) -> SentenceTransformer:
        # ¿Por qué cargar aquí y no en __init__? Cargar el modelo tarda segundos y la primera vez
        # descarga ~470 MB: que solo lo pague quien realmente genera embeddings.
        logger.info("Cargando modelo de embeddings %s", self.model_name)
        return SentenceTransformer(self.model_name)

    @property
    def dimension(self) -> int:
        return self._model.get_embedding_dimension()

    @property
    def max_tokens(self) -> int:
        """Tokens máximos que el modelo lee. Lo que pase de ahí se descarta SIN aviso."""
        return self._model.max_seq_length

    def count_tokens(self, text: str) -> int:
        """Tokens según el tokenizador del modelo de embeddings (no el del LLM)."""
        return len(self._model.tokenizer.encode(PASSAGE_PREFIX + text))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # Siempre en lote: una llamada con 50 textos es mucho más rápida que 50 llamadas.
        return self._encode([PASSAGE_PREFIX + t for t in texts])

    def embed_query(self, text: str) -> list[float]:
        return self._encode([QUERY_PREFIX + text])[0]

    def _encode(self, texts: list[str]) -> list[list[float]]:
        # normalize_embeddings=True deja cada vector con largo 1: así coseno = producto punto.
        vectors = self._model.encode(
            texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False
        )
        return vectors.tolist()


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    return Embedder(get_settings().embedding_model)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """1.0 = misma dirección (mismo significado); cerca de 0 = nada que ver."""
    va, vb = np.array(a), np.array(b)
    return float(va @ vb / (np.linalg.norm(va) * np.linalg.norm(vb)))
