"""
scheduler/checkpoint.py
Sistema de checkpointing para el pipeline de generacion.
Permite resumir jobs fallidos o interrumpidos desde la ultima fase completada.
"""
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("videobot.checkpoint")

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "output"))
JOBS_DIR = OUTPUT_DIR / "jobs"

PHASE_NAMES = {
    1: "script",
    2: "images",
    3: "tts",
    4: "video",
    5: "music",
    6: "compositing",
}


class JobCheckpoint:
    """
    Gestiona el estado persistente de un job en output/jobs/{job_id}/.
    Usa escritura atomica (write .tmp + os.rename) para evitar corrupcion.
    """

    def __init__(self, job_id: str, data: dict, job_dir: Path):
        self.job_id = job_id
        self.data = data
        self.job_dir = job_dir

    # ── Constructores ────────────────────────────────────────────────────────

    @classmethod
    def create(cls, job_id: str, title: str, script: dict) -> "JobCheckpoint":
        """Crea un nuevo checkpoint para un job."""
        job_dir = JOBS_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "job_id": job_id,
            "title": title,
            "status": "running",
            "failed_phase": None,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "script": script,
            "phases": {},
        }

        cp = cls(job_id, data, job_dir)
        cp.save()
        logger.info(f"Checkpoint creado para job {job_id}")
        return cp

    @classmethod
    def load(cls, job_id: str) -> "JobCheckpoint":
        """Carga un checkpoint existente desde disco."""
        job_dir = JOBS_DIR / job_id
        cp_path = job_dir / "checkpoint.json"

        if not cp_path.exists():
            raise FileNotFoundError(f"No checkpoint found for job {job_id}")

        with open(cp_path, "r") as f:
            data = json.load(f)

        return cls(job_id, data, job_dir)

    @classmethod
    def load_latest_incomplete(cls) -> "JobCheckpoint | None":
        """
        Busca el job incompleto mas reciente (status=failed o running).
        Devuelve None si no hay ninguno.
        """
        if not JOBS_DIR.exists():
            return None

        candidates = []
        for entry in JOBS_DIR.iterdir():
            if not entry.is_dir():
                continue
            cp_path = entry / "checkpoint.json"
            if not cp_path.exists():
                continue
            try:
                with open(cp_path, "r") as f:
                    data = json.load(f)
                if data.get("status") in ("failed", "running"):
                    candidates.append((data.get("updated_at", ""), entry.name, data))
            except (json.JSONDecodeError, KeyError):
                logger.warning(f"Checkpoint corrupto ignorado: {cp_path}")
                continue

        if not candidates:
            return None

        # Ordenar por updated_at descendente, tomar el mas reciente
        candidates.sort(key=lambda x: x[0], reverse=True)
        _, job_id, data = candidates[0]
        job_dir = JOBS_DIR / job_id

        logger.info(f"Job incompleto encontrado: {job_id} (status={data['status']})")
        return cls(job_id, data, job_dir)

    @classmethod
    def list_all(cls) -> list[dict]:
        """Lista todos los jobs con su estado (para la API)."""
        if not JOBS_DIR.exists():
            return []

        jobs = []
        for entry in sorted(JOBS_DIR.iterdir(), key=lambda e: e.stat().st_mtime, reverse=True):
            if not entry.is_dir():
                continue
            cp_path = entry / "checkpoint.json"
            if not cp_path.exists():
                continue
            try:
                with open(cp_path, "r") as f:
                    data = json.load(f)
                # Resumen sin el script completo
                jobs.append({
                    "job_id": data.get("job_id", entry.name),
                    "title": data.get("title", ""),
                    "status": data.get("status", "unknown"),
                    "failed_phase": data.get("failed_phase"),
                    "created_at": data.get("created_at"),
                    "updated_at": data.get("updated_at"),
                    "phases": data.get("phases", {}),
                })
            except (json.JSONDecodeError, KeyError):
                continue

        return jobs

    # ── Control de fases ─────────────────────────────────────────────────────

    def start_phase(self, phase_num: int):
        """Marca una fase como en ejecucion."""
        key = str(phase_num)
        self.data["phases"][key] = {
            "status": "running",
            "started_at": datetime.utcnow().isoformat(),
            "name": PHASE_NAMES.get(phase_num, f"phase_{phase_num}"),
        }
        self.data["status"] = "running"
        self.data["updated_at"] = datetime.utcnow().isoformat()
        self.save()
        logger.debug(f"[{self.job_id}] Fase {phase_num} iniciada")

    def complete_phase(self, phase_num: int, output_path: str | Path, duration: float):
        """Marca una fase como completada con exito."""
        key = str(phase_num)
        phase = self.data["phases"].get(key, {})
        phase.update({
            "status": "done",
            "output": str(output_path),
            "duration_seconds": round(duration, 1),
            "completed_at": datetime.utcnow().isoformat(),
        })
        self.data["phases"][key] = phase
        self.data["updated_at"] = datetime.utcnow().isoformat()

        # Si todas las 6 fases estan done, marcar el job como done
        if all(
            self.data["phases"].get(str(i), {}).get("status") == "done"
            for i in range(1, 7)
        ):
            self.data["status"] = "done"

        self.save()
        logger.debug(f"[{self.job_id}] Fase {phase_num} completada ({duration:.1f}s)")

    def fail_phase(self, phase_num: int, error_msg: str):
        """Marca una fase como fallida."""
        key = str(phase_num)
        phase = self.data["phases"].get(key, {})
        phase.update({
            "status": "failed",
            "error": error_msg[:500],
            "failed_at": datetime.utcnow().isoformat(),
        })
        self.data["phases"][key] = phase
        self.data["status"] = "failed"
        self.data["failed_phase"] = phase_num
        self.data["updated_at"] = datetime.utcnow().isoformat()
        self.save()
        logger.warning(f"[{self.job_id}] Fase {phase_num} fallida: {error_msg[:200]}")

    def is_phase_done(self, phase_num: int) -> bool:
        """Devuelve True si la fase ya fue completada."""
        key = str(phase_num)
        return self.data["phases"].get(key, {}).get("status") == "done"

    def get_phase_output(self, phase_num: int) -> str | None:
        """Devuelve el path del output guardado de una fase completada."""
        key = str(phase_num)
        phase = self.data["phases"].get(key, {})
        if phase.get("status") == "done":
            return phase.get("output")
        return None

    def reset_phases(self, phase_nums: list[int]):
        """Resetea fases especificas para forzar regeneracion."""
        for num in phase_nums:
            key = str(num)
            if key in self.data["phases"]:
                del self.data["phases"][key]
        self.data["status"] = "running"
        self.data["failed_phase"] = None
        self.data["updated_at"] = datetime.utcnow().isoformat()
        self.save()
        logger.info(f"[{self.job_id}] Fases {phase_nums} reseteadas para regeneracion")

    def next_phase(self) -> int:
        """Devuelve el numero de la primera fase que no esta completada."""
        for i in range(1, 7):
            if not self.is_phase_done(i):
                return i
        return 7  # Todas completadas

    # ── Persistencia ─────────────────────────────────────────────────────────

    def save(self):
        """Escritura atomica: escribe a .tmp y luego os.rename()."""
        self.job_dir.mkdir(parents=True, exist_ok=True)
        cp_path = self.job_dir / "checkpoint.json"
        tmp_path = self.job_dir / "checkpoint.json.tmp"

        with open(tmp_path, "w") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())

        os.rename(str(tmp_path), str(cp_path))

    def delete(self):
        """Elimina el directorio completo del job."""
        import shutil
        if self.job_dir.exists():
            shutil.rmtree(self.job_dir, ignore_errors=True)
            logger.info(f"Job {self.job_id} eliminado de disco")
