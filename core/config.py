"""Configuración centralizada leída desde variables de entorno."""

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()  # carga .env en os.environ (si existe)

# Datos de conexión de cada proveedor compatible con la API de OpenAI.
PROVIDERS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key_env": "GEMINI_API_KEY",
    },
}


@dataclass(frozen=True)  # ¿Por qué frozen? La config no debe cambiar mientras corre el programa.
class Settings:
    llm_provider: str
    llm_model: str
    llm_temperature: float
    llm_timeout_s: float
    llm_max_retries: int
    api_key: str
    base_url: str
    log_level: str
    input_cost_per_1m_tokens: float
    output_cost_per_1m_tokens: float


def _read_float(name: str, default: str) -> float:
    raw = os.getenv(name, default).strip()
    try:
        return float(raw)
    except ValueError as exc:
        # ¿Por qué? Un error que dice QUÉ variable está mal ahorra minutos de depuración.
        raise ValueError(f"{name}={raw!r} no es un número válido.") from exc


@lru_cache(maxsize=1)  # ¿Por qué? Se lee y valida una sola vez; después se reutiliza.
def get_settings() -> Settings:
    provider = os.getenv("LLM_PROVIDER", "groq").strip().lower()
    if provider not in PROVIDERS:
        raise ValueError(f"LLM_PROVIDER={provider!r} no soportado. Usa: {list(PROVIDERS)}")

    key_env = PROVIDERS[provider]["api_key_env"]
    api_key = os.getenv(key_env, "").strip()
    if not api_key:
        # Fail fast: mejor fallar al arrancar que a mitad de una petición.
        raise ValueError(f"Falta {key_env}. Agrégala a tu archivo .env")

    return Settings(
        llm_provider=provider,
        llm_model=os.getenv("LLM_MODEL", "openai/gpt-oss-120b").strip(),
        llm_temperature=_read_float("LLM_TEMPERATURE", "0.2"),
        llm_timeout_s=_read_float("LLM_TIMEOUT_S", "30"),
        llm_max_retries=int(os.getenv("LLM_MAX_RETRIES", "2").strip()),
        api_key=api_key,
        base_url=PROVIDERS[provider]["base_url"],
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
        input_cost_per_1m_tokens=_read_float("INPUT_COST_PER_1M_TOKENS", "0"),
        output_cost_per_1m_tokens=_read_float("OUTPUT_COST_PER_1M_TOKENS", "0"),
    )
