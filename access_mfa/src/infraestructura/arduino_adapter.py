from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from time import sleep

from negocio.exceptions import IntegracionHardwareError


class IActuadorAcceso(ABC):
    """Contrato para actuadores: LEDs / cerradura / alarma."""

    @abstractmethod
    def indicar_exito(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def indicar_fallo(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def abrir_puerta(self) -> None:
        raise NotImplementedError


@dataclass
class ArduinoSimulado(IActuadorAcceso):
    """Simula Arduino"""

    def indicar_exito(self) -> None:
        print("[ARDUINO] EXITO -> LEDs VERDES (simulado)")

    def indicar_fallo(self) -> None:
        print("[ARDUINO] FALLO -> LEDs ROJOS (simulado)")

    def abrir_puerta(self) -> None:
        print("[ARDUINO] PUERTA ABIERTA (simulado)")

    def enviar_leds(self, dedos: list[int]) -> None:
        print(f"[ARDUINO] dedos={dedos} (simulado)")


class ArduinoSerial(IActuadorAcceso):
    """
    Implementación real con pyserial.

    Protocolo:
      - header: 'A' (1 byte)
      - dedos: 5 bytes (0/1) [thumb,index,middle,ring,pinky]
      - estado: 1 byte
          0 = modo mano
          1 = éxito (verdes ON)
          2 = fallo (rojos ON)
    Total: 7 bytes por mensaje.
    """

    HEADER = b"A"
    ESTADO_MANO = 0
    ESTADO_EXITO = 1
    ESTADO_FALLO = 2

    def __init__(self, *, puerto: str, baudrate: int = 9600, timeout: float = 1.0) -> None:
        try:
            import serial  # type: ignore
        except Exception as ex:
            raise IntegracionHardwareError(f"pyserial no disponible: {ex}")

        try:
            self._serial = serial.Serial(port=puerto, baudrate=baudrate, timeout=timeout)
        except Exception as ex:
            raise IntegracionHardwareError(f"No se pudo abrir puerto {puerto}: {ex}")

        sleep(2.0)

        # Aseguramos “todo apagado” al iniciar
        self._enviar_paquete([0, 0, 0, 0, 0], self.ESTADO_MANO)

    def close(self) -> None:
        # Apagar todo al cerrar, para que no se queden LEDs prendidos
        try:
            self._enviar_paquete([0, 0, 0, 0, 0], self.ESTADO_MANO)
        except Exception:
            pass
        try:
            self._serial.close()
        except Exception:
            pass

    def _validar_dedos(self, dedos: list[int]) -> None:
        if len(dedos) != 5:
            raise IntegracionHardwareError("Arduino requiere exactamente 5 valores (5 dedos).")
        if any(d not in (0, 1) for d in dedos):
            raise IntegracionHardwareError("Cada dedo debe ser 0 o 1.")

    def _enviar_paquete(self, dedos: list[int], estado: int) -> None:
        self._validar_dedos(dedos)
        if estado not in (0, 1, 2):
            raise IntegracionHardwareError("Estado inválido (debe ser 0, 1 o 2).")

        payload = bytes(dedos) + bytes([estado])
        packet = self.HEADER + payload

        try:
            self._serial.write(packet)
            self._serial.flush()
        except Exception as ex:
            raise IntegracionHardwareError(f"Fallo enviando datos al Arduino: {ex}")

    def enviar_leds(self, dedos: list[int]) -> None:
        self._enviar_paquete(dedos, self.ESTADO_MANO)

    def indicar_exito(self) -> None:
        """Enciende los 5 verdes."""
        self._enviar_paquete([0, 0, 0, 0, 0], self.ESTADO_EXITO)
        sleep(1.2)
        self._enviar_paquete([0, 0, 0, 0, 0], self.ESTADO_MANO)

    def indicar_fallo(self) -> None:
        """Enciende los 5 rojos."""
        self._enviar_paquete([0, 0, 0, 0, 0], self.ESTADO_FALLO)
        sleep(1.2)
        self._enviar_paquete([0, 0, 0, 0, 0], self.ESTADO_MANO)

    def abrir_puerta(self) -> None:
        # Reutiliza exito como feedback
        self.indicar_exito()


class NullActuador(IActuadorAcceso):
    def indicar_exito(self) -> None:
        pass

    def indicar_fallo(self) -> None:
        pass

    def abrir_puerta(self) -> None:
        pass

    def enviar_leds(self, dedos: list[int]) -> None:
        pass
