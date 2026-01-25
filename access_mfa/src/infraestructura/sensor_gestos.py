from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from negocio.exceptions import IntegracionHardwareError, ValidacionError


class ISensorGestos(ABC):
    """Contrato de captura de gestos."""

    @abstractmethod
    def capturar_secuencia(
        self,
        cantidad: int,
        *,
        gesto_cierre: int | None = None,
        timeout_s: float | None = None,
    ) -> Tuple[List[int], List[float] | None]:
        raise NotImplementedError


@dataclass
class SensorGestosSimulado(ISensorGestos):
    """Uso si no hay cámara."""
    secuencias: list[list[int]]

    def capturar_secuencia(
        self,
        cantidad: int,
        *,
        gesto_cierre: int | None = None,
        timeout_s: float | None = None,
    ) -> Tuple[List[int], List[float] | None]:
        if cantidad <= 0:
            raise ValidacionError("cantidad debe ser > 0")
        if not self.secuencias:
            raise IntegracionHardwareError("No hay secuencias simuladas configuradas.")
        seq = self.secuencias.pop(0)
        return seq[:cantidad], None



class SensorGestosWebcamMediapipeTasks(ISensorGestos):
    def __init__(
        self,
        *,
        camera_index: int = 0,
        preview: bool = True,  # o mostrar_preview (ver alias abajo)
        stable_frames: int = 5,
        debounce_s: float = 0.6,
        flip: bool = True,
        model_path: str | None = None,
        arduino: object | None = None,  # <-- IMPORTANTE (ArduinoSerial / ArduinoSimulado)
        actuador: object | None = None,  # <-- alias por compatibilidad
        # reglas de captura:
        pin_require_no_hand: bool = True,
        patron_require_no_hand: bool = True,
        no_hand_frames: int = 6,
        debug: bool = False,
        mostrar_preview: bool | None = None,  # <-- alias de GUI/console si existía
        frame_sink: object | None = None,
    ) -> None:
        # Alias preview: si te pasan mostrar_preview, lo respeta
        if mostrar_preview is not None:
            preview = bool(mostrar_preview)

        self.camera_index = camera_index
        self.mostrar_preview = bool(preview)

        self.stable_frames = max(1, int(stable_frames))
        self.debounce_s = max(0.0, float(debounce_s))
        self.flip = bool(flip)

        # Arduino integrado:
        self.arduino = arduino if arduino is not None else actuador

        self.pin_require_no_hand = bool(pin_require_no_hand)
        self.patron_require_no_hand = bool(patron_require_no_hand)
        self.no_hand_frames = max(1, int(no_hand_frames))
        self.debug = bool(debug)
        self.frame_sink = frame_sink

        # Umbrales calibrables
        self.margen_y = float(os.getenv("GESTOS_MARGEN_Y", "0.04"))
        self.margen_x = float(os.getenv("GESTOS_MARGEN_X", "0.03"))

        # Imports con delay
        try:
            import cv2  # type: ignore
        except Exception as ex:
            raise IntegracionHardwareError(f"No se pudo importar opencv (cv2): {ex}")

        try:
            import mediapipe as mp  # type: ignore
            from mediapipe.tasks import python  # type: ignore
            from mediapipe.tasks.python import vision  # type: ignore
        except Exception as ex:
            raise IntegracionHardwareError(f"No se pudo importar mediapipe/tasks: {ex}")

        self._cv2 = cv2
        self._mp = mp
        self._mp_python = python
        self._mp_vision = vision

        self.model_path = self._resolver_model_path(model_path)

    def _push_frame(self, frame_bgr) -> None:
        sink = getattr(self, "frame_sink", None)
        if sink is None:
            return
        fn = getattr(sink, "push", None)
        if callable(fn):
            try:
                fn(frame_bgr)
            except Exception:
                pass

    def _emitir_leds_dedos(self, dedos: list[int]) -> None:
        """
        Espejo de dedos al Arduino durante la captura.
        Requiere que el actuador exponga enviar_leds([0/1]*5).
        """
        if self.arduino is None:
            return
        fn = getattr(self.arduino, "enviar_leds", None)
        if not callable(fn):
            return
        try:
            fn(dedos)
        except Exception:
            # Nunca debe romper la captura por un fallo de hardware
            pass

    def _resolver_model_path(self, model_path: str | None) -> str:
        if model_path:
            p = Path(model_path).expanduser().resolve()
            if not p.exists():
                raise IntegracionHardwareError(f"No existe el model .task en: {p}")
            return str(p)

        base = Path(__file__).resolve()
        proyecto = base.parents[2] if len(base.parents) >= 3 else base.parent
        candidato = (proyecto / "models" / "hand_landmarker.task").resolve()
        if not candidato.exists():
            raise IntegracionHardwareError(
                "No se encontró models/hand_landmarker.task.\n"
                f"Ruta esperada: {candidato}\n"
                "Crea la carpeta models/ en la raíz del proyecto y coloca ahí el archivo .task."
            )
        return str(candidato)

    @staticmethod
    def _dedos_a_bitmask(dedos: list[int]) -> int:
        # [thumb,index,middle,ring,pinky] => 1,2,4,8,16
        return dedos[0] * 1 + dedos[1] * 2 + dedos[2] * 4 + dedos[3] * 8 + dedos[4] * 16

    def _detectar_dedos(self, lm, handedness: str) -> list[int]:
        TH_TIP, TH_IP = 4, 3
        IDX_TIP, IDX_PIP = 8, 6
        MID_TIP, MID_PIP = 12, 10
        RING_TIP, RING_PIP = 16, 14
        PINK_TIP, PINK_PIP = 20, 18

        MARGEN_Y = self.margen_y
        MARGEN_X = self.margen_x

        dedos = [0, 0, 0, 0, 0]

        dx_thumb = lm[TH_TIP].x - lm[TH_IP].x
        if handedness.lower() == "right":
            dedos[0] = 1 if dx_thumb > MARGEN_X else 0
        else:
            dedos[0] = 1 if (-dx_thumb) > MARGEN_X else 0

        dedos[1] = 1 if lm[IDX_TIP].y < (lm[IDX_PIP].y - MARGEN_Y) else 0
        dedos[2] = 1 if lm[MID_TIP].y < (lm[MID_PIP].y - MARGEN_Y) else 0
        dedos[3] = 1 if lm[RING_TIP].y < (lm[RING_PIP].y - MARGEN_Y) else 0
        dedos[4] = 1 if lm[PINK_TIP].y < (lm[PINK_PIP].y - MARGEN_Y) else 0

        return dedos

    def capturar_secuencia(
        self,
        cantidad: int,
        *,
        gesto_cierre: int | None = None,
        timeout_s: float | None = None,
    ) -> Tuple[List[int], List[float] | None]:
        if cantidad <= 0:
            raise ValidacionError("cantidad debe ser > 0")

        cv2 = self._cv2
        mp = self._mp
        vision = self._mp_vision
        python = self._mp_python

        base_options = python.BaseOptions(model_asset_path=self.model_path)
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=0.6,
            min_hand_presence_confidence=0.6,
            min_tracking_confidence=0.6,
        )
        landmarker = vision.HandLandmarker.create_from_options(options)

        cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        if hasattr(cv2, "CAP_PROP_BUFFERSIZE"):
            try:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass

        if not cap.isOpened():
            landmarker.close()
            raise IntegracionHardwareError("No se pudo abrir la webcam (isOpened=False).")

        ok = False
        for _ in range(30):
            ok, _ = cap.read()
            if ok:
                break
        if not ok:
            cap.release()
            landmarker.close()
            raise IntegracionHardwareError("La webcam abrió, pero no entrega frames (cap.read() siempre False).")

        secuencia: List[int] = []
        tiempos: List[float] = []
        t_prev: datetime | None = None

        last_accept_ts: datetime | None = None
        stable_count = 0
        current_candidate: int | None = None

        start_ts = datetime.now()
        t0_ms = int(start_ts.timestamp() * 1000)

        # “Sin mano” entre gestos:
        # - PIN (cantidad=4): usa pin_require_no_hand
        # - Patrón (cantidad>=2 y !=4): usa patron_require_no_hand
        if cantidad == 4:
            enforce_no_hand_between = bool(self.pin_require_no_hand)
        elif cantidad >= 2:
            enforce_no_hand_between = bool(self.patron_require_no_hand)
        else:
            enforce_no_hand_between = False

        render_gui = bool(self.mostrar_preview or getattr(self, "frame_sink", None) is not None)

        waiting_no_hand = False
        no_hand_count = 0

        HAND_CONNECTIONS = [
            (0, 1), (1, 2), (2, 3), (3, 4),
            (0, 5), (5, 6), (6, 7), (7, 8),
            (5, 9), (9, 10), (10, 11), (11, 12),
            (9, 13), (13, 14), (14, 15), (15, 16),
            (13, 17), (17, 18), (18, 19), (19, 20),
            (0, 17)
        ]

        win = "SensorGestosWebcam"
        fail_reads = 0
        MAX_FAIL_READS = 60

        try:
            while len(secuencia) < cantidad:
                if timeout_s is not None and (datetime.now() - start_ts).total_seconds() > timeout_s:
                    break

                ok, frame = cap.read()
                if not ok or frame is None:
                    fail_reads += 1
                    if fail_reads >= MAX_FAIL_READS:
                        raise IntegracionHardwareError("La webcam dejó de entregar frames (cap.read falló repetidamente).")
                    continue
                fail_reads = 0

                if self.flip:
                    frame = cv2.flip(frame, 1)

                h, w = frame.shape[:2]

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

                ts_ms = int(datetime.now().timestamp() * 1000) - t0_ms
                result = landmarker.detect_for_video(mp_image, ts_ms)
                hay_mano = False
                gesto_raw: int | None = None

                gesto: int | None = None
                dedos: list[int] | None = None
                mano = "?"

                if result.hand_landmarks:
                    hay_mano = True
                    lm = result.hand_landmarks[0]
                    if result.handedness and result.handedness[0]:
                        mano = result.handedness[0][0].category_name  # "Right"/"Left"

                    dedos = self._detectar_dedos(lm, mano)
                    gesto_raw = self._dedos_a_bitmask(dedos)
                    self._emitir_leds_dedos(dedos)
                    gesto = gesto_raw
                    # Para PIN/Patrón, evitamos aceptar gesto=0 (mano cerrada) como dígito
                    if gesto_raw == 0 and cantidad >= 2:
                        gesto = None

                    # espejo de LEDs (si existe)
                    if self.arduino is not None and hasattr(self.arduino, "enviar_leds"):
                        try:
                            self.arduino.enviar_leds(dedos)  # type: ignore[attr-defined]
                        except Exception:
                            pass

                    if render_gui:
                        xs = [p.x for p in lm]
                        ys = [p.y for p in lm]
                        x1, y1 = int(min(xs) * w), int(min(ys) * h)
                        x2, y2 = int(max(xs) * w), int(max(ys) * h)
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

                        pts = [(int(p.x * w), int(p.y * h)) for p in lm]
                        for a, b in HAND_CONNECTIONS:
                            cv2.line(frame, pts[a], pts[b], (0, 255, 0), 2, cv2.LINE_AA)
                        for (px, py) in pts:
                            cv2.circle(frame, (px, py), 3, (0, 255, 0), -1, cv2.LINE_AA)

                # Bloque “sin mano” (PIN y Patrón)
                extra_line = ""
                if enforce_no_hand_between and waiting_no_hand:
                    if not hay_mano:
                        no_hand_count += 1
                        stable_count = 0
                        current_candidate = None
                        extra_line = f"NEUTRO (retira mano) {no_hand_count}/{self.no_hand_frames}"
                        if no_hand_count >= self.no_hand_frames:
                            waiting_no_hand = False
                            no_hand_count = 0
                    else:
                        # Hay mano: no aceptamos nada hasta que “desaparezca”
                        no_hand_count = 0
                        stable_count = 0
                        current_candidate = None
                        extra_line = "NEUTRO: retira la mano para continuar"                    # Render + (opcional) ventana y luego seguimos
                    if render_gui:
                        msg1 = f"Captura {len(secuencia)}/{cantidad} | ESC=salir | cierre={gesto_cierre if gesto_cierre is not None else '-'}"
                        msg2 = "Sin mano detectada" if not hay_mano else f"Gesto={gesto_raw} bin={gesto_raw:05b} mano={mano}"
                        msg3 = extra_line

                        def put_line(y: int, s: str) -> None:
                            if not s:
                                return
                            cv2.putText(frame, s, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 4, cv2.LINE_AA)
                            cv2.putText(frame, s, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA)

                        put_line(35, msg1)
                        put_line(70, msg2)
                        put_line(105, msg3)

                    # Enviar frame a la GUI (si está configurado)
                    self._push_frame(frame)

                    if self.mostrar_preview:
                        cv2.imshow(win, frame)
                        if cv2.getWindowProperty(win, cv2.WND_PROP_VISIBLE) < 1:
                            break
                        k = cv2.waitKey(1) & 0xFF
                        if k == 27 or k == ord("q"):
                            break

                    continue                # UI normal
                if render_gui:
                    msg1 = f"Captura {len(secuencia)}/{cantidad} | ESC=salir | cierre={gesto_cierre if gesto_cierre is not None else '-'}"
                    msg2 = f"Estabilizando {stable_count}/{self.stable_frames}" if hay_mano else "Sin mano detectada"
                    msg3 = f"Gesto={gesto_raw} bin={gesto_raw:05b} dedos={dedos} mano={mano}" if (gesto is not None and dedos is not None) else ""

                    def put_line(y: int, s: str) -> None:
                        if not s:
                            return
                        cv2.putText(frame, s, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 4, cv2.LINE_AA)
                        cv2.putText(frame, s, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA)

                    put_line(35, msg1)
                    put_line(70, msg2)
                    put_line(105, msg3)

                # Enviar frame a la GUI (si está configurado)
                self._push_frame(frame)

                if self.mostrar_preview:
                    cv2.imshow(win, frame)
                    if cv2.getWindowProperty(win, cv2.WND_PROP_VISIBLE) < 1:
                        break
                    k = cv2.waitKey(1) & 0xFF
                    if k == 27 or k == ord("q"):
                        break


                # Lógica de estabilidad
                if gesto is None:
                    stable_count = 0
                    current_candidate = None
                    continue

                if current_candidate == gesto:
                    stable_count += 1
                else:
                    current_candidate = gesto
                    stable_count = 1

                if stable_count < self.stable_frames:
                    continue

                now = datetime.now()
                if last_accept_ts is not None and (now - last_accept_ts).total_seconds() < self.debounce_s:
                    continue

                if gesto_cierre is not None and gesto == gesto_cierre:
                    break

                if t_prev is not None:
                    tiempos.append((now - t_prev).total_seconds())
                t_prev = now

                secuencia.append(gesto)
                last_accept_ts = now
                stable_count = 0
                current_candidate = None

                if self.debug:
                    print(f"[DEBUG] Aceptado gesto={gesto} -> {len(secuencia)}/{cantidad}")

                if enforce_no_hand_between:
                    waiting_no_hand = True
                    no_hand_count = 0

        finally:
            cap.release()
            # Apaga LEDs al salir (evita que se queden prendidos si cierras aquí)
            if self.arduino is not None and hasattr(self.arduino, "enviar_leds"):
                try:
                    self.arduino.enviar_leds([0, 0, 0, 0, 0])  # type: ignore[attr-defined]
                except Exception:
                    pass

            if self.mostrar_preview:
                try:
                    cv2.destroyAllWindows()
                except Exception:
                    pass
            landmarker.close()

            try:
                self._emitir_leds_dedos([0, 0, 0, 0, 0])
            except Exception:
                pass

        return secuencia, tiempos if tiempos else None
