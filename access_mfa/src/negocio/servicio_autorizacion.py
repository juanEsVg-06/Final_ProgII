from __future__ import annotations
import os

from dataclasses import dataclass
from datetime import datetime

from .exceptions import AutorizacionError
from .repositorios import RepoAreas, RepoPermisos


@dataclass
class ServicioAutorizacion:
    repo_areas: RepoAreas
    repo_permisos: RepoPermisos

    def verificar_permiso_y_horario(self, *, cedula_propietario: str, id_area: str, ahora: datetime):
        area = self.repo_areas.obtener(id_area)
        if os.getenv("DEBUG", "0") == "1":
            print(f"[DEBUG] Ahora={ahora.time()} Apertura={area.hora_apertura} Cierre={area.hora_cierre}")

        if not area.es_accesible_ahora(ahora):
            raise AutorizacionError("Acceso Denegado: fuera de horario permitido.")

        permiso = self.repo_permisos.buscar_permiso(cedula=cedula_propietario, id_area=id_area, hoy=ahora.date())
        if permiso is None:
            raise AutorizacionError("Acceso Denegado: el usuario no tiene permiso vigente para esta área.")

        return permiso
