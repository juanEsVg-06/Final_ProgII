import time
import serial

PORT = "COM5"      # <-- cambia esto
BAUD = 9600        # <-- cambia si tu ino usa otro baud

def enviar(dedos):
    # dedos debe ser lista de 5 ints 0/1
    ser.write(bytes(dedos))

if __name__ == "__main__":
    ser = serial.Serial(PORT, BAUD, timeout=1)
    time.sleep(2)  # Arduino reset al abrir serial

    print("Prueba 1: uno por uno")
    patrones = [
        [1,0,0,0,0],
        [0,1,0,0,0],
        [0,0,1,0,0],
        [0,0,0,1,0],
        [1,1,1,1,1],
    ]
    for p in patrones:
        enviar(p)
        print("Enviado:", p)
        time.sleep(1)

    print("Prueba 2: todos ON / todos OFF")
    enviar([1,1,1,1,1]); time.sleep(1)
    enviar([0,0,0,0,0]); time.sleep(1)

    ser.close()
    print("Listo.")
