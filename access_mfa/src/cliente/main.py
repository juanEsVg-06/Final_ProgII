from __future__ import annotations

import os
from typing import Callable, Optional
from dataclasses import dataclass
from datetime import date, datetime, time

from infraestructura.arduino_adapter import (
    ArduinoSerial,
    ArduinoSimulado,
    IActuadorAcceso,
    NullActuador,
)
from infraestructura.sensor_gestos import (
    ISensorGestos,
    SensorGestosWebcamMediapipeTasks,
)

from negocio.servicio_auditoria import ServicioAuditoria
from negocio.caso_uso_acceso import CasoUsoAcceso
from negocio.enums import EstadoCredencial, EstadoPermiso, TipoArea
from negocio.exceptions import (
    AutenticacionError,
    AutorizacionError,
    DominioError,
    IntegracionHardwareError,
)
from negocio.validadores import validar_cedula, validar_correo, validar_id_banner, validar_nombre
from negocio.modelos import (
    AreaAcceso,
    CredencialRFID,
    Estudiante,
    PatronGestual,
    PermisoAcceso,
    PinGestual,
)
from negocio.repositorios import (
    RepoAccesos,
    RepoAreas,
    RepoEstudiantes,
    RepoPatrones,
    RepoPermisos,
    RepoPins,
    RepoRFID,
    RepoRegistros,
)
from negocio.servicio_autenticacion import ServicioAutenticacion
from negocio.servicio_autorizacion import ServicioAutorizacion

@dataclass
class AppContext:
    repo_est: RepoEstudiantes
    repo_areas: RepoAreas
    repo_permisos: RepoPermisos
    repo_rfid: RepoRFID
    repo_pins: RepoPins
    repo_patrones: RepoPatrones
    repo_registros: RepoRegistros
    repo_accesos: RepoAccesos
    caso_uso: CasoUsoAcceso
    sensor: ISensorGestos
    actuador: IActuadorAcceso


# ------------------ Seed demo (opcional) ------------------

def _seed(repo_est, repo_areas, repo_permisos, repo_rfid, repo_pins, repo_pat) -> None:
    e = Estudiante(
        cedula_propietario="1710034065",
        nombres="Juan Esteban",
        apellidos="Velastegui Gordillo",
        correo_institucional="juanes@udla.edu.ec",
        id_banner="A00126187",
        carrera="Ciberseguridad",
    )
    repo_est.guardar(e)

    a = AreaAcceso(
        id_area="LAB-101",
        nombre="Laboratorio Redes",
        tipo=TipoArea.LABORATORIO,
        ubicacion="Bloque A",
        hora_apertura=time(7, 0),
        hora_cierre=time(23, 59),
    )
    repo_areas.guardar(a)

    p = PermisoAcceso(
        id_permiso="PERM-001",
        cedula_propietario=e.cedula_propietario,
        id_area=a.id_area,
        estado=EstadoPermiso.ACTIVO,
        vigente_desde=date.today(),
        vigente_hasta=date.today().replace(year=date.today().year + 1),
    )
    repo_permisos.guardar(p)

    r = CredencialRFID(
        serial="RFID-12345",
        cedula_propietario=e.cedula_propietario,
        fecha_emision=date.today().replace(year=date.today().year - 1),
        fecha_expiracion=date.today().replace(year=date.today().year + 1),
        estado=EstadoCredencial.ACTIVA,
    )
    repo_rfid.guardar(r)

    pin = PinGestual(id_pin="PIN-001", cedula_propietario=e.cedula_propietario, id_area=a.id_area, id_banner=e.id_banner, secuencia_gestos=[3, 7, 6, 2])
    repo_pins.guardar(pin)

    patron = PatronGestual(
        id_patron="PAT-001",
        cedula_propietario=e.cedula_propietario,
        secuencia_gestos=[17, 25, 25, 17, 6, 7, 7, 2, 30, 31],
        fecha_captura=datetime.now(),
        tiempos_entre_gestos=None,
    )
    repo_pat.guardar(patron)


