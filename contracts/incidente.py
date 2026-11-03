"""Contrato de un incidente: la forma exacta que el resto del sistema puede usar sin dudar."""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Severidad(StrEnum):
    SEV1 = "SEV1"
    SEV2 = "SEV2"
    SEV3 = "SEV3"
    SEV4 = "SEV4"


class Servicio(StrEnum):
    CHECKOUT_API = "checkout-api"
    PAYMENTS_API = "payments-api"
    AUTH_SERVICE = "auth-service"
    CATALOG_SERVICE = "catalog-service"
    SEARCH_SERVICE = "search-service"
    NOTIFICATIONS_WORKER = "notifications-worker"
    ADMIN_DASHBOARD = "admin-dashboard"
    REPORTS_BATCH = "reports-batch"
    DESCONOCIDO = "desconocido"


SERVICIOS_CRITICOS = frozenset(
    {Servicio.CHECKOUT_API, Servicio.PAYMENTS_API, Servicio.AUTH_SERVICE, Servicio.CATALOG_SERVICE}
)


class Incidente(BaseModel):
    """Un incidente extraído de un reporte en texto libre."""

    # extra="forbid": un campo que no está en el contrato es un error, no un dato más.
    model_config = ConfigDict(extra="forbid")

    # El orden importa: el modelo genera los campos en este orden, así que primero
    # registra los hechos y DESPUÉS decide la severidad con esos hechos a la vista.
    servicio: Servicio = Field(description="Servicio afectado; 'desconocido' si no se menciona.")
    sintoma: str = Field(min_length=3, max_length=200, description="El problema en una frase.")
    usuarios_afectados_pct: int | None = Field(
        ge=0, le=100, description="Porcentaje de usuarios afectados, o null si no se sabe."
    )
    perdida_datos_o_dinero: bool = Field(
        description="true si se pierden datos o hay cobros mal hechos."
    )
    severidad: Severidad
    justificacion: str = Field(max_length=300, description="Por qué esa severidad, en una frase.")

    @model_validator(mode="after")
    def _perdida_en_critico_es_sev1(self) -> Self:
        # Una regla de negocio que el modelo NO puede saltarse, la diga o no el prompt.
        if (
            self.perdida_datos_o_dinero
            and self.servicio in SERVICIOS_CRITICOS
            and self.severidad is not Severidad.SEV1
        ):
            raise ValueError("pérdida de datos o dinero en un servicio crítico siempre es SEV1")
        return self
