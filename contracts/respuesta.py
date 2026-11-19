"""Contrato de una respuesta con fuentes: qué dice y en qué fragmentos se apoya."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RespuestaRAG(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Primero decide SI las fuentes alcanzan; después responde. Mismo truco del orden de campos.
    encontrada: bool = Field(description="true solo si las fuentes contienen la respuesta.")
    respuesta: str = Field(
        max_length=1500,
        description="La respuesta en español, con pasos concretos. Si no hay información, dilo.",
    )
    citas: list[int] = Field(
        description="Números de las fuentes que usaste, por ejemplo [1, 3]. Vacía si no hay."
    )

    @model_validator(mode="after")
    def _citas_coherentes(self) -> Self:
        # El mensaje nombra LAS DOS salidas posibles: si solo dijera "cita una fuente", el modelo
        # inventaría una cita en vez de admitir que no encontró la respuesta.
        if self.encontrada and not self.citas:
            raise ValueError(
                "si encontraste la respuesta, cita al menos una fuente; "
                "si las fuentes no la contienen, marca encontrada=false"
            )
        if not self.encontrada and self.citas:
            raise ValueError("si no encontraste la respuesta, citas debe ser una lista vacía")
        return self