# Pre-validaciones input

def _prompt(etiqueta: str) -> str:
    lab = (etiqueta or "").strip()
    if not lab:
        lab = "Valor"
    # Evita el "doble :" si ya viene incluido en la etiqueta
    return f"{lab} " if lab.endswith(":") else f"{lab}: "


def pedir_no_vacio(etiqueta: str) -> str:
    while True:
        v = input(_prompt(etiqueta)).strip()
        if v:
            return v
        print("No puede estar vacío.")


def pedir_validado(etiqueta: str, validador) -> str:
    while True:
        v = input(_prompt(etiqueta)).strip()
        try:
            validador(v)
            return v
        except DominioError as ex:
            print(str(ex))

def pedir_int_rango(etiqueta: str, minimo: int, maximo: int) -> int:
    while True:
        s = input(f"{etiqueta} ({minimo}-{maximo}): ").strip()
        try:
            n = int(s)
            if minimo <= n <= maximo:
                return n
            print("Fuera de Rango!")
        except ValueError:
            print("Debe ser un número entero.")

def pedir_fecha(etiqueta: str) -> date:
    while True:
        s = input(f"{etiqueta} (YYYY-MM-DD): ").strip()
        try:
            return date.fromisoformat(s)
        except ValueError:
            print("Formato inválido. Ejemplo: 2026-01-10")

def obtener_ahora() -> datetime:
    """
    Permite forzar la hora/fecha en pruebas para no depender del reloj del PC.
    Formatos:
        - FORZAR_HORA = "HH:MM" (usa fecha actual)
        - FORZAR_FECHA_HORA = "YYYY-MM-DD HH:MM"
    """
    override_hora = os.getenv("FORZAR_HORA", "").strip()
    override_dt = os.getenv("FORZAR_FECHA_HORA", "").strip()

    if override_dt:
        try:
            return datetime.fromisoformat(override_dt)
        except ValueError:
            raise DominioError(
                "FORZAR_FECHA_HORA inválido. Usa 'YYYY-MM-DD HH:MM' o 'YYYY-MM-DD HH:MM:SS'."
            )
    if override_hora:
        try:
            hh, mm = override_hora.split(":")
            hh_i, mm_i = int(hh), int(mm)
            now = datetime.now()
            return now.replace(hour=hh_i, minute=mm_i, second=0, microsecond=0)
        except Exception:
            raise DominioError("FORZAR_HORA inválido. Usa 'HH:MM' (ej: 12:00).")

    return datetime.now()


def construir_actuador() -> IActuadorAcceso:
    puerto = os.getenv("ARDUINO_PORT")
    baud = int(os.getenv("ARDUINO_BAUD", "9600"))

    if not puerto:
        print("[INFO] ARDUINO_PORT no configurado -> usando NullActuador (sin hardware).")
        print("       Ejemplo PowerShell: $env:ARDUINO_PORT='COM5'")
        return NullActuador()

    try:
        act = ArduinoSerial(puerto=puerto, baudrate=baud, timeout=1.0)
        print(f"[INFO] ArduinoSerial activo en {puerto} (baud={baud}).")
        return act
    except IntegracionHardwareError as ex:
        print(f"[AVISO] No se pudo abrir Arduino en {puerto}: {ex}")
        print("[AVISO] Usando ArduinoSimulado (sin LEDs reales).")
        return ArduinoSimulado()


