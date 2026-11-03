"""Tools de infraestructura. Por ahora SIMULADAS: leen un JSON en vez de Kubernetes."""

import json
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from contracts.incidente import Servicio
from tools.base import Tool

LOGS = Path("data/infra/logs")
# Reloj SIMULADO: los logs son de un escenario fijo. Con datetime.now() la tool devolvería
# siempre vacío. Cuando conectes logs reales, este valor pasa a ser datetime.now(UTC).
AHORA = datetime(2026, 10, 28, 14, 30, tzinfo=UTC)
MAX_LINEAS = 50  # tope: los logs pueden ser enormes y cada línea son tokens

DATOS = Path("data/infra/servicios.json")


class EstadoServicioArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    servicio: Servicio = Field(description="Nombre exacto del servicio a consultar.")


class EstadoServicio(BaseModel):
    servicio: Servicio
    estado: Literal["ok", "degradado", "caido"]
    pods_listos: str = Field(description="Pods listos / pods deseados, por ejemplo '2/3'.")
    error_rate_pct: float
    latencia_p99_ms: int
    ultimo_deploy: str
    alertas: list[str]


@lru_cache(maxsize=1)
def _estados() -> dict[str, EstadoServicio]:
    with open(DATOS, encoding="utf-8") as f:
        estados = {item["servicio"]: EstadoServicio(**item) for item in json.load(f)}
    # El enum manda: si agregas un servicio y olvidas sus datos, falla aquí, no a mitad de un chat.
    faltan = set(Servicio) - estados.keys()
    if faltan:
        raise ValueError(f"{DATOS} no tiene datos de: {sorted(faltan)}")
    return estados


def estado_servicio(args: EstadoServicioArgs) -> EstadoServicio:
    return _estados()[args.servicio]


ESTADO_SERVICIO = Tool(
    name="estado_servicio",
    description=(
        "Devuelve el estado actual de un servicio de producción: pods listos, tasa de errores, "
        "latencia p99, último deploy y alertas activas. Úsala antes de diagnosticar un servicio."
    ),
    args_model=EstadoServicioArgs,
    fn=estado_servicio,
)


class LeerLogsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    servicio: Servicio = Field(description="Nombre exacto del servicio.")
    ultimos_minutos: int = Field(
        ge=1, le=60, description="Ventana de tiempo hacia atrás, en minutos."
    )


class LogsServicio(BaseModel):
    servicio: Servicio
    desde: str
    lineas: list[str]
    truncado: bool = Field(description="true si había más líneas que el máximo devuelto.")


def leer_logs(args: LeerLogsArgs) -> LogsServicio:
    desde = AHORA - timedelta(minutes=args.ultimos_minutos)
    archivo = LOGS / f"{args.servicio}.log"
    lineas = archivo.read_text(encoding="utf-8").splitlines() if archivo.exists() else []
    # Cada línea empieza con un timestamp ISO; se compara como fecha, no como texto.
    # linea.strip() salta las líneas vacías: fromisoformat("") lanzaría ValueError y tumbaría el chat.
    recientes = [
        linea
        for linea in lineas
        if linea.strip() and datetime.fromisoformat(linea.split(" ", 1)[0]) >= desde
    ]
    return LogsServicio(
        servicio=args.servicio,
        desde=desde.isoformat(),
        lineas=recientes[-MAX_LINEAS:],  # las más recientes
        truncado=len(recientes) > MAX_LINEAS,
    )


LEER_LOGS = Tool(
    name="leer_logs",
    description=(
        "Devuelve las líneas de log de un servicio en los últimos N minutos (máximo 60). "
        "Úsala para encontrar la causa de un error después de revisar estado_servicio."
    ),
    args_model=LeerLogsArgs,
    fn=leer_logs,
)
