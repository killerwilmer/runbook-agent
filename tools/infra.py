"""Tools de infraestructura. Por ahora SIMULADAS: leen un JSON en vez de Kubernetes."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from contracts.incidente import Servicio
from tools.base import Tool

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
        # Validar los datos simulados también: si el JSON está mal, falla aquí y no en el modelo.
        return {item["servicio"]: EstadoServicio(**item) for item in json.load(f)}


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
