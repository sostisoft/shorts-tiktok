"""
webui/app.py — Dashboard nativo con WebSocket para VideoBot Finanzas Claras.
Logs en tiempo real via SocketIO + file watcher.
"""
import os
import re
import json
import subprocess
import threading
import sqlite3
import time
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, jsonify, request, send_from_directory, abort
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config["SECRET_KEY"] = "videobot-finanzas-2026"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Rutas
PROJECT_DIR = Path(os.environ.get("PROJECT_DIR", str(Path(__file__).resolve().parent.parent)))
DB_PATH = os.environ.get("DB_PATH", str(PROJECT_DIR / "db" / "videobot.db"))
LOG_PATH = os.environ.get("LOG_PATH", str(PROJECT_DIR / "logs" / "videobot.log"))
OUTPUT_PATH = os.environ.get("OUTPUT_PATH", str(PROJECT_DIR / "output"))
RUN_SH = str(PROJECT_DIR / "run.sh")

# Estado de jobs
import queue as queue_mod
gen_queue = queue_mod.Queue()
gen_queue_items = []
gen_lock = threading.Lock()

PIPELINE_STEPS = [
    ("Iniciando", "init"), ("Guion LLM", "decide"),
    ("FLUX Imagenes", "flux"), ("Ken Burns Clips", "clips"),
    ("Concat", "concat"), ("MusicGen", "music"),
    ("TTS ES", "tts_es"), ("Mix ES", "mix_es"), ("Subs ES", "subs_es"), ("Outro ES", "cta_es"),
    ("TTS EN", "tts_en"), ("Mix EN", "mix_en"), ("Subs EN", "subs_en"), ("Outro EN", "cta_en"),
    ("Completado", "done"),
]


