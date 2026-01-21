# Sistema de Control de Acceso MFA

Proyecto académico (MVP) de control de acceso con **MFA** (Multi-Factor Authentication) combinando:

- **RFID** (algo que tienes)
- **PIN gestual** (4 gestos desde webcam)
- **Patrón gestual** (10 gestos desde webcam)
- **Auditoría** de intentos (éxito / fallo, motivo, factores)

Además, integra (opcional) un **Arduino Uno** para reflejar en LEDs el estado de dedos detectado (5 bits).

---

## 1) Estructura del proyecto

Carpetas principales:

- `src/negocio/`  
  Lógica de dominio: entidades, servicios, reglas, casos de uso, validaciones, excepciones.
- `src/infraestructura/`  
  Integraciones técnicas: webcam (MediaPipe/Tasks), serial Arduino, adaptadores.
- `tests/`  
  Pruebas manuales de cámara y Arduino.
- `models/`  
  Modelos `.task` (MediaPipe Tasks).
- `arduino/`  
  Sketch `.ino` del Arduino Uno.

---

## 2) Requisitos

### Software
- Python (recomendado 3.10–3.12; si 3.13 te funciona, úsalo sin problema)
- Pip / venv
- Webcam (para gestos)
- (Opcional) Arduino Uno + 5 LEDs + resistencias

### Librerías Python
Instala al menos:

- `opencv-python`
- `mediapipe`
- `pyserial` (solo si usarás Arduino)

---

## 3) Instalación

En Windows (PowerShell), desde la carpeta `access_mfa/access_mfa`:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install opencv-python mediapipe pyserial
```

### 2) Ejecutar el programa
- Opción A (recomendada): ejecutar desde src/
Desde la carpeta raíz (la que contiene src/):

```bash
cd src
python -m cliente.main`
```

- Opción B: ejecutar desde raíz usando PYTHONPATH

PowerShell

```bash
$env:PYTHONPATH="src"
python -m cliente.main`
```

CMD

```bash
set PYTHONPATH=src
python -m cliente.main`
```

### 3) Variables de entorno (calibración)

Estas variables permiten ajustar estabilidad del sensor sin modificar código.
Webcam / Gestos
  - `CAMERA_INDEX (default: 0)`
  - `GESTOS_PREVIEW (default: 1) → 1` muestra ventana, 0 sin preview
  - `GESTOS_STABLE_FRAMES (default: 10)`
  - `GESTOS_DEBOUNCE_S (default: 0.9)`
  - `GESTOS_MARGEN_Y (default: 0.04)`
  - `GESTOS_MARGEN_X (default: 0.03)`

PIN más estable (recomendado)
  - `PIN_REQUIRE_NO_HAND (default: 1)` → exige “sin mano” entre dígitos del PIN
  - `NO_HAND_FRAMES (default: 6)`

Arduino (opcional)
  - `ARDUINO_PORT (ej: COM3)`
  - `ARDUINO_BAUD (default: 9600)`

Ejemplo (PowerShell):

```bash
$env:PYTHONPATH="src"
$env:GESTOS_PREVIEW="1"
$env:GESTOS_STABLE_FRAMES="10"
$env:GESTOS_DEBOUNCE_S="0.9"
$env:PIN_REQUIRE_NO_HAND="1"
$env:NO_HAND_FRAMES="6"
python -m cliente.main`
```

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
