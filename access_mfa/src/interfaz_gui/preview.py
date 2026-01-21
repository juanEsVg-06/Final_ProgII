# src/interfaz_gui/preview.py
from __future__ import annotations
from dataclasses import dataclass, field
from queue import Queue, Empty
from typing import Optional

import numpy as np

@dataclass
class FrameSink:
    """Cola liviana de frames (BGR) para la GUI."""
    maxsize: int = 2
    _q: Queue = field(default_factory=lambda: Queue(maxsize=2))

    def push(self, frame_bgr: np.ndarray) -> None:
        # Mantiene solo lo más reciente (drop old)
        try:
            while True:
                self._q.get_nowait()
        except Empty:
            pass
        try:
            self._q.put_nowait(frame_bgr)
        except Exception:
            pass

    def pop_latest(self) -> Optional[np.ndarray]:
        try:
            return self._q.get_nowait()
        except Empty:
            return None
