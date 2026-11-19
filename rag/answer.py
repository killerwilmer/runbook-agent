"""RAG completo: recuperar fragmentos, armar el contexto y generar una respuesta con citas."""

from dataclasses import dataclass

from contracts.respuesta import RespuestaRAG
from core.llm_client import LLMClient, Parsed
from core.logger import get_logger
from core.tokenlab import check_budget
from prompting.rag import RESPONDER_V1
from rag.vectorstore import SearchResult, VectorStore

logger = get_logger(__name__)


@dataclass(frozen=True)
class RespuestaConFuentes:
    respuesta: RespuestaRAG
    fuentes: list[SearchResult]  # las que vio el modelo, en el orden en que las vio
    parsed: Parsed[RespuestaRAG]  # tokens, latencia, costo e intentos

    @property
    def citadas(self) -> list[SearchResult]:
        """Las fuentes que el modelo dijo usar (solo números que existen)."""
        return [self.fuentes[i - 1] for i in self.respuesta.citas if 1 <= i <= len(self.fuentes)]


def format_fuentes(results: list[SearchResult]) -> str:
    # Cada fuente lleva un número para citarla y su origen para que el humano pueda verificarla.
    return "\n\n".join(
        f"[{i}] {r.metadata['source']} (actualizado {r.metadata.get('actualizado', '¿?')})\n{r.text}"
        for i, r in enumerate(results, start=1)
    )


def responder(
    pregunta: str,
    store: VectorStore,
    client: LLMClient,
    k: int = 4,
    where: dict | None = None,
) -> RespuestaConFuentes:
    fuentes = store.search(pregunta, k=k, where=where)
    messages = RESPONDER_V1.render(fuentes=format_fuentes(fuentes), pregunta=pregunta)
    # El contexto recuperado es lo que más tokens gasta: se valida ANTES de llamar.
    budget = check_budget("responder_con_runbook", messages, client.model)
    parsed = client.parse(messages, RespuestaRAG, max_tokens=budget.max_output_tokens)

    invalidas = [i for i in parsed.value.citas if not 1 <= i <= len(fuentes)]
    if invalidas:
        # Pydantic no sabe cuántas fuentes hubo; esto lo revisamos aquí. Una cita a una fuente
        # que no existe es una alucinación: se registra para poder medirla.
        logger.warning(
            "Citas a fuentes inexistentes | citas=%s | fuentes=%d", invalidas, len(fuentes)
        )
    return RespuestaConFuentes(parsed.value, fuentes, parsed)