def parse_step(log_text):
    text = log_text.lower()
    step, progress = "init", 0
    patterns = [
        (r"iniciando.*pipeline|generaci[oó]n manual|tiempo estimado", "init", 2),
        (r"generando gui[oó]n|\[1/6\]|gui[oó]n generado", "decide", 5),
        # FLUX images (5 images = 8-35%)
        (r"flux|generando.*imagenes.*flux", "flux", 8),
        (r"imagen 1/|frame_00|img_00", "flux", 12),
        (r"imagen 2/|frame_01|img_01", "flux", 17),
        (r"imagen 3/|frame_02|img_02", "flux", 22),
        (r"imagen 4/|frame_03|img_03", "flux", 27),
        (r"imagen 5/|frame_04|img_04|⏱ flux", "flux", 35),
        # Ken Burns / Wan2.1 clips
        (r"animando|ken burns|wan2", "clips", 37),
        (r"clip 1/", "clips", 39),
        (r"clip 2/", "clips", 41),
        (r"clip 3/", "clips", 43),
        (r"clip 4/", "clips", 45),
        (r"clip 5/|⏱ wan2|⏱ ken", "clips", 48),
        # Concat + Music
        (r"concatena", "concat", 50),
        (r"musicgen|m[uú]sica de fondo", "music", 55),
        (r"⏱ musicgen", "music", 60),
        # ES version
        (r"versi[oó]n es", "tts_es", 62),
        (r"tts es|kokoro.*dora|chatterbox.*es", "tts_es", 65),
        (r"mix audio es", "mix_es", 70),
        (r"subt[ií]tulos es", "subs_es", 75),
        (r"outro es", "cta_es", 78),
        # EN version
        (r"versi[oó]n en", "tts_en", 80),
        (r"tts en|kokoro.*sarah|chatterbox.*en", "tts_en", 83),
        (r"mix audio en", "mix_en", 87),
        (r"subt[ií]tulos en", "subs_en", 91),
        (r"outro en", "cta_en", 94),
        # Done
        (r"pipeline.*completo|completado en", "done", 100),
    ]
    for pat, s, p in patterns:
        if re.search(pat, text):
            step, progress = s, p
    return step, min(progress, 100)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _get_system_stats():
    stats = {}
    # CPU
    try:
        r = subprocess.run(["sh", "-c", "head -1 /proc/stat; sleep 0.3; head -1 /proc/stat"],
                           capture_output=True, text=True, timeout=3)
        lines = r.stdout.strip().split("\n")
        if len(lines) == 2:
            c1 = [int(x) for x in lines[0].split()[1:]]
            c2 = [int(x) for x in lines[1].split()[1:]]
            d = [c2[i]-c1[i] for i in range(len(c1))]
            idle = d[3] + (d[4] if len(d) > 4 else 0)
            stats["cpu"] = round((1 - idle/sum(d)) * 100, 1) if sum(d) > 0 else 0
    except Exception:
        stats["cpu"] = 0

    # RAM
    try:
        mem = {}
        with open("/proc/meminfo") as f:
            for line in f:
                p = line.split()
                mem[p[0].rstrip(":")] = int(p[1])
        total, avail = mem.get("MemTotal", 0), mem.get("MemAvailable", 0)
        used = total - avail
        stats.update(ram_used_gb=round(used/1048576, 1), ram_total_gb=round(total/1048576, 1),
                     mem_total_gb=round(total/1048576, 1),
                     ram_pct=round(used/total*100, 1) if total else 0)
    except Exception:
        stats.update(ram_used_gb=0, ram_total_gb=0, ram_pct=0)

    # Disk
    try:
        r = subprocess.run(["df", "-B1", "/"], capture_output=True, text=True, timeout=3)
        p = r.stdout.strip().split("\n")[1].split()
        t, u = int(p[1]), int(p[2])
        stats.update(disk_used_gb=round(u/(1024**3), 1), disk_total_gb=round(t/(1024**3), 1),
                     disk_pct=round(u/t*100, 1) if t else 0)
    except Exception:
        stats.update(disk_used_gb=0, disk_total_gb=0, disk_pct=0)

    # Temps
    stats["cpu_temp"] = stats["nvme_temp"] = "-"
    try:
        import glob as gm
        for hw in gm.glob("/sys/class/hwmon/hwmon*"):
            nf = Path(hw) / "name"
            if not nf.exists(): continue
            n = nf.read_text().strip()
            if n == "k10temp":
                tf = Path(hw) / "temp1_input"
                if tf.exists(): stats["cpu_temp"] = f"{int(tf.read_text().strip())//1000}°C"
            elif n == "nvme":
                tf = Path(hw) / "temp1_input"
                if tf.exists(): stats["nvme_temp"] = f"{int(tf.read_text().strip())//1000}°C"
    except Exception: pass

    # GPU
    stats.update(gpu_use="-", gpu_vram="-", gpu_vram_used_gb=0, gpu_vram_total_gb=0,
                 gpu_temp="-", gpu_power="-", gtt_used_gb=0, gtt_total_gb=0, gtt_pct=0)
    try:
        import glob as gm
        for card in ["card0", "card1"]:
            base = Path(f"/sys/class/drm/{card}/device")
            busy = base / "gpu_busy_percent"
            if not busy.exists(): continue
            stats["gpu_use"] = busy.read_text().strip() + "%"
            for key, fname in [("mem_info_vram_used", "vram_used"), ("mem_info_vram_total", "vram_total"),
                               ("mem_info_gtt_used", "gtt_used"), ("mem_info_gtt_total", "gtt_total")]:
                f = base / key
                if f.exists():
                    stats[fname] = int(f.read_text().strip())
            if stats.get("vram_total"):
                stats["gpu_vram"] = f"{stats['vram_used']/stats['vram_total']*100:.1f}%"
                stats["gpu_vram_used_gb"] = round(stats["vram_used"]/(1024**3), 1)
                stats["gpu_vram_total_gb"] = round(stats["vram_total"]/(1024**3), 1)
            if stats.get("gtt_total"):
                stats["gtt_used_gb"] = round(stats.get("gtt_used", 0)/(1024**3), 1)
                stats["gtt_total_gb"] = round(stats["gtt_total"]/(1024**3), 1)
                stats["gtt_pct"] = round(stats.get("gtt_used", 0)/stats["gtt_total"]*100, 1)
            # Cleanup raw values
            for k in ["vram_used", "vram_total", "gtt_used", "gtt_total"]:
                stats.pop(k, None)
            hw = gm.glob(str(base / "hwmon/hwmon*/temp1_input"))
            if hw: stats["gpu_temp"] = f"{int(Path(hw[0]).read_text().strip())//1000}°C"
            pw = gm.glob(str(base / "hwmon/hwmon*/power1_average"))
            if pw: stats["gpu_power"] = f"{int(Path(pw[0]).read_text().strip())/1e6:.0f}W"
            break
    except Exception: pass
    return stats


