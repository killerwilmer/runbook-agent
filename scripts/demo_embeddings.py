"""Demo: textos con significado parecido quedan cerca, aunque no compartan palabras.

Uso:  uv run python -m scripts.demo_embeddings
"""

from rag.embeddings import cosine_similarity, get_embedder

PREGUNTA = "el pod se reinicia porque se queda sin memoria"
TEXTOS = [
    "El contenedor terminó con OOMKilled al superar su límite de 2Gi",
    "Pods reiniciándose por falta de memoria",
    "El certificado TLS del balanceador vence en 20 días",
    "Los clientes reportan cobros duplicados en payments-api",
]


def main() -> None:
    embedder = get_embedder()
    q = embedder.embed_query(PREGUNTA)
    print(f"Modelo: {embedder.model_name} · {embedder.dimension} dimensiones")
    print(f"Primeros 5 valores de la pregunta: {[round(x, 3) for x in q[:5]]}\n")
    scores = [cosine_similarity(q, v) for v in embedder.embed_documents(TEXTOS)]
    for score, texto in sorted(zip(scores, TEXTOS, strict=True), reverse=True):
        print(f"  {score:.3f}  {texto}")


if __name__ == "__main__":
    main()
