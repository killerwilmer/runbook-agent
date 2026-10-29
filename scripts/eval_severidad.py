"""Compara las versiones del prompt de severidad contra el golden set.

Uso:  uv run python -m scripts.eval_severidad                 (todas las versiones)
      uv run python -m scripts.eval_severidad --versiones 1 3 --delay 2
"""

import argparse

from core.config import get_settings
from core.llm_client import LLMClient
from core.logger import setup_logger
from core.tokenlab import BUDGETS, count_message_tokens
from prompting.evaluation import EvalReport, evaluate, load_golden_set
from prompting.promptkit import PromptTemplate, registry
from prompting.severidad import SEVERIDADES

GOLDEN_SET = "data/golden/severidad.json"


def imprimir_tabla(reports: list[EvalReport]) -> None:
    print(
        f"\n{'prompt':<26} {'accuracy':>8} {'JSON':>6} {'subestimó':>9} {'errores':>7} "
        f"{'tokens':>7} {'latencia':>9} {'costo':>10}"
    )
    for r in reports:
        print(
            f"{r.prompt:<26} {r.accuracy:>8.0%} {r.json_validos:>3}/{r.total:<2} "
            f"{r.subestimados:>9} {r.errores_llamada:>7} {r.tokens_promedio:>7.0f} "
            f"{r.latencia_promedio_ms:>7.0f}ms ${r.cost_usd:>9.6f}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Evalúa los prompts de severidad.")
    parser.add_argument("--versiones", type=int, nargs="+", default=[1, 2, 3, 4])
    parser.add_argument("--delay", type=float, default=1.0, help="segundos entre llamadas")
    args = parser.parse_args()

    setup_logger("WARNING")
    casos = load_golden_set(GOLDEN_SET)
    # temperature=0: para clasificar queremos la respuesta más probable, no creatividad.
    client = LLMClient(temperature=0.0)
    budget = BUDGETS["clasificar_severidad"]
    print(f"Modelo: {get_settings().llm_provider} / {client.model} · {len(casos)} casos")

    reports = []
    for version in args.versiones:
        prompt = registry.get("clasificar_severidad", version)
        if isinstance(prompt, PromptTemplate):
            entrada = count_message_tokens(prompt.render(incidente=casos[0].input), client.model)
            cabe = "✅" if entrada <= budget.max_input_tokens else "❌"
            extra = f" · entrada ~{entrada} tokens {cabe} (presupuesto {budget.max_input_tokens})"
        else:
            extra = f" · cadena de {len(prompt.steps)} pasos"
        print(f"\n▶ {prompt.key}: {prompt.description}{extra}")

        report = evaluate(
            prompt,
            client,
            casos,
            variable="incidente",
            campo="severidad",
            valores=SEVERIDADES,
            delay_s=args.delay,
            max_tokens=budget.max_output_tokens,
        )
        for fallo in report.fallos:
            print(f"   ✗ {fallo}")
        reports.append(report)

    imprimir_tabla(reports)


if __name__ == "__main__":
    main()
