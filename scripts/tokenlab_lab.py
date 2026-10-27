"""Laboratorio de TokenLab: tokens, costo, latencia y temperatura en runbook-agent.

Uso:  uv run python -m scripts.tokenlab_lab
"""

from core.config import get_settings
from core.llm_client import LLMClient
from core.logger import setup_logger
from core.tokenlab import (
    BudgetExceededError,
    Pricing,
    check_budget,
    count_message_tokens,
    count_tokens,
    project_monthly_cost,
)

SYSTEM_PROMPT = (
    "Eres runbook-agent, un asistente para ingenieros de guardia (SRE/DevOps). "
    "Respondes en español, de forma concisa y con pasos accionables."
)

# Un fragmento típico de runbook; lo repetimos para simular documentos de distintos tamaños.
RUNBOOK_FRAGMENT = (
    "Si checkout-api devuelve 502, revisa el estado de los pods con kubectl get pods -n checkout. "
    "Si ves reinicios con OOMKilled, aumenta el límite de memoria o reinicia el deployment. "
    "Si hubo un deploy en la última hora, evalúa un rollback con aprobación del líder de guardia. "
)


def titulo(texto: str) -> None:
    print(f"\n{'=' * 70}\n {texto}\n{'=' * 70}")


def exp1_idiomas(model: str) -> None:
    titulo("1. Mismo mensaje en español e inglés")
    pares = [
        ("El servicio de pagos está caído", "The payments service is down"),
        (
            "Reinicia los pods que se quedaron sin memoria",
            "Restart the pods that ran out of memory",
        ),
        (
            "¿Cuál es el procedimiento de escalamiento?",
            "What is the escalation procedure?",
        ),
    ]
    for es, en in pares:
        t_es, t_en = count_tokens(es, model), count_tokens(en, model)
        print(f"ES {t_es:>3} | EN {t_en:>3} | ratio {t_es / t_en:.2f} | {es}")


def exp2_costo(model: str) -> None:
    titulo("2. Anatomía y costo de un request con RAG (proyección)")
    pricing = Pricing.from_settings()
    partes = {
        "system prompt": count_tokens(SYSTEM_PROMPT, model),
        "runbook recuperado (RAG)": count_tokens(RUNBOOK_FRAGMENT * 15, model),
        "pregunta del usuario": count_tokens("checkout-api da 502, ¿qué reviso?", model),
    }
    for nombre, tokens in partes.items():
        print(f"  {nombre:<26} {tokens:>6} tokens")
    entrada, salida = sum(partes.values()), 500
    print(f"  {'TOTAL entrada':<26} {entrada:>6} tokens  (+ ~{salida} de salida)")
    for por_dia in (100, 10_000, 100_000):
        mensual = project_monthly_cost(entrada, salida, por_dia, pricing)
        print(f"  {por_dia:>7} consultas/día → ${mensual:>10,.2f} USD/mes")


def exp3_latencia(client: LLMClient) -> None:
    titulo("3. Latencia vs tamaño del input (streaming, máx. 400 tokens de salida)")
    print(f"  {'tokens entrada':>14} {'TTFT ms':>9} {'total ms':>9} {'tokens/s':>9}")
    for repeticiones in (1, 20, 80):
        contexto = RUNBOOK_FRAGMENT * repeticiones
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"{contexto}\n\nResume este runbook en una línea.",
            },
        ]
        r = client.stream(messages, max_tokens=400)
        tps = f"{r.tokens_per_second:.0f}" if r.tokens_per_second is not None else "-"
        ttft = f"{r.ttft_ms:.0f}" if r.ttft_ms is not None else "-"
        print(f"  {r.prompt_tokens:>14} {ttft:>9} {r.latency_ms:>9.0f} {tps:>9}")


def exp4_temperatura() -> None:
    titulo("4. Temperatura: la misma pregunta 3 veces")
    pregunta = (
        "Clasifica la severidad (SEV1, SEV2, SEV3 o SEV4) y justifica en una frase: "
        "'el login falla para el 30% de los usuarios desde hace 5 minutos'."
    )
    for temperatura in (0.0, 1.2):
        client = LLMClient(temperature=temperatura)
        print(f"\n  temperature={temperatura}")
        for i in range(3):
            r = client.chat(pregunta, max_tokens=200)
            print(f"   {i + 1}. {r.text.replace(chr(10), ' ')[:110]}")


def exp5_presupuesto(model: str) -> None:
    titulo("5. Presupuesto por feature")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": RUNBOOK_FRAGMENT * 20 + "\n¿Qué severidad tiene?"},
    ]
    print(f"  El request usa ~{count_message_tokens(messages, model)} tokens de entrada")
    for feature in ("clasificar_severidad", "responder_con_runbook"):
        try:
            budget = check_budget(feature, messages, model)
            print(f"  ✅ {feature}: cabe (máx. salida {budget.max_output_tokens})")
        except BudgetExceededError as exc:
            print(f"  ❌ {exc}")


def main() -> None:
    setup_logger("WARNING")  # el laboratorio imprime sus propias tablas
    model = get_settings().llm_model
    exp1_idiomas(model)
    exp2_costo(model)
    exp5_presupuesto(model)
    exp3_latencia(LLMClient())
    exp4_temperatura()


if __name__ == "__main__":
    main()
