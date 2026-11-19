"""Pregúntale a runbook-agent: busca en los documentos indexados y responde citando las fuentes.

Uso:  uv run python -m scripts.preguntar "checkout-api devuelve 502 después del deploy"
      uv run python -m scripts.preguntar "¿cómo hago rollback?" --tipo runbooks --k 3
"""

import argparse

from core.llm_client import ContractError, LLMClient
from core.logger import setup_logger
from rag.answer import responder
from rag.vectorstore import VectorStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Pregunta sobre los runbooks y postmortems.")
    parser.add_argument("pregunta")
    parser.add_argument("--k", type=int, default=4, help="cuántos fragmentos recuperar")
    parser.add_argument("--tipo", choices=["runbooks", "postmortems", "guias"])
    parser.add_argument("--servicio")
    args = parser.parse_args()
    setup_logger("WARNING")  # solo avisos: la salida de este script es la respuesta

    filtros = [{"tipo": args.tipo}] if args.tipo else []
    filtros += [{"servicio": args.servicio}] if args.servicio else []
    # Chroma pide $and para combinar dos o más condiciones.
    where = {"$and": filtros} if len(filtros) > 1 else (filtros[0] if filtros else None)

    store = VectorStore()
    if store.count() == 0:
        raise SystemExit("El índice está vacío. Corre primero: uv run python -m scripts.indexar")
    try:
        r = responder(args.pregunta, store, LLMClient(temperature=0.0), args.k, where)
    except ContractError as exc:
        raise SystemExit(f"❌ {exc}")

    print("\n📚 Fragmentos recuperados:")
    for i, f in enumerate(r.fuentes, start=1):
        marca = "→" if f in r.citadas else " "
        print(f" {marca} [{i}] {f.score:.3f}  {f.chunk_id}  ({f.metadata['seccion'] or '-'})")

    icono = "✅" if r.respuesta.encontrada else "🤷"
    print(f"\n{icono} {r.respuesta.respuesta}")
    if r.citadas:
        # dict.fromkeys quita repetidos sin perder el orden (dos chunks del mismo archivo).
        print("\nFuentes: " + ", ".join(dict.fromkeys(f.metadata["source"] for f in r.citadas)))
    p = r.parsed
    print(f"\n({p.total_tokens} tokens · {p.latency_ms:.0f} ms · intentos: {p.attempts})")


if __name__ == "__main__":
    main()
