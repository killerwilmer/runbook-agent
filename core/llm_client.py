"""Cliente LLM independiente del proveedor, con métricas de uso en cada llamada."""

import time
from collections.abc import Callable
from dataclasses import dataclass

from openai import OpenAI

from core.config import get_settings
from core.logger import get_logger
from core.tokenlab import count_message_tokens, count_tokens

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
    ttft_ms: float | None = None

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def tokens_per_second(self) -> float | None:
        """Velocidad de generación: tokens de salida / tiempo desde el primer token."""
        if self.ttft_ms is None or self.latency_ms <= self.ttft_ms:
            return None
        return self.completion_tokens / ((self.latency_ms - self.ttft_ms) / 1000)


class LLMClient:
    def __init__(self, model: str | None = None, temperature: float | None = None) -> None:
        self.settings = get_settings()
        self.provider = self.settings.llm_provider
        self.model = model or self.settings.llm_model
        self.temperature = self.settings.llm_temperature if temperature is None else temperature
        self._client = OpenAI(
            api_key=self.settings.api_key,
            base_url=self.settings.base_url,
            timeout=self.settings.llm_timeout_s,
            max_retries=self.settings.llm_max_retries,
        )

    def chat(self, messages: list[Message] | str, max_tokens: int = 1024) -> LLMResponse:
        messages = self._normalize(messages)
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

        choice = response.choices[0]
        text = (choice.message.content or "").strip()
        usage = response.usage
        return self._finish(
            text,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            latency_ms=latency_ms,
            finish_reason=choice.finish_reason,
        )

    def stream(
        self,
        messages: list[Message] | str,
        on_token: Callable[[str], None] = lambda token: None,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Como chat(), pero entrega el texto a medida que llega y mide el TTFT."""
        messages = self._normalize(messages)
        started = time.perf_counter()
        ttft_ms: float | None = None
        parts: list[str] = []
        usage = None
        finish_reason: str | None = None

        try:
            chunks = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=max_tokens,
                stream=True,
                # Pide que el último chunk traiga el conteo real de tokens.
                stream_options={"include_usage": True},
            )
            for chunk in chunks:
                if chunk.usage:
                    usage = chunk.usage
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                if choice.finish_reason:  # llega en el último chunk con choices
                    finish_reason = choice.finish_reason
                token = choice.delta.content or ""
                if not token:
                    continue
                if ttft_ms is None:
                    ttft_ms = (time.perf_counter() - started) * 1000
                parts.append(token)
                on_token(token)
        except Exception as exc:
            logger.exception("Falló el stream | provider=%s model=%s", self.provider, self.model)
            raise RuntimeError("Falló la llamada al proveedor LLM.") from exc
        latency_ms = (time.perf_counter() - started) * 1000

        text = "".join(parts).strip()
        if usage:
            prompt_tokens, completion_tokens = (
                usage.prompt_tokens,
                usage.completion_tokens,
            )
        else:
            # Plan B: si el proveedor no reporta usage en streaming, estimamos con TokenLab.
            logger.warning("El proveedor no reportó usage; tokens estimados con TokenLab.")
            prompt_tokens = count_message_tokens(messages, self.model)
            completion_tokens = count_tokens(text, self.model)
        return self._finish(
            text, prompt_tokens, completion_tokens, latency_ms, ttft_ms, finish_reason
        )

    def _normalize(self, messages: list[Message] | str) -> list[Message]:
        # ¿Por qué aceptar str? Comodidad para pruebas rápidas: client.chat("hola").
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        if not messages:
            raise ValueError("messages no puede estar vacío.")
        return messages

    def _finish(
        self,
        text: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
        ttft_ms: float | None = None,
        finish_reason: str | None = None,
    ) -> LLMResponse:
        """Paso común a chat() y stream(): valida, calcula costo y registra métricas."""
        if not text:
            # ¿Por qué distinguir? "length" significa que se acabó max_tokens antes de escribir
            # la respuesta: típico de modelos que razonan. Un error que dice la causa ahorra horas.
            if finish_reason == "length":
                raise RuntimeError(
                    f"Respuesta vacía: se agotó max_tokens ({completion_tokens} tokens de salida, "
                    "probablemente razonando). Sube max_tokens o baja el esfuerzo de razonamiento."
                )
            raise RuntimeError(
                f"El LLM devolvió una respuesta vacía (finish_reason={finish_reason})."
            )
        result = LLMResponse(
            text=text,
            provider=self.provider,
            model=self.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            cost_usd=self._estimate_cost(prompt_tokens, completion_tokens),
            ttft_ms=ttft_ms,
        )
        self._log_usage(result)
        return result

    def _estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        # Los proveedores cobran por MILLÓN de tokens, con precios distintos para entrada y salida.
        s = self.settings
        return (
            prompt_tokens * s.input_cost_per_1m_tokens
            + completion_tokens * s.output_cost_per_1m_tokens
        ) / 1_000_000

    def _log_usage(self, r: LLMResponse) -> None:
        # Formato clave=valor: fácil de leer y fácil de procesar con grep o con herramientas de logs.
        ttft = f"{r.ttft_ms:.0f}" if r.ttft_ms is not None else "-"
        logger.info(
            "llm_call | provider=%s | model=%s | prompt_tokens=%d | completion_tokens=%d "
            "| ttft_ms=%s | latency_ms=%.0f | cost_usd=%.6f",
            r.provider,
            r.model,
            r.prompt_tokens,
            r.completion_tokens,
            ttft,
            r.latency_ms,
            r.cost_usd,
        )