def construir_sensor(actuador: Optional[IActuadorAcceso]) -> ISensorGestos:
    """
    Construye el sensor REAL (webcam) con parámetros controlables por variables de entorno.

    Objetivo:
    - No simular: usar webcam + MediaPipe/Tasks.
    - Hacer PIN (4) más repetible: opción de exigir 'sin mano' entre dígitos.
    """

    # Parámetros Base
    camera_index = int(os.getenv("CAMERA_INDEX", "0"))
    mostrar_preview = os.getenv("GESTOS_PREVIEW", "1") == "1"

    stable_frames = int(os.getenv("GESTOS_STABLE_FRAMES", "10"))
    debounce_s = float(os.getenv("GESTOS_DEBOUNCE_S", "0.9"))

    # --- Regla “sin mano" ---
    # 1 = habilitado, 0 = deshabilitado
    pin_require_no_hand = os.getenv("PIN_REQUIRE_NO_HAND", "1") == "1"
    patron_require_no_hand = os.getenv("PATRON_REQUIRE_NO_HAND", "1") == "1"

    no_hand_frames = int(os.getenv("NO_HAND_FRAMES", "4"))

    debug = os.getenv("DEBUG", "0") == "1"

    # Validaciones mínimas
    if camera_index < 0:
        raise IntegracionHardwareError("CAMERA_INDEX inválido (debe ser >= 0).")

    if stable_frames < 1:
        raise IntegracionHardwareError("GESTOS_STABLE_FRAMES inválido (mínimo 1).")

    if debounce_s < 0:
        raise IntegracionHardwareError("GESTOS_DEBOUNCE_S inválido (debe ser >= 0).")

    if no_hand_frames < 1:
        raise IntegracionHardwareError("NO_HAND_FRAMES inválido (mínimo 1).")

    # Construcción del sensor webcam
    try:
        sensor = SensorGestosWebcamMediapipeTasks(
            camera_index=camera_index,
            mostrar_preview=mostrar_preview,
            stable_frames=stable_frames,
            debounce_s=debounce_s,
            arduino=actuador,
            pin_require_no_hand=pin_require_no_hand,
            patron_require_no_hand=True,
            no_hand_frames=no_hand_frames,
            debug=debug,
        )
    except TypeError:
        sensor = SensorGestosWebcamMediapipeTasks(
            camera_index=camera_index,
            mostrar_preview=mostrar_preview,
            stable_frames=stable_frames,
            debounce_s=debounce_s,
            arduino=actuador,
        )
        for k, v in {
            "pin_require_no_hand": pin_require_no_hand,
            "patron_require_no_hand": patron_require_no_hand,
            "no_hand_frames": no_hand_frames,
            "debug": debug,
        }.items():
            if hasattr(sensor, k):
                setattr(sensor, k, v)

    if debug:
        print(
            "[CFG] SensorGestosWebcam configurado -> "
            f"camera_index={camera_index}, preview={mostrar_preview}, "
            f"stable_frames={stable_frames}, debounce_s={debounce_s}, "
            f"pin_require_no_hand={pin_require_no_hand}, "
            f"patron_require_no_hand={patron_require_no_hand}, "
            f"no_hand_frames={no_hand_frames}"
        )

    return sensor


# Acciones menu

# Estudiantes

def accion_crear_estudiante(ctx: AppContext) -> None:
    cedula = pedir_validado("Cédula", validar_cedula)
    nombres = pedir_validado("Nombres", validar_nombre)
    apellidos = pedir_validado("Apellidos", validar_nombre)
    correo = pedir_validado("Correo institucional", validar_correo)
    banner = pedir_validado("ID Banner", validar_id_banner)
    carrera = pedir_no_vacio("Carrera")

    ctx.repo_est.guardar(
        Estudiante(
            cedula_propietario=cedula,
            nombres=nombres,
            apellidos=apellidos,
            correo_institucional=correo,
            id_banner=banner,
            carrera=carrera,
        )
    )
    print("Estudiante Creado/Actualizado.")

def accion_listar_estudiantes(ctx: AppContext) -> None:
    ests = ctx.repo_est.listar()
    if not ests:
        print("NO hay Estudiantes registrados.")
        return
    for e in ests:
        print(f"- {e.cedula_propietario} | {e.nombres} {e.apellidos} | {e.carrera}")

# Areas

