"""Identificadores de mensajes independientes del idioma y de la interfaz."""
from types import MappingProxyType


class Message(str):
    """Código estable y parámetros; convertir a str nunca realiza traducciones.

    La base str permite persistir el identificador en CSV/JSON sin conocer una
    capa de presentación. Los parámetros se conservan para presentar errores.
    """
    def __new__(cls, code: str, /, **parameters):
        instance = super().__new__(cls, code)
        instance.parameters = MappingProxyType(dict(parameters))
        return instance

    @property
    def code(self) -> str:
        return str(self)


def message(code: str, /, **parameters) -> Message:
    return Message(code, **parameters)
