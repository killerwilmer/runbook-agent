"""runbook-agent: chat por consola con streaming y control de presupuesto."""

from core.config import get_settings
from core.llm_client import LLMClient
from core.logger import get_logger, setup_logger
from core.tokenlab import BudgetExceededError, check_budget

logger = get_logger(__name__)

SYSTEM_PROMPT = (
    "Eres runbook-agent, un asistente para ingenieros de guardia (SRE/DevOps). "
    "Respondes en español, de forma concisa y con pasos accionables."
)


def main() -> None:
    setup_logger(get_settings().log_level)
    client = LLMClient()

    user_prompt = input("Ingresa tu mensaje: ")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    try:
        # 1) Validar el presupuesto ANTES de gastar un solo token.
        budget = check_budget("chat_general", messages, client.model)
        # 2) Streaming: el usuario ve la respuesta mientras se genera.
        print("\n=== Respuesta ===")
        r = client.stream(
            messages,
            on_token=lambda token: print(token, end="", flush=True),
            max_tokens=budget.max_output_tokens,
        )
    except BudgetExceededError as exc:
        logger.error("%s", exc)
        raise SystemExit(1)
    except RuntimeError:
        raise SystemExit(1)  # el detalle ya quedó en el log

    tps = f"{r.tokens_per_second:.0f} tokens/s" if r.tokens_per_second is not None else "-"
    print("\n\n=== Métricas ===")
    print(f"proveedor/modelo : {r.provider} / {r.model}")
    print(
        f"tokens           : {r.prompt_tokens} entrada + {r.completion_tokens} salida = {r.total_tokens}"
    )
    print(
        f"TTFT             : {r.ttft_ms:.0f} ms"
        if r.ttft_ms is not None
        else "TTFT             : -"
    )
    print(f"latencia total   : {r.latency_ms:.0f} ms ({tps})")
    print(f"costo estimado   : ${r.cost_usd:.6f} USD")


if __name__ == "__main__":
    main()
