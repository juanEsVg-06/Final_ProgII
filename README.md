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
