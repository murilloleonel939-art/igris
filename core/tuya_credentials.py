"""Cifrado de las credenciales de Tuya que introduce cada usuario.

El Access Secret de Tuya da control total sobre los dispositivos de una casa.
Guardarlo en claro en la base de datos lo expone en cualquier copia de
seguridad, volcado o consulta de soporte. Aquí se cifra con Fernet (AES-128 en
modo CBC con HMAC) usando una clave derivada de la SECRET_KEY del servidor.

Por qué derivar y no usar otra variable: si la SECRET_KEY cambia, los usuarios
tienen que volver a entrar igualmente. Añadir una segunda variable que puede
faltar solo crea otro modo de fallo silencioso. La clave se deriva de forma
determinista, así que el mismo despliegue siempre descifra lo que cifró.

Consecuencia a tener en cuenta: si la SECRET_KEY cambia, los secretos de Tuya
guardados dejan de poder descifrarse y el usuario tendrá que volver a pegarlos.
Es preferible a que queden ilegibles para siempre sin que nadie lo note: el
descifrado falla de forma visible y el panel pide reconectar.
"""

from __future__ import annotations

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

from core.auth import SECRET_KEY

logger = logging.getLogger(__name__)

# Fernet exige 32 bytes codificados en base64url. Se derivan de la SECRET_KEY
# con SHA-256 para no depender de la longitud original.
_key = base64.urlsafe_b64encode(hashlib.sha256(SECRET_KEY.encode("utf-8")).digest())
_fernet = Fernet(_key)


def encrypt_secret(value: str) -> str:
    """Cifra un secreto para guardarlo. Devuelve texto ASCII seguro."""
    if not value:
        return ""
    return _fernet.encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str) -> str:
    """Descifra un secreto guardado.

    Devuelve "" si el valor está corrupto o se cifró con otra SECRET_KEY. No se
    lanza la excepción hacia arriba: un secreto ilegible debe tratarse como
    "no configurado" para que el panel pida reconectar, en lugar de romper la
    petición con un error 500 que no explica nada.
    """
    if not value:
        return ""
    try:
        return _fernet.decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeDecodeError):
        logger.warning(
            "No se pudo descifrar un secreto de Tuya: probablemente se guardó "
            "con otra SECRET_KEY. El usuario tendrá que volver a introducirlo."
        )
        return ""
