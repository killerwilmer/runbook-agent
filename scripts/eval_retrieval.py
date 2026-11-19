"""Mide si la búsqueda encuentra el documento correcto para cada pregunta del golden set.

Uso:  uv run python -m scripts.eval_retrieval
      uv run python -m scripts.eval_retrieval --k 1 3 5
"""

import argparse

from rag.evaluation import evaluate_retrieval, load_retrieval_set
from rag.vectorstore import VectorStore

GOLDEN = "data/golden/retrieval.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Evalúa el retrieval contra el golden set.")
    parser.add_argument("--k", type=int, nargs="+", default=[1, 3, 5])
    args = parser.parse_args()

    store = VectorStore()
    if store.count() == 0:
        raise SystemExit("El índice está vacío. Corre primero: uv run python -m scripts.indexar")
    casos = load_retrieval_set(GOLDEN)
    print(f"{len(casos)} preguntas · {store.count()} chunks · modelo {store.embedder.model_name}\n")

    reports = [evaluate_retrieval(casos, store.search, k) for k in args.k]
    print(f"{'k':>3} {'hit rate':>9} {'MRR':>6}")
    for r in reports:
        print(f"{r.k:>3} {r.hit_rate:>8.0%} {r.mrr:>6.2f}")

    # Los fallos del k más grande son los más interesantes: ni buscando más lejos aparece.
    peor = reports[-1]
    if peor.fallos:
        print(f"\nFallos con k={peor.k}:")
        for fallo in peor.fallos:
            print(f"  ✗ {fallo}")


if __name__ == "__main__":
    main()
