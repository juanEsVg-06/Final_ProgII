from cliente.main import construir_sensor

def main():
    # actuador puede ser None si el builder lo permite, o un dummy
    sensor = construir_sensor(actuador=None)  # ajusta según firma real

    print("Captura PIN (4). Haz 4 gestos.")
    pin, _ = sensor.capturar_secuencia(4, gesto_cierre=19, timeout_s=60)
    print("PIN capturado:", pin)

if __name__ == "__main__":
    main()
