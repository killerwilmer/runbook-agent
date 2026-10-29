"""TokenLab: contar tokens, estimar costos y controlar presupuestos por feature."""

from dataclasses import dataclass
from functools import lru_cache

import tiktoken

from core.config import get_settings

Message = dict[str, str]

# Tokenizador por familia de modelo. Cada familia tiene el suyo, así que fuera de gpt-oss
# el conteo es una APROXIMACIÓN. El conteo real es el que devuelve la API en `usage`;
# este sirve para decidir ANTES de llamar (¿cabe?, ¿cuánto costará?).
_ENCODING_BY_PREFIX = {"openai/gpt-oss": "o200k_harmony"}
_DEFAULT_ENCODING = "o200k_base"

# Cada mensaje agrega tokens de formato (rol, separadores) que no ves en el texto.
_TOKENS_PER_MESSAGE = 4


@lru_cache(maxsize=8)  # ¿Por qué? Cargar un tokenizador es lento; se hace una vez por encoding.
def _encoding(name: str) -> tiktoken.Encoding:
    return tiktoken.get_encoding(name)


def count_tokens(text: str, model: str = "") -> int:
    """Tokens aproximados de un texto para el modelo dado."""
    name = next(
        (enc for prefix, enc in _ENCODING_BY_PREFIX.items() if model.startswith(prefix)),
        _DEFAULT_ENCODING,
    )
    return len(_encoding(name).encode(text))


def count_message_tokens(messages: list[Message], model: str = "") -> int:
    """Tokens aproximados de una lista de mensajes, incluyendo el formato de cada uno."""
    return sum(count_tokens(m["content"], model) + _TOKENS_PER_MESSAGE for m in messages)


@dataclass(frozen=True)
class Pricing:
    input_per_1m: float
    output_per_1m: float

    @classmethod
    def from_settings(cls) -> "Pricing":
        s = get_settings()
        return cls(s.input_cost_per_1m_tokens, s.output_cost_per_1m_tokens)


def estimate_cost(input_tokens: int, output_tokens: int, pricing: Pricing) -> float:
    return (input_tokens * pricing.input_per_1m + output_tokens * pricing.output_per_1m) / 1_000_000


def project_monthly_cost(
    input_tokens: int, output_tokens: int, requests_per_day: int, pricing: Pricing
) -> float:
    """Costo mensual (30 días) si cada request gasta esos tokens."""
    return estimate_cost(input_tokens, output_tokens, pricing) * requests_per_day * 30


@dataclass(frozen=True)
class FeatureBudget:
    max_input_tokens: int
    max_output_tokens: int


# Presupuesto de tokens por feature de runbook-agent. Son valores iniciales:
# los ajustarás con mediciones reales a medida que construyas cada feature.
BUDGETS: dict[str, FeatureBudget] = {
    "chat_general": FeatureBudget(max_input_tokens=2_000, max_output_tokens=800),
    # Medido: el prompt v3 usa ~670 tokens y gpt-oss razona antes de responder.
    "clasificar_severidad": FeatureBudget(max_input_tokens=1_000, max_output_tokens=500),
    "responder_con_runbook": FeatureBudget(max_input_tokens=4_000, max_output_tokens=800),
    "diagnostico_agente": FeatureBudget(max_input_tokens=15_000, max_output_tokens=2_000),
}


class BudgetExceededError(RuntimeError):
    """El request supera el presupuesto de tokens de su feature."""


def check_budget(feature: str, messages: list[Message], model: str = "") -> FeatureBudget:
    """Valida el input ANTES de llamar al LLM y devuelve el presupuesto a respetar."""
    if feature not in BUDGETS:
        raise ValueError(f"Feature {feature!r} sin presupuesto. Defínelo en BUDGETS.")
    budget = BUDGETS[feature]
    used = count_message_tokens(messages, model)
    if used > budget.max_input_tokens:
        raise BudgetExceededError(
            f"{feature}: el input usa ~{used} tokens y el máximo es {budget.max_input_tokens}."
        )
    return budget
