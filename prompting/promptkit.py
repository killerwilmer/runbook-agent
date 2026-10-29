"""PromptKit: plantillas versionadas, registro central, cadenas de prompts y lectura de JSON."""

import json
from dataclasses import dataclass
from string import Template

from core.llm_client import LLMClient

Message = dict[str, str]


@dataclass(frozen=True)
class RunResult:
    """Lo que devuelve ejecutar un prompt (o una cadena): el texto final + métricas sumadas."""

    text: str
    total_tokens: int
    latency_ms: float
    cost_usd: float


@dataclass(frozen=True)
class PromptTemplate:
    """Un prompt como código: nombre, versión y texto con variables ($incidente)."""

    name: str
    version: int
    user: str
    system: str = ""
    description: str = ""

    @property
    def key(self) -> str:
        return f"{self.name}@v{self.version}"

    def render(self, **variables: str) -> list[Message]:
        # substitute() (y no safe_substitute) lanza KeyError si falta una variable:
        # mejor fallar aquí que mandarle al modelo un "$incidente" literal.
        messages = []
        if self.system:
            messages.append(
                {"role": "system", "content": Template(self.system).substitute(variables)}
            )
        messages.append({"role": "user", "content": Template(self.user).substitute(variables)})
        return messages

    def run(self, client: LLMClient, max_tokens: int = 1024, **variables: str) -> RunResult:
        r = client.chat(self.render(**variables), max_tokens=max_tokens)
        return RunResult(r.text, r.total_tokens, r.latency_ms, r.cost_usd)


@dataclass(frozen=True)
class PromptChain:
    """Ejecuta plantillas en orden: la salida de cada paso entra al siguiente como $previo."""

    name: str
    version: int
    steps: tuple[PromptTemplate, ...]
    description: str = ""

    @property
    def key(self) -> str:
        return f"{self.name}@v{self.version}"

    def run(self, client: LLMClient, max_tokens: int = 1024, **variables: str) -> RunResult:
        previo, tokens, latency_ms, cost = "", 0, 0.0, 0.0
        for step in self.steps:
            r = step.run(client, max_tokens=max_tokens, **variables, previo=previo)
            previo = r.text
            tokens += r.total_tokens
            latency_ms += r.latency_ms
            cost += r.cost_usd
        return RunResult(previo, tokens, latency_ms, cost)


# Para quien usa un prompt da igual si es una plantilla o una cadena: ambos tienen key y run().
Prompt = PromptTemplate | PromptChain


class PromptRegistry:
    """Un solo lugar donde viven todos los prompts del sistema, por nombre y versión."""

    def __init__(self) -> None:
        self._prompts: dict[str, dict[int, Prompt]] = {}

    def register(self, prompt: Prompt) -> Prompt:
        versions = self._prompts.setdefault(prompt.name, {})
        if prompt.version in versions:
            # Una versión publicada no se modifica: si cambias el prompt, es una versión nueva.
            raise ValueError(f"{prompt.key} ya está registrado.")
        versions[prompt.version] = prompt
        return prompt

    def get(self, name: str, version: int | None = None) -> Prompt:
        if name not in self._prompts:
            raise KeyError(f"No hay prompts con el nombre {name!r}.")
        versions = self._prompts[name]
        if version is None:
            return versions[max(versions)]  # la versión más reciente
        if version not in versions:
            raise KeyError(f"{name}@v{version} no existe. Versiones: {sorted(versions)}")
        return versions[version]

    def keys(self) -> list[str]:
        return [p.key for versions in self._prompts.values() for p in versions.values()]


registry = PromptRegistry()  # el registro global del sistema


def extract_json(text: str) -> dict | None:
    """Devuelve el ÚLTIMO objeto JSON del texto, aunque venga con ```json o texto alrededor."""
    # ¿Por qué el último? Algunos modelos (Gemma) piensan en voz alta y citan el formato
    # antes de dar su respuesta final.
    decoder = json.JSONDecoder()
    last = None
    i = text.find("{")
    while i != -1:
        try:
            obj, end = decoder.raw_decode(text, i)
        except json.JSONDecodeError:
            i = text.find("{", i + 1)
            continue
        if isinstance(obj, dict):
            last = obj
        i = text.find("{", end)
    return last