def accion_crear_area(ctx: AppContext) -> None:
    id_area = pedir_no_vacio("ID área (ej: LAB-101)")
    nombre = pedir_no_vacio("Nombre")
    ubicacion = pedir_no_vacio("Ubicación")

    tipo = TipoArea.LABORATORIO

    hora_apertura = time(pedir_int_rango("Hora Apertura", 0, 23), pedir_int_rango("Minuto Apertura", 0, 59))
    hora_cierre = time(pedir_int_rango("Hora Cierre", 0, 23), pedir_int_rango("Minuto Cierre", 0, 59))

    ctx.repo_areas.guardar(
        AreaAcceso(
            id_area=id_area,
            nombre=nombre,
            tipo=tipo,
            ubicacion=ubicacion,
            hora_apertura=hora_apertura,
            hora_cierre=hora_cierre,
        )
    )
    print("Área Creada/Actualizada.")

def accion_listar_areas(ctx: AppContext) -> None:
    areas = ctx.repo_areas.listar()
    if not areas:
        print("NO hay Áreas registradas.")
        return
    for a in areas:
        print(f"- {a.id_area} | {a.nombre} | {a.tipo.value} | {a.ubicacion} | {a.hora_apertura}-{a.hora_cierre}")

# Permisos

def accion_listar_permisos(ctx: AppContext) -> None:
    perms = ctx.repo_permisos.listar()
    if not perms:
        print("NO hay Permisos.")
        return
    for p in perms:
        print(f"- {p.id_permiso} | Cédula > {p.cedula_propietario} | Área > {p.id_area} | Estado > {p.estado.value} "
              f"| {p.vigente_desde} -> {p.vigente_hasta}")

def accion_asignar_permiso(ctx: AppContext) -> None:
    cedula = pedir_validado("Cédula", validar_cedula)
    id_area = pedir_no_vacio("ID Área (ej: LAB-101)")
    id_permiso = pedir_no_vacio("ID Permiso")

    est = ctx.repo_est.buscar(cedula)
    if not est:
        print("NO existe ese Estudiante. Cree el Estudiante primero.")
        return

    area = ctx.repo_areas.buscar(id_area)
    if not area:
        print("NO existe el Área. Cree el Área primero.")
        return

    vigente_desde = pedir_fecha("Vigente Desde")
    vigente_hasta = pedir_fecha("Vigente Hasta")
    if vigente_hasta < vigente_desde:
        print("Error: El valor de la Vigencia Hasta no puede ser menor que la Vigencia Desde.")
        return

    print("Estado Permiso: 1) ACTIVO  2) SUSPENDIDO")
    op = input("Opción: ").strip()
    estado = EstadoPermiso.ACTIVO if op != "2" else EstadoPermiso.SUSPENDIDO

    ctx.repo_permisos.guardar(
        PermisoAcceso(
            id_permiso=id_permiso,
            cedula_propietario=cedula,
            id_area=id_area,
            estado=estado,
            vigente_desde=vigente_desde,
            vigente_hasta=vigente_hasta,
        )
    )
    print("Permiso Creado/Actualizado.")

# RFIDs

def accion_listar_rfid(ctx: AppContext) -> None:
    rfids = ctx.repo_rfid.listar()
    if not rfids:
        print("NO hay credenciales RFID.")
        return
    for r in rfids:
        print(f"- Serial > {r.serial} | Cédula > {r.cedula_propietario} | {r.fecha_emision} -> {r.fecha_expiracion} | Estado > {r.estado.value}")

def accion_asignar_rfid(ctx: AppContext) -> None:
    serial = pedir_no_vacio("Serial RFID")
    cedula = pedir_validado("Cédula de Propietario", validar_cedula)
    emision = pedir_fecha("Fecha de Emisión")
    expiracion = pedir_fecha("Fecha de Expiración")
    if expiracion < emision:
        print("Error: La fecha de expiración no puede ser menor que la fecha de emisión.")
        return

    # Validacion - estudiante existe
    if not ctx.repo_est.buscar(cedula):
        print("NO existe ese Estudiante. Cree el Estudiante primero.")
        return

    if ctx.repo_rfid.buscar_por_serial(serial):
        print("Error: YA existe una credencial con ese serial.")
        return

    ctx.repo_rfid.guardar(
        CredencialRFID(
            serial=serial,
            cedula_propietario=cedula,
            fecha_emision=emision,
            fecha_expiracion=expiracion,
            estado=EstadoCredencial.ACTIVA,
        )
    )
    print("RFID Asignada.")

