from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .enums import EstadoCredencial, EstadoPin, MetodoIngreso, ResultadoAutenticacion
from .exceptions import AutenticacionError, ValidacionError, RecursoNoEncontradoError
from .repositorios import RepoAccesos, RepoPatrones, RepoPins, RepoRFID

@dataclass
class ServicioAutenticacion:
    repo_rfid: RepoRFID
    repo_pins: RepoPins
    repo_patrones: RepoPatrones
    repo_accesos: RepoAccesos

    max_intentos_rfid: int = 3
    max_intentos_pin: int = 3
    umbral_similitud_patron: float = 0.9

    def validar_rfid(self, *, serial: str, cedula_esperada: str, ahora: datetime) -> None:
        try:
            cred = self.repo_rfid.obtener_por_serial(serial)
        except RecursoNoEncontradoError:
            raise AutenticacionError("RFID no registrada en el sistema.")

        # Estado de la credencial (salida temprana)

        if cred.estado == EstadoCredencial.BLOQUEADA:
            raise AutenticacionError("RFID bloqueada.")
        if cred.estado == EstadoCredencial.PERDIDA:
            raise AutenticacionError("RFID marcada como perdida.")
        if cred.estado == EstadoCredencial.EXPIRADA:
            raise AutenticacionError("RFID expirada.")

        if cred.cedula_propietario != cedula_esperada:
            cred.intentos_fallidos += 1
            if cred.intentos_fallidos >= self.max_intentos_rfid:
                cred.estado = EstadoCredencial.BLOQUEADA
                raise AutenticacionError("RFID bloqueada por demasiados intentos fallidos.")
            raise AutenticacionError("RFID no corresponde al usuario.")

        if not cred.esta_vigente(ahora.date()):
            cred.intentos_fallidos += 1
            if ahora.date() > cred.fecha_expiracion:
                cred.estado = EstadoCredencial.EXPIRADA
            if cred.intentos_fallidos >= self.max_intentos_rfid:
                cred.estado = EstadoCredencial.BLOQUEADA
                raise AutenticacionError("RFID bloqueada por demasiados intentos fallidos.")
            raise AutenticacionError("RFID inválida/expirada/bloqueada.")


        # Reset de fallos y éxito
        cred.intentos_exitosos += 1
        cred.intentos_fallidos = 0
        cred.ultimo_acceso = ahora

    def validar_pin(self, *, id_area: str, secuencia_capturada: list[int]) -> None:
        try:
            pin = self.repo_pins.obtener_por_area(id_area)
        except RecursoNoEncontradoError:
            raise AutenticacionError("No hay PIN gestual configurado para esta área.")

        if pin.estado == EstadoPin.BLOQUEADO:
            raise AutenticacionError("PIN gestual bloqueado para esta área.")

        if secuencia_capturada != pin.secuencia_gestos:
            pin.intentos_fallidos += 1
            if pin.intentos_fallidos >= self.max_intentos_pin:
                pin.estado = EstadoPin.BLOQUEADO
            raise AutenticacionError("PIN gestual incorrecto.")

        # exito
        pin.intentos_fallidos = 0

    def validar_patron(self, *, cedula: str, secuencia_capturada: list[int], tiempos: list[float] | None) -> None:
        try:
            patron = self.repo_patrones.obtener_por_usuario(cedula)
        except RecursoNoEncontradoError:
            raise AutenticacionError("No hay patrón gestual enrolado para este usuario.")

        if len(secuencia_capturada) == 0:
            raise ValidacionError("La secuencia capturada del patrón está vacía.")

        # Similitud discreta. Si longitudes difieren, se penaliza.
        n = max(len(patron.secuencia_gestos), len(secuencia_capturada))
        matches = 0
        for i in range(min(len(patron.secuencia_gestos), len(secuencia_capturada))):
            if patron.secuencia_gestos[i] == secuencia_capturada[i]:
                matches += 1
        similitud = matches / n

        if similitud < self.umbral_similitud_patron:
            raise AutenticacionError(
                f"Patrón gestual no coincide (similitud={similitud:.2f}, umbral={self.umbral_similitud_patron:.2f})."
            )

        # Opcional: validación ligera de timing (si ambos existen)
        if patron.tiempos_entre_gestos is not None and tiempos is not None:
            if len(patron.tiempos_entre_gestos) == len(tiempos):
                # tolerancia simple: cada delta dentro de ±40%
                for ref, got in zip(patron.tiempos_entre_gestos, tiempos):
                    if ref == 0:
                        continue
                    if not (0.6 * ref <= got <= 1.4 * ref):
                        raise AutenticacionError("Patrón gestual: timings fuera de tolerancia.")
