from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

from .exceptions import RecursoNoEncontradoError, ValidacionError
from .modelos import (
    Acceso,
    AreaAcceso,
    CredencialRFID,
    Estudiante,
    PermisoAcceso,
    PinGestual,
    PatronGestual,
    RegistroAutenticacion,
)

@dataclass
class RepoEstudiantes:
    _data: Dict[str, Estudiante] = field(default_factory=dict)

    def guardar(self, e: Estudiante) -> None:
        self._data[e.cedula_propietario] = e

    def obtener(self, cedula: str) -> Estudiante:
        try:
            return self._data[cedula]
        except KeyError as ex:
            raise RecursoNoEncontradoError(f"Estudiante no encontrado: {cedula}") from ex

    def buscar(self, cedula: str) -> Optional[Estudiante]:
        return self._data.get(cedula)

    def listar(self) -> List[Estudiante]:
        return list(self._data.values())

@dataclass
class RepoAreas:
    _data: Dict[str, AreaAcceso] = field(default_factory=dict)

    def guardar(self, a: AreaAcceso) -> None:
        self._data[a.id_area] = a

    def obtener(self, id_area: str) -> AreaAcceso:
        try:
            return self._data[id_area]
        except KeyError as ex:
            raise RecursoNoEncontradoError(f"Area no encontrada: {id_area}") from ex

    def buscar(self, id_area: str) -> Optional[AreaAcceso]:
        return self._data.get(id_area)

    def listar(self) -> List[AreaAcceso]:
        return list(self._data.values())


@dataclass
class RepoRFID:
    _data: Dict[str, CredencialRFID] = field(default_factory=dict)  # serial -> credencial
    _index_cedula: Dict[str, str] = field(default_factory=dict)     # cedula -> serial

    def guardar(self, c: CredencialRFID) -> None:
        serial = c.serial
        cedula = c.cedula_propietario

        # Un serial NO se reasigna a otra cedula
        existente_serial = self._data.get(serial)
        if existente_serial is not None and existente_serial.cedula_propietario != cedula:
            raise ValidacionError(
                f"Serial RFID '{serial}' ya está asignado a Cédula > {existente_serial.cedula_propietario}."
            )

        # Una cedula NO puede tener otro serial distinto ya asignado (por defecto)
        serial_actual = self._index_cedula.get(cedula)
        if serial_actual is not None and serial_actual != serial:
            raise ValidacionError(
                f"La Cédula > {cedula} ya tiene un RFID asignado (Serial > {serial_actual})."
            )

        self._data[serial] = c
        self._index_cedula[cedula] = serial

    def buscar_por_serial(self, serial: str) -> Optional[CredencialRFID]:
        return self._data.get(serial)

    def obtener_por_serial(self, serial: str) -> CredencialRFID:
        try:
            return self._data[serial]
        except KeyError as ex:
            raise RecursoNoEncontradoError(f"Credencial RFID no encontrada: {serial}") from ex

    def buscar_por_cedula(self, cedula: str) -> Optional[CredencialRFID]:
        serial = self._index_cedula.get(cedula)
        if serial is None:
            return None
        return self._data.get(serial)

    def listar(self) -> List[CredencialRFID]:
        return list(self._data.values())


@dataclass
class RepoPins:
    _data: Dict[tuple[str, str], PinGestual] = field(default_factory=dict)  # (cedula, id_area) -> pin
    _index_id_pin: Dict[str, tuple[str, str]] = field(default_factory=dict)  # id_pin -> (cedula, id_area)

    def guardar(self, p: PinGestual) -> None:
        key = (p.cedula_propietario, p.id_area)

        # Regla: un id_pin NO puede estar asignado a otro usuario/area
        owner = self._index_id_pin.get(p.id_pin)
        if owner is not None and owner != key:
            raise ValidacionError(
                f"ID Pin '{p.id_pin}' ya está asignado a Cédula > {owner[0]} en Área > {owner[1]}."
            )

        # Si ya existe un pin para (cedula, area), permitimos actualizacion
        existente = self._data.get(key)
        if existente is not None:
            # Si cambio el id_pin del mismo usuario/área, libera el anterior
            if existente.id_pin != p.id_pin:
                self._index_id_pin.pop(existente.id_pin, None)

        self._data[key] = p
        self._index_id_pin[p.id_pin] = key

    def obtener_por_usuario_area(self, cedula_propietario: str, id_area: str) -> PinGestual:
        key = (cedula_propietario, id_area)
        try:
            return self._data[key]
        except KeyError as ex:
            raise RecursoNoEncontradoError(
                f"PIN no encontrado para Cédula > {cedula_propietario} en Área > {id_area}"
            ) from ex

    def buscar_por_usuario_area(self, cedula_propietario: str, id_area: str) -> PinGestual | None:
        return self._data.get((cedula_propietario, id_area))

    def listar(self) -> list[PinGestual]:
        return list(self._data.values())


@dataclass
class RepoPatrones:
    _data: Dict[str, PatronGestual] = field(default_factory=dict)  # cedula -> patron
    _index_id_patron: Dict[str, str] = field(default_factory=dict)  # id_patron -> cedula

    def guardar(self, p: PatronGestual) -> None:
        cedula = p.cedula_propietario

        # Regla: un id_patron NO puede estar asignado a otra cedula
        owner = self._index_id_patron.get(p.id_patron)
        if owner is not None and owner != cedula:
            raise ValidacionError(
                f"ID Patrón '{p.id_patron}' ya está asignado a Cédula > {owner}."
            )

        existente = self._data.get(cedula)
        if existente is not None:
            # Si cambio el id_patron del mismo usuario, libera el anterior
            if existente.id_patron != p.id_patron:
                self._index_id_patron.pop(existente.id_patron, None)

        self._data[cedula] = p
        self._index_id_patron[p.id_patron] = cedula

    def obtener_por_usuario(self, cedula: str) -> PatronGestual:
        try:
            return self._data[cedula]
        except KeyError as ex:
            raise RecursoNoEncontradoError(f"Patrón no encontrado para Usuario > {cedula}") from ex

    def buscar_por_usuario(self, cedula: str) -> PatronGestual | None:
        return self._data.get(cedula)

    def listar(self) -> list[PatronGestual]:
        return list(self._data.values())


@dataclass
class RepoPermisos:
    _data: Dict[str, PermisoAcceso] = field(default_factory=dict)  # id_permiso -> permiso

    def guardar(self, p: PermisoAcceso) -> None:
        self._data[p.id_permiso] = p

    def buscar_permiso(self, cedula: str, id_area: str, hoy: date) -> Optional[PermisoAcceso]:
        for p in self._data.values():
            if p.cedula_propietario == cedula and p.id_area == id_area and p.es_vigente(hoy):
                return p
        return None

    def listar(self) -> List[PermisoAcceso]:
        return list(self._data.values())

@dataclass
class RepoRegistros:
    _data: List[RegistroAutenticacion] = field(default_factory=list)

    def agregar(self, r: RegistroAutenticacion) -> None:
        self._data.append(r)

    def listar(self) -> List[RegistroAutenticacion]:
        return list(self._data)

    def listar_por_usuario(self, cedula: str) -> List[RegistroAutenticacion]:
        return [r for r in self._data if r.cedula_propietario == cedula]

    def listar_por_area(self, id_area: str) -> List[RegistroAutenticacion]:
        return [r for r in self._data if r.id_area == id_area]


@dataclass
class RepoAccesos:
    _data: List[Acceso] = field(default_factory=list)

    def agregar(self, a: Acceso) -> None:
        self._data.append(a)

    def listar(self) -> List[Acceso]:
        return list(self._data)
