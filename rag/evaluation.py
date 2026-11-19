"""Evaluar el retrieval: ¿el documento correcto aparece entre los primeros resultados?"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from rag.vectorstore import SearchResult


@dataclass(frozen=True)
class CasoRetrieval:
    pregunta: str
    esperado: str  # doc_id del documento que contiene la respuesta
    nota: str = ""


def load_retrieval_set(path: str | Path) -> list[CasoRetrieval]:
    with open(path, encoding="utf-8") as f:
        return [CasoRetrieval(**item) for item in json.load(f)]


@dataclass
class RetrievalReport:
    k: int
    total: int = 0
    hits: int = 0
    reciprocal_ranks: float = 0.0
    fallos: list[str] = field(default_factory=list)

    @property
    def hit_rate(self) -> float:
        """Fracción de preguntas con el documento correcto en el top k."""
        return self.hits / self.total if self.total else 0.0

    @property
    def mrr(self) -> float:
        """Mean Reciprocal Rank: 1.0 si siempre sale primero, 0.5 si sale segundo..."""
        return self.reciprocal_ranks / self.total if self.total else 0.0


def evaluate_retrieval(
    casos: list[CasoRetrieval], search: Callable[[str, int], list[SearchResult]], k: int = 4
) -> RetrievalReport:
    # Recibe una función de búsqueda, no un VectorStore: así podrás comparar con la misma
    # evaluación la búsqueda semántica de hoy y la híbrida que vas a construir después.
    report = RetrievalReport(k=k)
    for caso in casos:
        report.total += 1
        # Varios chunks pueden ser del mismo documento: nos quedamos con el orden de documentos.
        docs: list[str] = []
        for r in search(caso.pregunta, k):
            if r.metadata["doc_id"] not in docs:
                docs.append(r.metadata["doc_id"])
        if caso.esperado in docs:
            report.hits += 1
            report.reciprocal_ranks += 1 / (docs.index(caso.esperado) + 1)
        else:
            report.fallos.append(
                f"{caso.pregunta}\n      esperado {caso.esperado} · obtenido {docs}"
            )
    return report
