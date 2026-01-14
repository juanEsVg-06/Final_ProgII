class DominioError(Exception):
    """Error base del dominio de negocio."""


class ValidacionError(DominioError):
    """Entrada no valida o datos inconsistentes."""


class AutenticacionError(DominioError):
    """Fallo de auth (RFID/PIN/Patrón)."""


class AutorizacionError(DominioError):
    """Fallo de autorizacion (sin permiso / fuera de horario)."""


class RecursoNoEncontradoError(DominioError):
    """Entidad solicitada no existe."""


class IntegracionHardwareError(DominioError):
    """Fallo al comunicarse con webcam/Arduino u otros adaptadores."""
