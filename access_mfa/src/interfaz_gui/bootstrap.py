# src/interfaz_gui/bootstrap.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from negocio.exceptions import IntegracionHardwareError

from negocio.repositorios import (
    RepoEstudiantes,
    RepoAreas,
    RepoPermisos,
    RepoRFID,
    RepoPins,
    RepoPatrones,
    RepoRegistros,
    RepoAccesos,
)

from negocio.servicio_autenticacion import ServicioAutenticacion
from negocio.servicio_autorizacion import ServicioAutorizacion
from negocio.servicio_auditoria import ServicioAuditoria
from negocio.caso_uso_acceso import CasoUsoAcceso

from infraestructura.arduino_adapter import ArduinoSerial, ArduinoSimulado, NullActuador
from infraestructura.sensor_gestos import SensorGestosSimulado, SensorGestosWebcamMediapipeTasks


@dataclass
class AppBoot:
    caso_uso: CasoUsoAcceso
    sensor: object
    actuador: object

    repo_estudiantes: RepoEstudiantes
    repo_areas: RepoAreas
    repo_permisos: RepoPermisos
    repo_rfid: RepoRFID
    repo_pins: RepoPins
    repo_patrones: RepoPatrones
    repo_registros: RepoRegistros
    repo_accesos: RepoAccesos

    svc_authn: ServicioAutenticacion
    svc_autz: ServicioAutorizacion
    svc_audit: ServicioAuditoria


    # --- Aliases de compatibilidad (GUI/console) ---

    @property
    def repo_est(self) -> RepoEstudiantes:
        """Alias: en la GUI se usa `repo_est` (console usa el mismo nombre)."""
        return self.repo_estudiantes

    def close(self) -> None:
        """Cierra recursos externos (puerto serial, etc.) si implementan `.close()`."""
        for obj in (self.sensor, self.actuador):
            fn = getattr(obj, "close", None)
            if callable(fn):
                try:
                    fn()
                except Exception:
                    pass

def crear_app(
    usar_camara: bool,
    camera_index: int,
    mostrar_preview: bool,
    usar_arduino: bool,
    fallback_sim_arduino: bool,
    puerto_arduino: str,
    baudrate: int,
    stable_frames: int = 10,
    debounce_s: float = 0.8,
    no_hand_frames: int = 6,
    debug: bool = False,
):
    actuador = _crear_actuador(
        usar_arduino=usar_arduino,
        fallback_sim_arduino=fallback_sim_arduino,
        puerto_arduino=puerto_arduino,
        baudrate=baudrate,
    )

    sensor = _crear_sensor(
        usar_camara=usar_camara,
        camera_index=camera_index,
        mostrar_preview=mostrar_preview,
        actuador=actuador,
        stable_frames=stable_frames,
        debounce_s=debounce_s,
        no_hand_frames=no_hand_frames,
        debug=debug,
    )

    # Repos
    repo_estudiantes = RepoEstudiantes()
    repo_areas = RepoAreas()
    repo_permisos = RepoPermisos()
    repo_rfid = RepoRFID()
    repo_pins = RepoPins()
    repo_patrones = RepoPatrones()
    repo_accesos = RepoAccesos()
    repo_registros = RepoRegistros()

    # Servicios (IMPORTANTE: ServicioAutenticacion NO recibe repo_est)
    svc_authn = ServicioAutenticacion(repo_rfid, repo_pins, repo_patrones, repo_accesos)
    svc_authz = ServicioAutorizacion(repo_areas, repo_permisos)
    svc_audit = ServicioAuditoria(repo_registros)

    caso_uso = CasoUsoAcceso(svc_authz, svc_authn, svc_audit)

    return AppBoot(
        repo_estudiantes=repo_estudiantes,
        repo_areas=repo_areas,
        repo_permisos=repo_permisos,
        repo_rfid=repo_rfid,
        repo_pins=repo_pins,
        repo_patrones=repo_patrones,
        repo_accesos=repo_accesos,
        repo_registros=repo_registros,
        svc_authn=svc_authn,
        svc_autz=svc_authz,
        svc_audit=svc_audit,
        caso_uso=caso_uso,
        sensor=sensor,
        actuador=actuador,
    )



def _crear_actuador(
    usar_arduino: bool,
    fallback_sim_arduino: bool,
    puerto_arduino: str,
    baudrate: int,
):
    if not usar_arduino:
        return ArduinoSimulado()

    try:
        return ArduinoSerial(puerto=puerto_arduino, baudrate=baudrate, timeout=1.0)
    except Exception:
        if fallback_sim_arduino:
            return ArduinoSimulado()
        raise


def _crear_sensor(
    usar_camara: bool,
    camera_index: int,
    mostrar_preview: bool,
    actuador,
    stable_frames: int = 10,
    debounce_s: float = 0.8,
    no_hand_frames: int = 6,
    debug: bool = False,
):
    if usar_camara:
        return SensorGestosWebcamMediapipeTasks(
            camera_index=camera_index,
            mostrar_preview=mostrar_preview,
            stable_frames=stable_frames,
            debounce_s=debounce_s,
            arduino=actuador,
            pin_require_no_hand=True,
            patron_require_no_hand=True,
            no_hand_frames=no_hand_frames,
            debug=debug,
        )
    else:
        secuencias = [
            [1, 3, 7, 15],
            [1, 1, 2, 3, 5, 8, 13, 21, 3, 1],
        ]
        return SensorGestosSimulado(secuencias=secuencias)