# PINs

def accion_listar_pins(ctx: AppContext) -> None:
    pins = ctx.repo_pins.listar()
    if not pins:
        print("NO hay PINs.")
        return
    for p in pins:
        print(f"- Área > {p.id_area} | ID Pin > {p.id_pin}")


def accion_configurar_pin(ctx: AppContext) -> None:
    cedula = pedir_validado("Cédula", validar_cedula)
    id_banner = pedir_validado("ID Banner", validar_id_banner)
    id_pin = pedir_no_vacio("ID PIN (ej: PIN-001)")
    id_area = pedir_no_vacio("ID Área")

    # Garantía: 1 PIN por (cedula, area)
    existente = None
    for pin in ctx.repo_pins.listar():
        if pin.cedula_propietario == cedula and pin.id_area == id_area:
            existente = pin
            break

    if existente:
        print(f"[AVISO] Ya existe un PIN para este estudiante en esta área (ID = {existente.id_pin}).")
        op = input("¿Desea sobrescribirlo? (S/N): ").strip().upper()
        if op != "S":
            print("Operación cancelada.")
            return

    est = ctx.repo_est.buscar(cedula)
    if not est:
        print("No existe un estudiante con esa cédula. Cree el estudiante primero.")
        return
    if est.id_banner != id_banner:
        print("Identidad no verificada: el ID Banner no corresponde a la cédula ingresada.")
        return

    if not ctx.repo_areas.buscar(id_area):
        print("NO existe esa Área. Cree el Área primero.")
        return

    # Aviso (no bloqueante): si no hay permiso ACTIVO vigente, el acceso igual será denegado por autorización.
    hoy = date.today()
    permiso_ok = any(
        (perm.cedula_propietario == cedula and perm.id_area == id_area and perm.estado.name == "ACTIVO" and perm.es_vigente(hoy))
        for perm in ctx.repo_permisos.listar()
    )
    if not permiso_ok:
        print("[AVISO] No se encontró un permiso ACTIVO y vigente para este estudiante en el área.\n")

    print("Ponga la mano frente a la Cámara. Registre 4 gestos.")
    sec, _ = ctx.sensor.capturar_secuencia(4, gesto_cierre=19, timeout_s=60)
    if len(sec) != 4:
        print("PIN Incompleto/Cancelado.")
        return

    ctx.repo_pins.guardar(
        PinGestual(
            id_pin=id_pin,
            cedula_propietario=cedula,
            id_banner=id_banner,
            id_area=id_area,
            secuencia_gestos=sec,
        )
    )
    print(f"PIN configurado con Éxito")

# Patrones

def accion_listar_patrones(ctx: AppContext) -> None:
    pats = ctx.repo_patrones.listar()
    if not pats:
        print("NO hay Patrones.")
        return
    for p in pats:
        print(f"- Cédula > {p.cedula_propietario} | ID Patron > {p.id_patron} | Fecha de Captura > {p.fecha_captura:%Y-%m-%d %H:%M:%S}")