# ── Log file watcher — emits new lines via WebSocket ──

class LogWatcher(threading.Thread):
    def __init__(self, path, socketio):
        super().__init__(daemon=True)
        self.path = path
        self.sio = socketio
        self._stop = threading.Event()

    def run(self):
        while not self._stop.is_set():
            try:
                if not Path(self.path).exists():
                    time.sleep(1)
                    continue
                with open(self.path, "r") as f:
                    f.seek(0, 2)  # end of file
                    while not self._stop.is_set():
                        line = f.readline()
                        if line:
                            line = line.rstrip()
                            step, progress = parse_step(line)
                            self.sio.emit("log_line", {
                                "line": line, "step": step, "progress": progress,
                                "ts": datetime.now().isoformat()
                            })
                        else:
                            time.sleep(0.3)
            except Exception:
                time.sleep(2)


_log_watcher = LogWatcher(LOG_PATH, socketio)
_log_watcher.start()


# ── Routes ──

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    stats = {}
    try:
        db = get_db()
        for table in ["videos", "published_videos"]:
            try:
                stats["total"] = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                stats["success"] = db.execute(f"SELECT COUNT(*) FROM {table} WHERE status IN ('published','success')").fetchone()[0]
                stats["failed"] = db.execute(f"SELECT COUNT(*) FROM {table} WHERE status IN ('error','failed')").fetchone()[0]
                stats["pending"] = db.execute(f"SELECT COUNT(*) FROM {table} WHERE status='pending'").fetchone()[0]
                break
            except sqlite3.OperationalError:
                continue
        db.close()
    except Exception: pass

    with gen_lock:
        is_running = any(i["status"] == "running" for i in gen_queue_items)
        running_name = next((i["name"] for i in gen_queue_items if i["status"] == "running"), None)
        queued_count = sum(1 for i in gen_queue_items if i["status"] == "queued")

    return jsonify({
        "job": {"running": is_running, "name": running_name, "queued": queued_count},
        "stats": stats,
        "system": _get_system_stats(),
    })


@app.route("/api/logs")
def api_logs():
    lines = int(request.args.get("lines", 100))
    try:
        r = subprocess.run(["tail", "-n", str(lines), LOG_PATH], capture_output=True, text=True, timeout=5)
        return jsonify({"logs": r.stdout})
    except Exception as e:
        return jsonify({"logs": f"Error: {e}"})


@app.route("/api/videos")
def api_videos():
    try:
        db = get_db()
        for table in ["videos", "published_videos"]:
            try:
                rows = db.execute(f"SELECT * FROM {table} ORDER BY created_at DESC LIMIT 100").fetchall()
                db.close()
                return jsonify([dict(r) for r in rows])
            except sqlite3.OperationalError:
                continue
        db.close()
        return jsonify([])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/videos/pending/<filename>")
def serve_pending_video(filename):
    """Sirve un video de output/pending/ por URL."""
    pending_dir = Path(OUTPUT_PATH) / "pending"
    if not (pending_dir / filename).is_file():
        abort(404)
    return send_from_directory(str(pending_dir), filename)


@app.route("/videos/pending")
def list_pending_videos():
    """Lista todos los videos pendientes con sus URLs."""
    pending_dir = Path(OUTPUT_PATH) / "pending"
    if not pending_dir.exists():
        return jsonify([])
    videos = sorted(pending_dir.glob("*.mp4"), key=lambda f: f.stat().st_mtime, reverse=True)
    base = request.host_url.rstrip("/")
    return jsonify([
        {"name": v.name, "size_mb": round(v.stat().st_size / 1048576, 1),
         "url": f"{base}/videos/pending/{v.name}"}
        for v in videos
    ])


# ── Generation ──

