# Sistema de Control de Acceso MFA (Webcam + Arduino)

Proyecto de Programación II: control de acceso por múltiples factores (MFA) para áreas (laboratorios), usando:
- RFID (factor de posesión)
- PIN gestual (4 gestos) por webcam
- Patrón gestual (10 gestos) por webcam
- Auditoría de intentos (éxito y fallo)

La captura de gestos se realiza con **MediaPipe Tasks** y OpenCV. El Arduino (si está conectado) refleja el estado de los dedos en 5 LEDs.

---

## Estructura

- `src/cliente/` : menú por consola (CLI)
- `src/negocio/` : lógica de negocio (modelos, servicios, caso de uso)
- `src/infraestructura/` : integración webcam + serial Arduino
- `models/hand_landmarker.task` : modelo requerido por MediaPipe Tasks
- `tests/` : pruebas de cámara/sensor

---

## Requisitos

- Python 3.10+ (recomendado 3.11)
- Paquetes:
  - `opencv-python`
  - `mediapipe`
  - `pyserial` (solo si se usará Arduino por serial)

## EJECUCIÓN

**Carpeta a abrir en VS Code:** `access_mfa/access_mfa/` (debe contener `src/` y `models/`).

### 1) Instalar dependencias (una sola vez)
```bash
pip install opencv-python mediapipe pyserial

### 2) Ejecutar el programa
Opción A (recomendada): desde src/
cd src
python -m cliente.main

Opción B: desde la raíz usando PYTHONPATH

PowerShell

$env:PYTHONPATH="src"
python -m cliente.main

CMD

set PYTHONPATH=src
python -m cliente.main