"""Tools: funciones que el modelo puede PEDIR ejecutar, con argumentos validados por Pydantic."""

import json
from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from core.llm_client import LLMClient, LLMResponse, Message
from core.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class Tool:
    name: str
    description: str  # documentación PARA EL MODELO: de esto depende que la elija bien
    args_model: type[BaseModel]
    fn: Callable[[BaseModel], BaseModel]

    def spec(self) -> dict:
        """La definición que viaja al proveedor. El JSON Schema sale del modelo Pydantic."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_model.model_json_schema(),
            },
        }

    def run(self, arguments: str) -> str:
        """Valida los argumentos que generó el modelo, ejecuta la función y devuelve JSON."""
        try:
            args = self.args_model.model_validate_json(arguments)
        except ValidationError as exc:
            # No se cae el programa: el error vuelve al modelo para que corrija los argumentos.
            errores = [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()]
            return json.dumps(
                {"error": "argumentos inválidos", "detalle": errores}, ensure_ascii=False
            )
        return self.fn(args).model_dump_json()


def chat_con_tools(
    client: LLMClient, messages: list[Message], tools: list[Tool], max_rondas: int = 3
) -> LLMResponse:
    """Conversa con el modelo dejándolo usar tools hasta que dé una respuesta final."""
    messages = list(messages)  # copia: no modificamos la lista de quien llama
    por_nombre = {t.name: t for t in tools}
    specs = [t.spec() for t in tools]
    # ¿Por qué un máximo? Un modelo puede pedir tools en bucle; cada ronda cuesta tokens.
    for _ in range(max_rondas):
        r = client.chat(messages, tools=specs)
        if not r.tool_calls:
            return r  # respuesta final en texto
        messages.append(
            {
                "role": "assistant",
                "content": r.text,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": tc.arguments},
                    }
                    for tc in r.tool_calls
                ],
            }
        )
        for tc in r.tool_calls:
            tool = por_nombre.get(tc.name)
            resultado = (
                tool.run(tc.arguments) if tool else json.dumps({"error": "tool inexistente"})
            )
            logger.info(
                "tool_call | name=%s | args=%s | result=%s", tc.name, tc.arguments, resultado
            )
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": resultado})
    raise RuntimeError(f"Sin respuesta final después de {max_rondas} rondas de tools.")