def _run_generate(item):
    item["status"] = "running"
    item["started_at"] = datetime.now().isoformat()
    socketio.emit("job_update", {"name": item["name"], "status": "running", "started_at": item["started_at"]})
    try:
        resume_id = item.get("resume_job_id")
        cmd_args = [RUN_SH, "resume", resume_id] if resume_id else [RUN_SH, "generate"]
        proc = subprocess.Popen(
            cmd_args, cwd=str(PROJECT_DIR),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        item["pid"] = proc.pid
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                step, progress = parse_step(line)
                socketio.emit("gen_output", {
                    "name": item["name"], "line": line,
                    "step": step, "progress": progress,
                })
        proc.wait(timeout=3600)
        item["status"] = "done" if proc.returncode == 0 else f"error:{proc.returncode}"
    except subprocess.TimeoutExpired:
        proc.kill()
        item["status"] = "timeout"
    except Exception as e:
        item["status"] = f"error:{e}"
    finally:
        item["finished_at"] = datetime.now().isoformat()
        socketio.emit("job_update", {"name": item["name"], "status": item["status"],
                                      "finished_at": item["finished_at"]})


def _queue_worker():
    while True:
        item = gen_queue.get()
        if item is None: break
        _run_generate(item)
        gen_queue.task_done()

threading.Thread(target=_queue_worker, daemon=True).start()


@app.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json(silent=True) or {}
    count = min(int(data.get("count", 1)), 5)
    with gen_lock:
        active = [i for i in gen_queue_items if i["status"] in ("queued", "running")]
        if len(active) >= 5:
            return jsonify({"error": "Max 5 en cola"}), 409
    queued = []
    for i in range(count):
        name = f"gen-{datetime.now().strftime('%H%M%S')}-{i}"
        item = {"name": name, "status": "queued", "queued_at": datetime.now().isoformat(),
                "started_at": None, "finished_at": None, "pid": None}
        with gen_lock:
            gen_queue_items.append(item)
            if len(gen_queue_items) > 20:
                gen_queue_items[:] = gen_queue_items[-20:]
        gen_queue.put(item)
        queued.append(name)
        socketio.emit("job_update", {"name": name, "status": "queued"})
    return jsonify({"message": f"{len(queued)} video(s) en cola", "queued": queued})


@app.route("/api/queue")
def api_queue():
    with gen_lock:
        items = [{"name": i["name"], "status": i["status"], "queued_at": i["queued_at"],
                  "started_at": i.get("started_at"), "finished_at": i.get("finished_at")}
                 for i in gen_queue_items[-20:]]
    return jsonify({"items": items, "queue_pending": gen_queue.qsize()})


# ── Topics ──

@app.route("/api/topics")
def api_topics():
    estado = request.args.get("estado")
    search = request.args.get("q", "").strip()
    try:
        db = get_db()
        q = "SELECT * FROM topic_ideas WHERE 1=1"
        params = []
        if estado: q += " AND estado = ?"; params.append(estado)
        if search: q += " AND (tema LIKE ? OR enfoque LIKE ?)"; params.extend([f"%{search}%"]*2)
        q += " ORDER BY CASE prioridad WHEN 'alta' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END, created_at DESC"
        rows = db.execute(q, params).fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/topics", methods=["POST"])
def api_topics_add():
    data = request.get_json()
    if not data: return jsonify({"error": "No JSON"}), 400
    items = data if isinstance(data, list) else [data]
    db = get_db()
    added = skipped = 0
    for it in items:
        tema = it.get("tema", "").strip()
        if not tema: continue
        if db.execute("SELECT id FROM topic_ideas WHERE tema = ?", (tema,)).fetchone():
            skipped += 1; continue
        hashtags = it.get("hashtags", "")
        if isinstance(hashtags, list): hashtags = " ".join(hashtags)
        prio = it.get("prioridad", "normal").strip().lower()
        if prio not in ("alta", "normal", "baja"): prio = "normal"
        db.execute("INSERT INTO topic_ideas (tema,enfoque,titulo,texto,hashtags,categoria,prioridad,estado,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                   (tema, it.get("enfoque","").strip() or None, it.get("titulo","").strip() or None,
                    it.get("texto","").strip() or None, hashtags or None,
                    it.get("categoria","finanzas").strip().lower(), prio, "pendiente", datetime.now().isoformat()))
        added += 1
    db.commit(); db.close()
    return jsonify({"added": added, "skipped": skipped})


