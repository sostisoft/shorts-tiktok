"""
PipelineTimer: tracking de progreso con ETA y estimaciones por fase.
Muestra progreso en tiempo real con barras visuales.
"""
import time
import logging

logger = logging.getLogger("videobot")

# Estimaciones por defecto (segundos) — se actualizan con datos reales
DEFAULT_ESTIMATES = {
    "FLUX imagenes": 60,
    "Wan2.1 clip": 80,
    "Wan2.1 animacion": 240,
    "Concat clips": 3,
    "MusicGen": 45,
    "TTS ES": 3,
    "TTS EN": 3,
    "Mix audio ES": 8,
    "Mix audio EN": 8,
    "Subtitulos ES": 15,
    "Subtitulos EN": 15,
    "Outro ES": 8,
    "Outro EN": 8,
    "Post-prod ES": 35,
    "Post-prod EN": 35,
}

# Peso relativo de cada fase para el progreso total
PHASE_WEIGHTS = {
    "FLUX imagenes": 15,
    "Wan2.1 animacion": 50,
    "Concat clips": 1,
    "MusicGen": 10,
    "TTS ES": 1,
    "Mix audio ES": 2,
    "Subtitulos ES": 3,
    "Outro ES": 2,
    "TTS EN": 1,
    "Mix audio EN": 2,
    "Subtitulos EN": 3,
    "Outro EN": 2,
}
TOTAL_WEIGHT = sum(PHASE_WEIGHTS.values())


def _progress_bar(pct: float, width: int = 20) -> str:
    """Genera barra visual de progreso."""
    filled = int(width * pct / 100)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct:.0f}%"


def _fmt_duration(seconds: float) -> str:
    """Formatea duración humana."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}m{s:02d}s"


class PipelineTimer:
    """Trackea progreso del pipeline con ETA y estimaciones."""

    def __init__(self, job_id: str, estimates: dict = None):
        self.job_id = job_id
        self.start_time = time.time()
        self.phase_times = {}
        self.estimates = {**DEFAULT_ESTIMATES, **(estimates or {})}
        self.completed_weight = 0
        self.current_phase = None
        self.current_phase_start = None

    def start_phase(self, phase: str):
        """Marca inicio de una fase."""
        self.current_phase = phase
        self.current_phase_start = time.time()

    def end_phase(self, phase: str = None):
        """Marca fin de una fase. Retorna duración."""
        phase = phase or self.current_phase
        if not self.current_phase_start:
            return 0

        elapsed = time.time() - self.current_phase_start
        self.phase_times[phase] = elapsed

        # Actualizar progreso
        weight = PHASE_WEIGHTS.get(phase, 2)
        self.completed_weight += weight

        total_elapsed = time.time() - self.start_time
        pct = min(99, (self.completed_weight / TOTAL_WEIGHT) * 100)
        eta = self._estimate_remaining()

        bar = _progress_bar(pct)
        self._log(
            f"⏱ {phase}: {_fmt_duration(elapsed)} "
            f"(total: {_fmt_duration(total_elapsed)}) "
            f"{bar} ETA: ~{_fmt_duration(eta)}"
        )

        self.current_phase = None
        self.current_phase_start = None
        return elapsed

    def log_subphase(self, msg: str):
        """Log dentro de una fase (ej: clip 2/3)."""
        elapsed = time.time() - (self.current_phase_start or self.start_time)
        total = time.time() - self.start_time
        self._log(f"   {msg} ({_fmt_duration(elapsed)}, total: {_fmt_duration(total)})")

    def finish(self):
        """Log final con resumen."""
        total = time.time() - self.start_time
        self._log(f"════ PIPELINE COMPLETO en {_fmt_duration(total)} ════")

        # Resumen por fase
        summary = " | ".join(
            f"{k}: {_fmt_duration(v)}" for k, v in self.phase_times.items()
        )
        self._log(f"Tiempos: {summary}")
        return total

    def estimated_total(self) -> str:
        """Retorna estimación total del pipeline como string legible."""
        total_est = sum(self.estimates.get(k, 30) for k in PHASE_WEIGHTS)
        return _fmt_duration(total_est)

    def _estimate_remaining(self) -> float:
        """Estima tiempo restante basado en fases completadas y sus tiempos reales."""
        remaining = 0
        for phase, weight in PHASE_WEIGHTS.items():
            if phase not in self.phase_times:
                remaining += self.estimates.get(phase, 30)
        return max(0, remaining)

    def _log(self, msg: str):
        """Log + print para docker logs y web UI."""
        full = f"[{self.job_id}] {msg}"
        logger.info(full)
        print(full, flush=True)
