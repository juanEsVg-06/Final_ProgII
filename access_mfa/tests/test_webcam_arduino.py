from cliente.main import construir_sensor, construir_actuador

def main():
    actuador = construir_actuador()
    sensor = construir_sensor(actuador)

    print("Captura PIN (4). Haz 4 gestos.")
    pin, _ = sensor.capturar_secuencia(4, gesto_cierre=19, timeout_s=60)
    print("PIN capturado:", pin)

if __name__ == "__main__":
    main()
