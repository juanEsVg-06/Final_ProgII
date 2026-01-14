import os
import time
from infraestructura.arduino_adapter import ArduinoSerial

PORT = os.getenv("ARDUINO_PORT", "COM5")   # cambia o setea env var
BAUD = int(os.getenv("ARDUINO_BAUD", "9600"))

def main():
    ard = ArduinoSerial(puerto=PORT, baudrate=BAUD, timeout=1.0)

    # 1) Lectura (status=0): dedos en azules
    patrones = [
        [1,0,0,0,0],
        [0,1,0,0,0],
        [0,0,1,0,0],
        [0,0,0,1,0],
        [0,0,0,0,1],
        [0,0,0,0,0],
    ]
    for p in patrones:
        ard.enviar_leds(p)
        print("Lectura dedos:", p)
        time.sleep(0.7)

    # 2) Éxito: azules ON
    print("EXITO (azules ON)")
    ard.indicar_exito()
    time.sleep(0.5)

    # 3) Fallo: rojos ON
    print("FALLO (rojos ON)")
    ard.indicar_fallo()
    time.sleep(0.5)

    ard.close()
    print("Listo.")

if __name__ == "__main__":
    main()
