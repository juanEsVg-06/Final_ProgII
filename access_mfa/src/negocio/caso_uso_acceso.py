from __future__ import annotations
import os


from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from infraestructura.arduino_adapter import IActuadorAcceso
from infraestructura.sensor_gestos import ISensorGestos

from .servicio_auditoria import ServicioAuditoria
from .enums import MetodoIngreso, ResultadoAutenticacion
from .exceptions import AutenticacionError, AutorizacionError, IntegracionHardwareError
from .servicio_autenticacion import ServicioAutenticacion
from .servicio_autorizacion import ServicioAutorizacion


@dataclass
class CasoUsoAcceso:
    servicio_autorizacion: ServicioAutorizacion
    servicio_autenticacion: ServicioAutenticacion
    servicio_auditoria: ServicioAuditoria

    def solicitar_acceso(
            self,
            *,
            cedula_propietario: str,
            id_area: str,
            serial_rfid: str,
            sensor: ISensorGestos,
            actuador: IActuadorAcceso,
            gesto_cierre: int | None = None,
            ahora: datetime | None = None,
    ):
        factores_ok: list[MetodoIngreso] = []
        permiso = None

        if ahora is None:
            ahora = datetime.now()

        # Desactivación de 'gesto_cierre' por defecto (evita cortes accidentales al retirar la mano).
        # Activación explícita con AUTH_GESTO_CIERRE=1
        gesto_cierre_auth: int | None = None
        if os.getenv("AUTH_GESTO_CIERRE", "0") == "1":
            gesto_cierre_auth = gesto_cierre

        pin_timeout_s = float(os.getenv("AUTH_PIN_TIMEOUT_S", "60"))
        patron_timeout_s = float(os.getenv("AUTH_PATRON_TIMEOUT_S", "150"))
        patron_len = int(os.getenv("AUTH_PATRON_LEN", "6"))


        try:
            # 1) Autorización
            permiso = self.servicio_autorizacion.verificar_permiso_y_horario(
                cedula_propietario=cedula_propietario, id_area=id_area, ahora=ahora
            )

            # 2) RFID
            self.servicio_autenticacion.validar_rfid(
                serial=serial_rfid, cedula_propietario=cedula_propietario, ahora=ahora
            )
            factores_ok.append(MetodoIngreso.RFID)

            # 3) PIN (4)
            sec_pin, _ = sensor.capturar_secuencia(4, gesto_cierre=gesto_cierre_auth, timeout_s=pin_timeout_s)
            if len(sec_pin) != 4:
                raise AutenticacionError(f"PIN gestual incompleto: {len(sec_pin)}/4 (cancelado o timeout).")
            self.servicio_autenticacion.validar_pin(cedula_propietario=cedula_propietario, id_area=id_area, secuencia_capturada=sec_pin)
            factores_ok.append(MetodoIngreso.PIN_GESTUAL)

            # 4) Patrón (len configurable, por defecto 6)
            sec_pat, tiempos = sensor.capturar_secuencia(patron_len, gesto_cierre=gesto_cierre_auth, timeout_s=patron_timeout_s)
            if len(sec_pat) != patron_len:
                raise AutenticacionError(f"Patrón Incompleto: {len(sec_pat)}/{patron_len} (cancelado o timeout).")
            self.servicio_autenticacion.validar_patron(
                cedula_propietario=cedula_propietario, secuencia_capturada=sec_pat, tiempos=tiempos
            )
            factores_ok.append(MetodoIngreso.PATRON_GESTUAL)

            # 5) Exito: actuador + auditoría + acceso
            actuador.indicar_exito()
            actuador.abrir_puerta()

            registro = self.servicio_auditoria.registrar(
                cedula_propietario=cedula_propietario,
                id_area=id_area,
                metodo=MetodoIngreso.RFID,
                factores=factores_ok,
                resultado=ResultadoAutenticacion.EXITO,
                motivo="",
                id_permiso=permiso.id_permiso,
                timestamp=ahora,
            )

            from .modelos import Acceso

            acceso = Acceso(
                id_acceso=str(uuid4()),
                cedula_propietario=cedula_propietario,
                id_area=id_area,
                fecha_entrada=ahora,
                registro_exitoso_id=registro.id_registro,
            )
            self.servicio_autenticacion.repo_accesos.agregar(acceso)

            return acceso, registro

        except (AutenticacionError, AutorizacionError) as ex:
            try:
                actuador.indicar_fallo()
            except Exception:
                pass
            self.servicio_auditoria.registrar(
                cedula_propietario=cedula_propietario,
                id_area=id_area,
                metodo=MetodoIngreso.RFID,
                factores=factores_ok,
                resultado=ResultadoAutenticacion.FALLO,
                motivo=str(ex),
                id_permiso=permiso.id_permiso if permiso else None,
                timestamp=ahora,
            )

            raise
        except IntegracionHardwareError as ex:
            # hardware/cámara/modelo: auditado
            try:
                actuador.indicar_fallo()
            except Exception:
                pass

            self.servicio_auditoria.registrar(
                cedula_propietario=cedula_propietario,
                id_area=id_area,
                metodo=MetodoIngreso.RFID,
                factores=factores_ok,
                resultado=ResultadoAutenticacion.FALLO,
                motivo=f"Fallo hardware: {ex}",
                id_permiso=permiso.id_permiso if permiso else None,
            )
            raise