@app.route("/api/topics/<int:tid>", methods=["DELETE"])
def api_topics_delete(tid):
    db = get_db(); db.execute("DELETE FROM topic_ideas WHERE id = ?", (tid,)); db.commit(); db.close()
    return jsonify({"ok": True})


@app.route("/api/topics/<int:tid>/estado", methods=["PATCH"])
def api_topics_update(tid):
    estado = request.get_json().get("estado", "")
    if estado not in ("pendiente", "usado", "descartado"): return jsonify({"error": "Invalid"}), 400
    db = get_db(); db.execute("UPDATE topic_ideas SET estado = ? WHERE id = ?", (estado, tid)); db.commit(); db.close()
    return jsonify({"ok": True})


@app.route("/api/topics/stats")
def api_topics_stats():
    try:
        db = get_db()
        r = {k: db.execute(f"SELECT COUNT(*) FROM topic_ideas WHERE estado='{k}'").fetchone()[0]
             for k in ("pendiente", "usado", "descartado")}
        r["total"] = sum(r.values()); db.close()
        return jsonify(r)
    except Exception:
        return jsonify({"total": 0, "pendiente": 0, "usado": 0, "descartado": 0})


# ── Checkpoint / Jobs API ──

@app.route("/api/jobs")
def api_jobs():
    """Lista todos los jobs con su estado de checkpoint."""
    try:
        from scheduler.checkpoint import JobCheckpoint
        jobs = JobCheckpoint.list_all()
        return jsonify(jobs)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/resume/<job_id>", methods=["POST"])
def api_resume(job_id):
    """Reanuda un job fallido en un hilo separado."""
    try:
        from scheduler.checkpoint import JobCheckpoint
        cp = JobCheckpoint.load(job_id)
        if cp.data["status"] == "done":
            return jsonify({"error": "Job ya completado"}), 400
        if cp.data["status"] == "running":
            return jsonify({"error": "Job ya en ejecucion"}), 409

        # Lanzar en hilo via la cola de generacion existente
        name = f"resume-{job_id}"
        item = {"name": name, "status": "queued", "queued_at": datetime.now().isoformat(),
                "started_at": None, "finished_at": None, "pid": None, "resume_job_id": job_id}
        with gen_lock:
            gen_queue_items.append(item)
            if len(gen_queue_items) > 20:
                gen_queue_items[:] = gen_queue_items[-20:]
        gen_queue.put(item)
        socketio.emit("job_update", {"name": name, "status": "queued"})
        return jsonify({"message": f"Job {job_id} en cola para resumir", "name": name})
    except FileNotFoundError:
        return jsonify({"error": f"Job {job_id} no encontrado"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/jobs/<job_id>", methods=["DELETE"])
def api_jobs_delete(job_id):
    """Elimina un job fallido de disco."""
    try:
        from scheduler.checkpoint import JobCheckpoint
        cp = JobCheckpoint.load(job_id)
        if cp.data["status"] == "running":
            return jsonify({"error": "No se puede eliminar un job en ejecucion"}), 409
        cp.delete()
        return jsonify({"ok": True, "message": f"Job {job_id} eliminado"})
    except FileNotFoundError:
        return jsonify({"error": f"Job {job_id} no encontrado"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── SocketIO events ──

@socketio.on("connect")
def on_connect():
    # Enviar últimas 50 líneas del log al conectar
    try:
        r = subprocess.run(["tail", "-n", "50", LOG_PATH], capture_output=True, text=True, timeout=5)
        emit("initial_logs", {"logs": r.stdout})
    except Exception:
        emit("initial_logs", {"logs": ""})

    # Enviar estado actual de jobs
    with gen_lock:
        for item in gen_queue_items[-10:]:
            emit("job_update", {"name": item["name"], "status": item["status"],
                                "started_at": item.get("started_at"), "finished_at": item.get("finished_at")})


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5050, debug=False, allow_unsafe_werkzeug=True)
