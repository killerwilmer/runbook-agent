"""Cliente LLM independiente del proveedor, con métricas de uso en cada llamada."""

import time
from dataclasses import dataclass

from openai import OpenAI

from core.config import get_settings
from core.logger import get_logger

logger = get_logger(__name__)

Message = dict[str, str]  # {"role": "system" | "user" | "assistant", "content": "..."}


@dataclass(frozen=True)
class LLMResponse:
    """Lo que devuelve el cliente: el texto + todo lo necesario para auditar la llamada."""

    text: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    cost_usd: float

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class LLMClient:
    def __init__(self, model: str | None = None, temperature: float | None = None) -> None:
        self.settings = get_settings()
        self.provider = self.settings.llm_provider
        self.model = model or self.settings.llm_model
        self.temperature = self.settings.llm_temperature if temperature is None else temperature
        self._client = OpenAI(api_key=self.settings.api_key, base_url=self.settings.base_url)

    def chat(self, messages: list[Message] | str, max_tokens: int = 1024) -> LLMResponse:
        # ¿Por qué aceptar str? Comodidad para pruebas rápidas: client.chat("hola").
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        if not messages:
            raise ValueError("messages no puede estar vacío.")

        started = time.perf_counter()  # perf_counter es el reloj correcto para medir duraciones
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            # logger.exception registra el traceback completo; luego relanzamos un error
            # de NUESTRO dominio para que quien llama no dependa de las excepciones del SDK.
            logger.exception("Falló la llamada | provider=%s model=%s", self.provider, self.model)
            raise RuntimeError("Falló la llamada al proveedor LLM.") from exc
        latency_ms = (time.perf_counter() - started) * 1000

        text = (response.choices[0].message.content or "").strip()
        if not text:
            raise RuntimeError("El LLM devolvió una respuesta vacía.")

        usage = response.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0

        result = LLMResponse(
            text=text,
            provider=self.provider,
            model=self.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            cost_usd=self._estimate_cost(prompt_tokens, completion_tokens),
        )
        self._log_usage(result)
        return result

    def _estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        # Los proveedores cobran por MILLÓN de tokens, con precios distintos para entrada y salida.
        s = self.settings
        return (prompt_tokens * s.input_cost_per_1m_tokens
                + completion_tokens * s.output_cost_per_1m_tokens) / 1_000_000

    def _log_usage(self, r: LLMResponse) -> None:
        # Formato clave=valor: fácil de leer y fácil de procesar con grep o con herramientas de logs.
        logger.info(
            "llm_call | provider=%s | model=%s | prompt_tokens=%d | completion_tokens=%d "
            "| latency_ms=%.0f | cost_usd=%.6f",
            r.provider, r.model, r.prompt_tokens, r.completion_tokens, r.latency_ms, r.cost_usd,
        )
