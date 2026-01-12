# Sistema de Control de Acceso MFA (Webcam + Arduino)

Proyecto final de **Programación II**: sistema de control de acceso por **múltiples factores (MFA)** para áreas (por ejemplo, laboratorios), combinando:

- **RFID** (posesión)
- **PIN gestual** (4 gestos) capturado por webcam
- **Patrón gestual** (10 gestos) capturado por webcam
- **Auditoría** de intentos (éxito/fallo)

La captura de gestos se realiza con **MediaPipe Tasks** y **OpenCV**.  
El Arduino (si está conectado) puede reflejar el estado de los dedos en **5 LEDs** por serial.

---

## Tecnologías

- Python
- OpenCV (`opencv-python`)
- MediaPipe (`mediapipe`) + modelo `hand_landmarker.task`
- Serial Arduino (`pyserial`) *(opcional, solo si se conecta Arduino)*

---

## Estructura del proyecto

- `src/cliente/` : menú por consola (CLI) y “wiring” (creación de servicios + handlers)
- `src/negocio/` : lógica de negocio (modelos, servicios, caso de uso)
- `src/infraestructura/` : integración (webcam + MediaPipe + Arduino serial)
- `models/hand_landmarker.task` : modelo requerido por MediaPipe Tasks
- `arduino/ArduinoUno_progra2_P2.ino` : sketch de Arduino (protocolo serial)
- `tests/` : pruebas rápidas del sensor (webcam)

---

## EJECUCIÓN

**Carpeta a abrir en VS Code:** la que contiene `src/` y `models/`.

### 1) Instalar dependencias

```bash
pip install opencv-python mediapipe pyserial
```

### 2) Ejecutar el programa
- Opción A (recomendada): ejecutar desde src/
Desde la carpeta raíz (la que contiene src/):

`cd src
python -m cliente.main`

- Opción B: ejecutar desde raíz usando PYTHONPATH

PowerShell

`$env:PYTHONPATH="src"
python -m cliente.main`

CMD

`set PYTHONPATH=src
python -m cliente.main`

### 3) Variables de entorno (calibración)

Estas variables permiten ajustar estabilidad del sensor sin modificar código.
Webcam / Gestos
  - CAMERA_INDEX (default: 0)
  - GESTOS_PREVIEW (default: 1) → 1 muestra ventana, 0 sin preview
  - GESTOS_STABLE_FRAMES (default: 10)
  - GESTOS_DEBOUNCE_S (default: 0.9)
  - GESTOS_MARGEN_Y (default: 0.04)
  - GESTOS_MARGEN_X (default: 0.03)

PIN más estable (recomendado)
  - PIN_REQUIRE_NO_HAND (default: 1) → exige “sin mano” entre dígitos del PIN
  - NO_HAND_FRAMES (default: 6)

Arduino (opcional)
  - ARDUINO_PORT (ej: COM3)
  - ARDUINO_BAUD (default: 9600)

Ejemplo (PowerShell):

`$env:PYTHONPATH="src"
$env:GESTOS_PREVIEW="1"
$env:GESTOS_STABLE_FRAMES="10"
$env:GESTOS_DEBOUNCE_S="0.9"
$env:PIN_REQUIRE_NO_HAND="1"
$env:NO_HAND_FRAMES="6"
python -m cliente.main`

### 4) Flujo recomendado para demo/defensa
  - Crear estudiante
  - Crear área
  - Asignar permiso
  - Asignar RFID
  - Configurar PIN (4 gestos)
  - Enrolar patrón (10 gestos)
  - Intentar acceso
  - Ver auditoría y listados

### 5) Arduino (.ino) – Protocolo serial

El Arduino recibe 5 bytes (0/1), uno por dedo, para encender 5 LEDs.

En Python se envía:

`ser.write(bytes(dedos))`
donde dedos = `[thumb, index, middle, ring, pinky]` con valores 0/1.

### 6) Troubleshooting rápido
  - La webcam no abre: cierra apps que usen cámara (Zoom/Teams/Discord) y reinicia.
  - No detecta mano estable: sube `GESTOS_STABLE_FRAMES` o `GESTOS_DEBOUNCE_S.`
  - PIN falla mucho: activa `PIN_REQUIRE_NO_HAND=1` para separar dígitos con “sin mano”.

::contentReference[oaicite:0]{index=0}
```bash
pip install opencv-python mediapipe pyserial