def accion_enrolar_patron(ctx: AppContext) -> None:
    id_pat = pedir_no_vacio("ID Patrón (ej: PAT-001)")
    cedula = pedir_validado("Cédula", validar_cedula)
    id_banner = pedir_validado("ID Banner", validar_id_banner)

    # Garantía: 1 patrón por estudiante
    existente = None
    for pat in ctx.repo_patrones.listar():
        if pat.cedula_propietario == cedula:
            existente = pat
            break

    if existente:
        print(f"[AVISO] Ya existe un patrón para esta cédula (ID={existente.id_patron}).")
        op = input("¿Desea sobrescribirlo? (S/N): ").strip().upper()
        if op != "S":
            print("Operación cancelada.")
            return

    est = ctx.repo_est.buscar(cedula)
    if not est:
        print("No existe un estudiante con esa cédula. Cree el estudiante primero.")
        return
    if est.id_banner != id_banner:
        print("Identidad no verificada: el ID Banner no corresponde a la cédula ingresada.")
        return

    print("Ponga la mano frente a la Cámara. Registre 10 gestos.")
    sec, tiempos = ctx.sensor.capturar_secuencia(10, gesto_cierre=19, timeout_s=180)
    if len(sec) != 10:
        print("Patrón Incompleto/Cancelado.")
        return

    ctx.repo_patrones.guardar(
        PatronGestual(
            id_patron=id_pat,
            cedula_propietario=cedula,
            secuencia_gestos=sec,
            fecha_captura=datetime.now(),
            tiempos_entre_gestos=tiempos,
        )
    )
    print(f"Patron enrolado con Éxito")

# Accesos

def accion_listar_accesos(ctx: AppContext) -> None:
    accs = ctx.repo_accesos.listar()
    if not accs:
        print("NO hay Accesos concedidos.")
        return
    for a in accs:
        print(
            f"- ID Acceso > {a.id_acceso} | Cédula > {a.cedula_propietario} | Área > {a.id_area} | "
            f" Fecha de Acceso > {a.fecha_entrada:%Y-%m-%d %H:%M:%S} | Registro > {a.registro_exitoso_id}"
        )


def accion_intentar_acceso(ctx: AppContext) -> None:
    cedula = pedir_validado("Cédula", validar_cedula)
    id_area = pedir_no_vacio("ID Área (ej: LAB-101)")
    serial = pedir_no_vacio("Serial RFID (ej: RFID-12345)")

    try:
        ahora = obtener_ahora()
        acceso, registro = ctx.caso_uso.solicitar_acceso(
            cedula_propietario=cedula,
            id_area=id_area,
            serial_rfid=serial,
            sensor=ctx.sensor,
            actuador=ctx.actuador,
            gesto_cierre=19,
            ahora=ahora,
        )
        print(f"Acceso Concedido! ID Acceso > {acceso.id_acceso}, Registro > {registro.id_registro}")
    except (AutorizacionError, AutenticacionError) as ex:
        print(f"|ALERTA| - Acceso Denegado! | {ex}")
    except DominioError as ex:
        print(f"Error de Dominio: {ex}")

# Registros

def accion_ver_registros(ctx: AppContext) -> None:
    regs = ctx.repo_registros.listar()
    if not regs:
        print("NO hay Registros.")
        return
    for r in regs:
        print(
            f"[{r.timestamp:%Y-%m-%d %H:%M:%S}] Usuario > {r.cedula_propietario} Área > {r.id_area} "
            f"Resultado > {r.resultado} Factores > {','.join([f.value for f in r.factores])} Motivo > {r.motivo}"
        )

# Datos Demo

def accion_cargar_seed_y_mostrar(ctx: AppContext) -> None:
    try:
        _seed(ctx.repo_est, ctx.repo_areas, ctx.repo_permisos, ctx.repo_rfid, ctx.repo_pins, ctx.repo_patrones)
    except DominioError as ex:
        print(f"|ALERTA| - Seed falló por validación: {ex}")
        return

    print("Seed cargada.")
    print("\n[Seed] Estudiantes:")
    accion_listar_estudiantes(ctx)
    print("\n[Seed] Áreas:")
    accion_listar_areas(ctx)
    print("\n[Seed] Permisos:")
    accion_listar_permisos(ctx)
    print("\n[Seed] RFID:")
    accion_listar_rfid(ctx)
    print("\n[Seed] PINs:")
    accion_listar_pins(ctx)
    print("\n[Seed] Patrones:")
    accion_listar_patrones(ctx)


