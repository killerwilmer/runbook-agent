"""Evaluar un prompt contra un golden set: saber con números si una versión es mejor que otra."""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from core.llm_client import LLMClient
from core.logger import get_logger
from prompting.promptkit import Prompt, extract_json

logger = get_logger(__name__)


@dataclass(frozen=True)
class Caso:
    """Un ejemplo del golden set: la entrada y la respuesta correcta."""

    input: str
    esperado: str
    nota: str = ""


def load_golden_set(path: str | Path) -> list[Caso]:
    with open(path, encoding="utf-8") as f:
        return [Caso(**item) for item in json.load(f)]


@dataclass
class EvalReport:
    prompt: str
    total: int
    correctos: int = 0
    json_validos: int = 0
    valores_validos: int = 0
    subestimados: int = 0  # respondió algo MENOS grave que lo esperado: el error más caro
    errores_llamada: int = 0
    tokens: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    fallos: list[str] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return self.correctos / self.total if self.total else 0.0

    @property
    def llamadas_ok(self) -> int:
        return self.total - self.errores_llamada

    @property
    def tokens_promedio(self) -> float:
        return self.tokens / self.llamadas_ok if self.llamadas_ok else 0.0

    @property
    def latencia_promedio_ms(self) -> float:
        return self.latency_ms / self.llamadas_ok if self.llamadas_ok else 0.0


def evaluate(
    prompt: Prompt,
    client: LLMClient,
    casos: list[Caso],
    *,
    variable: str,
    campo: str,
    valores: tuple[str, ...],
    delay_s: float = 0.0,
    max_tokens: int = 1024,
) -> EvalReport:
    """Corre el prompt con cada caso y compara `campo` del JSON de respuesta con lo esperado.

    `valores` son las respuestas válidas, ordenadas de más a menos grave.
    """
    report = EvalReport(prompt=prompt.key, total=len(casos))
    for i, caso in enumerate(casos):
        if i and delay_s:
            time.sleep(delay_s)  # ¿Por qué? La capa gratuita limita las llamadas por minuto.
        try:
            r = prompt.run(client, max_tokens=max_tokens, **{variable: caso.input})
        except RuntimeError as exc:
            # Un caso que falla no detiene la evaluación: se cuenta y se sigue.
            report.errores_llamada += 1
            report.fallos.append(f"ERROR  | {caso.input[:60]} | {exc}")
            continue

        report.tokens += r.total_tokens
        report.latency_ms += r.latency_ms
        report.cost_usd += r.cost_usd

        data = extract_json(r.text)
        obtenido = str(data.get(campo, "")).strip().upper() if data else ""
        if data is not None:
            report.json_validos += 1
        if obtenido in valores:
            report.valores_validos += 1
        if obtenido == caso.esperado:
            report.correctos += 1
            continue

        if obtenido in valores and valores.index(obtenido) > valores.index(caso.esperado):
            report.subestimados += 1
        report.fallos.append(
            f"esperado {caso.esperado} · obtenido {obtenido or '¿?'} | {caso.input[:60]}"
        )
    logger.info("eval | prompt=%s | accuracy=%.2f", report.prompt, report.accuracy)
    return report
