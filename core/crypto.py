"""Cifrado de secretos guardados en la base de datos.

Hoy solo se usa para los refresh tokens de Google de cada usuario: son
credenciales de larga duración que dan acceso al correo y al calendario, así que
NO pueden quedar en claro en la tabla (un volcado de la base o un backup los
expondría).

La clave se deriva de SECRET_KEY con HKDF-SHA256: se usa una etiqueta distinta
("igris:field-encryption:v1"), de modo que la clave que cifra los datos NO es la
misma que firma los tokens. Así, conocer una no compromete la otra.

Si SECRET_KEY cambia (por ejemplo, alguien la rota en Coolify sin avisar), los
tokens guardados dejan de poder descifrarse. En ese caso decrypt() devuelve None
y el usuario simplemente tiene que volver a conectar su cuenta de Google: no se
rompe nada más.
"""

import base64
import hashlib
import hmac
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_INFO = b"igris:field-encryption:v1"


def _fernet():
    """Fernet derivado de SECRET_KEY, o None si falta la dependencia."""
    try:
        from cryptography.fernet import Fernet
    except Exception:  # pragma: no cover - cryptography llega con python-jose
        logger.error("Falta 'cryptography': los secretos de Google no se pueden cifrar")
        return None

    from core.auth import SECRET_KEY

    # HKDF (RFC 5869) en versión corta: solo se necesita una clave de 32 bytes.
    prk = hmac.new(b"igris-hkdf-salt-v1", SECRET_KEY.encode("utf-8"), hashlib.sha256).digest()
    key = hmac.new(prk, _INFO, hashlib.sha256).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt(plaintext: Optional[str]) -> Optional[str]:
    """Cifra un texto. Devuelve None si la entrada es vacía."""
    if not plaintext:
        return None
    f = _fernet()
    if f is None:
        # Sin cifrado disponible se prefiere fallar a guardar un token en claro.
        raise RuntimeError("No se puede cifrar: falta la dependencia 'cryptography'")
    return f.encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt(token: Optional[str]) -> Optional[str]:
    """Descifra un texto. None si el token es inválido, está corrupto o cambió SECRET_KEY."""
    if not token:
        return None
    f = _fernet()
    if f is None:
        return None
    try:
        return f.decrypt(token.encode("ascii")).decode("utf-8")
    except Exception:
        # No se registra el token (es un secreto); solo el hecho.
        logger.warning("No se pudo descifrar un secreto almacenado (¿cambió SECRET_KEY?)")
        return None
