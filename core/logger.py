"""Configuración de logging con salida bonita en consola (rich)."""

import logging

from rich.logging import RichHandler


def setup_logger(level: str = "INFO") -> None:
    """Configura el logger raíz. Se llama UNA vez, al inicio del programa."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(message)s",
        datefmt="%H:%M:%S",
        handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
    )
    logging.getLogger("httpx2").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Cada módulo pide su logger con get_logger(__name__) para saber de dónde viene cada mensaje."""
    return logging.getLogger(name)
