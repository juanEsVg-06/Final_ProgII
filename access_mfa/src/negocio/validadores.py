from __future__ import annotations

import re

from negocio.exceptions import ValidacionError


_RE_EMAIL = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$"
)

_RE_NOMBRE = re.compile(
    r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+(?:[ '\-][A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)*$"
)

_RE_BANNER = re.compile(
    r"^A\d{8}$"
)


def validar_correo(correo: str) -> str:
    correo = (correo or "").strip()
    if not correo:
        raise ValidacionError("Correo institucional es requerido")
    if len(correo) > 254:
        raise ValidacionError("Correo institucional demasiado largo")
    if _RE_EMAIL.fullmatch(correo) is None:
        raise ValidacionError("Correo institucional inválido (Formato usuario@dominio)")
    return correo


def validar_nombre(texto: str, *, campo: str = "nombre") -> str:
    texto = (texto or "").strip()
    if not texto:
        raise ValidacionError(f"{campo} es requerido")
    if len(texto) < 2 or len(texto) > 60:
        raise ValidacionError(f"{campo} debe tener entre 2 y 60 caracteres")
    if _RE_NOMBRE.fullmatch(texto) is None:
        raise ValidacionError(
            f"{campo} inválido: no debe contener números. Use solo letras y separadores (espacio, '-', \')"
        )
    return texto


def validar_id_banner(id_banner: str) -> str:
    id_banner = (id_banner or "").strip().upper()
    if not id_banner:
        raise ValidacionError("ID Banner es requerido")
    if _RE_BANNER.fullmatch(id_banner) is None:
        raise ValidacionError("ID Banner Inválido: Formato esperado A######## (9 caracteres)")
    return id_banner


def _cedula_checksum_ok(cedula: str) -> bool:
    coef = [2, 1, 2, 1, 2, 1, 2, 1, 2]
    s = 0
    for d, c in zip(map(int, cedula[:9]), coef):
        p = d * c
        if p >= 10:
            p -= 9
        s += p
    mod = s % 10
    verif = 0 if mod == 0 else 10 - mod
    return guarantee_int(cedula[9]) == verif


def guarantee_int(ch: str) -> int:
    return ord(ch) - ord('0')


def validar_cedula(cedula: str) -> str:
    cedula = (cedula or "").strip()

    if not cedula:
        raise ValidacionError("Cédula es requerida")

    if not cedula.isdigit():
        raise ValidacionError("Cédula inválida: use solo dígitos (sin letras ni guiones)")

    if len(cedula) != 10:
        raise ValidacionError("Cédula inválida: debe tener exactamente 10 dígitos")

    provincia = int(cedula[:2])
    if provincia < 1 or provincia > 24:
        raise ValidacionError("Cédula inválida: Código de Provincia NO válido")

    tercer = int(cedula[2])
    if tercer < 0 or tercer > 5:
        raise ValidacionError("Cédula inválida: Tercer dígito NO corresponde a Persona Natural")

    if not _cedula_checksum_ok(cedula):
        raise ValidacionError("Cédula inválida: Dígito verificador NO coincide")

    return cedula
