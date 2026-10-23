"""Hello AI System: punto de entrada."""

from core.config import get_settings
from core.llm_client import LLMClient
from core.logger import get_logger, setup_logger

logger = get_logger(__name__)


def main() -> None:
    setup_logger(get_settings().log_level)
    client = LLMClient()

    user_prompt = input("Ingresa tu mensaje: ")
    try:
        r = client.chat([
            {
                "role": "system",
                "content": (
                    "Eres runbook-agent, un asistente para ingenieros de guardia (SRE/DevOps). "
                    "Respondes en español, de forma concisa y con pasos accionables."
                ),
            },
            {"role": "user", "content": user_prompt},
        ])
    except RuntimeError:
        raise SystemExit(1)  # el detalle ya quedó en el log

    print(f"\n=== Respuesta ===\n{r.text}\n")
    print("=== Métricas ===")
    print(f"proveedor/modelo : {r.provider} / {r.model}")
    print(f"tokens           : {r.prompt_tokens} entrada + {r.completion_tokens} salida = {r.total_tokens}")
    print(f"latencia         : {r.latency_ms:.0f} ms")
    print(f"costo estimado   : ${r.cost_usd:.6f} USD")


if __name__ == "__main__":
    main()