# ------------------ Menu ------------------

def imprimir_menu() -> None:
    print("\n--- Sistema de Control de Acceso MFA ---")
    print("1) Crear Estudiante")
    print("2) Listar Estudiantes")
    print("3) Crear Área")
    print("4) Listar Areas")
    print("5) Asignar Permiso")
    print("6) Asignar RFID")
    print("7) Configurar PIN (por Área)")
    print("8) Enrolar Patrón (por Estudiante)")
    print("9) Solicitar Acceso (MFA)")
    print("10) Ver Registros de Autenticación")
    print("11) Listar Permisos")
    print("12) Listar RFIDs")
    print("13) Listar PINs")
    print("14) Listar Patrones")
    print("15) Listar Accesos Concedidos")
    print("D) Cargar datos demo (seed) [opcional]")
    print("0) Salir")

def main_loop(ctx: AppContext) -> None:
    acciones: dict[str, Callable[[AppContext], None]] = {
        "1": accion_crear_estudiante,
        "2": accion_listar_estudiantes,
        "3": accion_crear_area,
        "4": accion_listar_areas,
        "5": accion_asignar_permiso,
        "6": accion_asignar_rfid,
        "7": accion_configurar_pin,
        "8": accion_enrolar_patron,
        "9": accion_intentar_acceso,
        "10": accion_ver_registros,
        "11": accion_listar_permisos,
        "12": accion_listar_rfid,
        "13": accion_listar_pins,
        "14": accion_listar_patrones,
        "15": accion_listar_accesos,
        "D": accion_cargar_seed_y_mostrar,
    }

    while True:
        imprimir_menu()
        op = input("Opción: ").strip().upper()
        if op == "0":
            print("Saliendo del programa...")
            # Cierre del serial si aplica
            if hasattr(ctx.actuador, "close"):
                try:
                    ctx.actuador.close()
                except Exception:
                    pass
            break

        accion = acciones.get(op)
        if not accion:
            print("|ALERTA| - Opción Inválida!")
            continue

        try:
            accion(ctx)
        except DominioError as ex:
            print(f"Error de dominio: {ex}")
        except Exception as ex:
            if os.getenv("DEBUG", "0") == "1":
                print(f"[ERROR] {type(ex).__name__}: {ex}")
            else:
                print("Ocurrió un error inesperado. Verifique su configuración e intente nuevamente.")

def main() -> None:
    repo_est = RepoEstudiantes()
    repo_areas = RepoAreas()
    repo_permisos = RepoPermisos()
    repo_rfid = RepoRFID()
    repo_pins = RepoPins()
    repo_patrones = RepoPatrones()
    repo_registros = RepoRegistros()
    repo_accesos = RepoAccesos()

    svc_autorizacion = ServicioAutorizacion(repo_areas=repo_areas, repo_permisos=repo_permisos)
    svc_autenticacion = ServicioAutenticacion(
        repo_rfid=repo_rfid,
        repo_pins=repo_pins,
        repo_patrones=repo_patrones,
        repo_accesos=repo_accesos,
    )
    svc_auditoria = ServicioAuditoria(repo_registros=repo_registros)

    caso_uso = CasoUsoAcceso(
        servicio_autorizacion=svc_autorizacion,
        servicio_autenticacion=svc_autenticacion,
        servicio_auditoria=svc_auditoria,
    )

    actuador = construir_actuador()
    sensor = construir_sensor(actuador)

    ctx = AppContext(
        repo_est=repo_est,
        repo_areas=repo_areas,
        repo_permisos=repo_permisos,
        repo_rfid=repo_rfid,
        repo_pins=repo_pins,
        repo_patrones=repo_patrones,
        repo_registros=repo_registros,
        repo_accesos=repo_accesos,
        caso_uso=caso_uso,
        sensor=sensor,
        actuador=actuador,
    )

    main_loop(ctx)

if __name__ == "__main__":
    main()
