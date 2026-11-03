"""Demo: de texto libre a un Incidente validado, y la primera tool con function calling.

Uso:  uv run python -m scripts.demo_contratos
"""

from contracts.incidente import Incidente
from core.llm_client import ContractError, LLMClient
from core.logger import setup_logger
from core.tokenlab import BUDGETS
from prompting.incidente import EXTRAER_INCIDENTE_V2
from tools.base import chat_con_tools
from tools.infra import ESTADO_SERVICIO, LEER_LOGS

REPORTES = [
    "Desde el deploy de las 14:00 payments-api cobra dos veces cada compra, nos están llamando clientes.",
    "algo raro pasa con el login, a varios compañeros no les deja entrar",
    "checkout-api p99 latency is 3 s for 5% of requests, no errors.",
]


def titulo(texto: str) -> None:
    print(f"\n{'=' * 70}\n {texto}\n{'=' * 70}")


def demo_extraccion(client: LLMClient) -> None:
    titulo("1. Texto libre -> Incidente validado (structured outputs + Pydantic)")
    for reporte in REPORTES:
        print(f"\n📝 {reporte}")
        try:
            p = client.parse(
                EXTRAER_INCIDENTE_V2.render(incidente=reporte),
                Incidente,
                max_tokens=BUDGETS["extraer_incidente"].max_output_tokens,
            )
        except ContractError as exc:
            print(f"   ❌ {exc}")
            continue
        i = p.value  # un objeto Incidente: autocompletado, tipos y reglas garantizadas
        pct = f"{i.usuarios_afectados_pct} %" if i.usuarios_afectados_pct is not None else "¿?"
        print(f"   [{i.severidad}] {i.servicio or '¿?'} · {i.sintoma}")
        print(f"   usuarios: {pct} · pérdida: {i.perdida_datos_o_dinero} · intentos: {p.attempts}")
        print(f"   ↳ {i.justificacion}")


def demo_tool(client: LLMClient) -> None:
    titulo("2. Function calling: el modelo decide qué tools consultar")
    messages = [
        {
            "role": "system",
            "content": (
                "Eres el ingeniero de guardia de una tienda online. Antes de opinar sobre un "
                "servicio, consulta su estado con las tools. Responde en español, en 3 líneas."
            ),
        },
        {"role": "user", "content": "¿Por qué falla checkout-api?"},
    ]
    r = chat_con_tools(client, messages, [ESTADO_SERVICIO, LEER_LOGS], max_rondas=4)
    print(f"\n{r.text}")


def main() -> None:
    setup_logger("INFO")  # INFO para ver las líneas tool_call y llm_call
    client = LLMClient(temperature=0.0)
    demo_extraccion(client)
    demo_tool(client)


if __name__ == "__main__":
    main()
