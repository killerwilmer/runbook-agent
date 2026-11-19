"""Ingesta: de archivos a Documents con metadatos, y de Documents a Chunks listos para indexar."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

from core.logger import get_logger
from core.tokenlab import count_tokens

logger = get_logger(__name__)

# Lo único que ChromaDB acepta como valor de un metadato.
MetaValue = str | int | float | bool


@dataclass(frozen=True)
class Document:
    doc_id: str  # ruta relativa sin extensión: "runbooks/checkout-api". Única y estable.
    title: str
    content: str
    metadata: dict[str, MetaValue]


@dataclass(frozen=True)
class Chunk:
    chunk_id: str  # "runbooks/checkout-api#3": el mismo documento genera siempre los mismos ids
    text: str
    metadata: dict[str, MetaValue]


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Separa el bloque YAML entre '---' del inicio. Devuelve (metadatos, cuerpo)."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    meta = yaml.safe_load(text[4:end]) or {}
    return meta, text[end + 5 :]


def _clean_metadata(raw: dict) -> dict[str, MetaValue]:
    # ChromaDB rechaza None, listas o fechas. YAML convierte "2026-10-12" en un date:
    # lo pasamos a texto ISO, que además se puede comparar y ordenar como string.
    clean: dict[str, MetaValue] = {}
    for key, value in raw.items():
        if value is None:
            continue
        if isinstance(value, date):
            value = value.isoformat()
        clean[key] = value if isinstance(value, MetaValue) else str(value)
    return clean


def load_document(path: Path, root: Path) -> Document:
    """Carga un .md o .txt. Los metadatos salen de la carpeta y del frontmatter."""
    text = path.read_text(encoding="utf-8")
    meta, body = _split_frontmatter(text) if path.suffix == ".md" else ({}, text)
    relative = path.relative_to(root)
    doc_id = relative.with_suffix("").as_posix()
    # El título es el primer "# ..." del documento; si no hay, el nombre del archivo.
    title = next(
        (line[2:].strip() for line in body.splitlines() if line.startswith("# ")), path.stem
    )
    metadata = _clean_metadata(
        {"doc_id": doc_id, "source": relative.as_posix(), "tipo": relative.parts[0], **meta}
    )
    return Document(doc_id, title, body.strip(), metadata)


SUPPORTED = {".md", ".txt"}


def load_directory(root: str | Path) -> list[Document]:
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(f"No existe el directorio de documentos: {root}")
    docs = [load_document(p, root) for p in sorted(root.rglob("*")) if p.suffix in SUPPORTED]
    logger.info("Cargados %d documentos desde %s", len(docs), root)
    return docs


def _sections(content: str) -> list[tuple[str, list[str]]]:
    """Divide el texto en secciones (por encabezados) y cada sección en párrafos."""
    sections: list[tuple[str, list[str]]] = []
    heading, paragraphs = "", []
    for block in content.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if block.startswith("#"):
            first_line, _, rest = block.partition("\n")  # un encabezado pegado a su texto
            if paragraphs:
                sections.append((heading, paragraphs))
            heading, paragraphs = first_line.lstrip("#").strip(), []
            if rest.strip():
                paragraphs.append(rest.strip())
        else:
            paragraphs.append(block)
    if paragraphs:
        sections.append((heading, paragraphs))
    return sections


def chunk_document(
    doc: Document,
    max_tokens: int = 300,
    overlap: int = 1,
    count: Callable[[str], int] = count_tokens,
) -> list[Chunk]:
    """Agrupa párrafos de una misma sección hasta max_tokens, repitiendo `overlap` párrafos."""
    chunks: list[Chunk] = []

    def emit(section: str, paragraphs: list[str]) -> None:
        # El encabezado viaja DENTRO del texto: "Paso 2: escala a 5 réplicas" solo no dice de
        # qué servicio habla; con "Runbook: checkout-api › Mitigación" delante, sí.
        header = f"{doc.title} › {section}" if section and section != doc.title else doc.title
        text = header + "\n\n" + "\n\n".join(paragraphs)
        index = len(chunks)
        chunks.append(
            Chunk(
                chunk_id=f"{doc.doc_id}#{index}",
                text=text,
                metadata={**doc.metadata, "seccion": section, "chunk_index": index},
            )
        )

    for section, paragraphs in _sections(doc.content):
        group: list[str] = []
        for paragraph in paragraphs:
            if group and count("\n\n".join([*group, paragraph])) > max_tokens:
                emit(section, group)
                # Overlap: los últimos párrafos se repiten al inicio del siguiente chunk para no
                # perder la continuidad. Nunca cruza secciones: un encabezado es un corte natural.
                group = group[-overlap:] if overlap else []
            group.append(paragraph)
        if group:
            emit(section, group)
    return chunks
