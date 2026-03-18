import os
import re
import json
import subprocess
import threading
import sqlite3
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

DB_PATH = os.environ.get("DB_PATH", "/app/db/videobot.db")
LOG_PATH = os.environ.get("LOG_PATH", "/app/logs/videobot.log")
OUTPUT_PATH = os.environ.get("OUTPUT_PATH", "/app/output")
COMPOSE_DIR = os.environ.get("COMPOSE_DIR", "/app/shorts")

current_job = {"running": False, "status": "", "step": "", "progress": 0,
               "started_at": None, "log": ""}

# Cola de generación: max 1 en GPU a la vez, los demás esperan
import queue as queue_mod
gen_queue = queue_mod.Queue()
gen_queue_items = []  # Track queued/running items for UI
gen_lock = threading.Lock()
MAX_GPU_JOBS = 1  # Solo 1 job en GPU a la vez (APU comparte RAM)

PIPELINE_STEPS = [
    ("Iniciando", "init"),
    ("Claude decide", "decide"),
    ("Generando imagen 1/3", "img1"),
    ("Generando imagen 2/3", "img2"),
    ("Generando imagen 3/3", "img3"),
    ("Animando clip 1/3", "anim1"),
    ("Animando clip 2/3", "anim2"),
    ("Animando clip 3/3", "anim3"),
    ("Concatenando", "concat"),
    ("Generando voz", "tts"),
    ("Mezclando audio", "mix"),
    ("Subtitulos", "subs"),
    ("CTA overlay", "cta"),
    ("Publicando", "publish"),
    ("Completado", "done"),
]


def parse_step(log_text):
    text = log_text.lower()
    step = "init"
    progress = 0

    step_patterns = [
        (r"iniciando nuevo job", "init", 3),
        (r"tema:", "decide", 7),
        (r"generando imagen 1", "img1", 13),
        (r"generando imagen 2", "img2", 20),
        (r"generando imagen 3", "img3", 27),
        (r"animando.*clip.*1|video_gen.*1/3", "anim1", 35),
        (r"animando.*clip.*2|video_gen.*2/3", "anim2", 45),
        (r"animando.*clip.*3|video_gen.*3/3", "anim3", 55),
        (r"concatena", "concat", 65),
        (r"generando voz|tts|kokoro", "tts", 70),
        (r"mezclando|mix_audio", "mix", 78),
        (r"subt[ií]tulo", "subs", 83),
        (r"cta|suscr[ií]bete", "cta", 88),
        (r"publicando", "publish", 92),
        (r"job completado|completado", "done", 100),
    ]

    for pattern, s, p in step_patterns:
        if re.search(pattern, text):
            step = s
            progress = p

    # Parse progress bars for sub-step granularity
    pbar_matches = re.findall(r'(\d+)%\|', log_text)
    if pbar_matches:
        last_pbar = int(pbar_matches[-1])
        if step in ("img1", "img2", "img3"):
            base = {"img1": 13, "img2": 20, "img3": 27}[step]
            progress = base + int(last_pbar * 0.07)
        elif step in ("anim1", "anim2", "anim3"):
            base = {"anim1": 35, "anim2": 45, "anim3": 55}[step]
            progress = base + int(last_pbar * 0.10)

    return step, min(progress, 100)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _find_generate_container():
    containers = _find_all_generate_containers()
    return containers[0] if containers else None


def _find_all_generate_containers():
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=5
        )
        return [name for name in result.stdout.strip().split("\n")
                if name and "gen" in name.lower() and "webui" not in name.lower()
                and "download" not in name.lower()]
    except Exception:
        return []


def _get_system_stats():
    """Get CPU, RAM, disk stats from /proc and /sys."""
    stats = {}

    # Use host proc/sys if mounted, otherwise container's own
    PROC = "/host/proc" if Path("/host/proc/stat").exists() else "/proc"
    SYS = "/host/sys" if Path("/host/sys").exists() else "/sys"

    # CPU usage (from /proc/stat snapshot)
    try:
        result = subprocess.run(
            ["sh", "-c",
             f"head -1 {PROC}/stat; sleep 0.3; head -1 {PROC}/stat"],
            capture_output=True, text=True, timeout=3
        )
        lines = result.stdout.strip().split("\n")
        if len(lines) == 2:
            def parse_cpu(line):
                parts = line.split()[1:]
                return [int(x) for x in parts]
            c1, c2 = parse_cpu(lines[0]), parse_cpu(lines[1])
            delta = [c2[i] - c1[i] for i in range(len(c1))]
            idle = delta[3] + (delta[4] if len(delta) > 4 else 0)
            total = sum(delta)
            stats["cpu"] = round((1 - idle / total) * 100, 1) if total > 0 else 0
    except Exception:
        stats["cpu"] = 0

    # RAM
    try:
        with open(f"{PROC}/meminfo") as f:
            mem = {}
            for line in f:
                parts = line.split()
                mem[parts[0].rstrip(":")] = int(parts[1])
            total = mem.get("MemTotal", 0)
            available = mem.get("MemAvailable", 0)
            used = total - available
            stats["ram_used_gb"] = round(used / 1048576, 1)
            stats["ram_total_gb"] = round(total / 1048576, 1)
            stats["ram_pct"] = round(used / total * 100, 1) if total > 0 else 0
    except Exception:
        stats["ram_used_gb"] = 0
        stats["ram_total_gb"] = 0
        stats["ram_pct"] = 0

    # Disk
    try:
        result = subprocess.run(
            ["df", "-B1", "/"],
            capture_output=True, text=True, timeout=3
        )
        parts = result.stdout.strip().split("\n")[1].split()
        total = int(parts[1])
        used = int(parts[2])
        stats["disk_used_gb"] = round(used / (1024**3), 1)
        stats["disk_total_gb"] = round(total / (1024**3), 1)
        stats["disk_pct"] = round(used / total * 100, 1) if total > 0 else 0
    except Exception:
        stats["disk_used_gb"] = 0
        stats["disk_total_gb"] = 0
        stats["disk_pct"] = 0

    # GPU - read from running generate container that has GPU access
    stats["gpu_use"] = "-"
    stats["gpu_vram"] = "-"
    stats["gpu_temp"] = "-"
    try:
        # Try rocm-smi inside a generate container
        gen_containers = _find_all_generate_containers()
        gpu_container = gen_containers[0] if gen_containers else None

        if gpu_container:
            result = subprocess.run(
                ["docker", "exec", gpu_container, "python3", "-c",
                 "import json,subprocess;r=subprocess.run(['rocm-smi','--showuse','--showmemuse','--showtemp','--json'],capture_output=True,text=True);print(r.stdout if r.returncode==0 else '{}')"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                gpu_data = json.loads(result.stdout.strip())
                if gpu_data:
                    card = list(gpu_data.values())[0]
                    stats["gpu_use"] = str(card.get("GPU use (%)", card.get("GFX Activity", "-")))
                    if "%" not in stats["gpu_use"] and stats["gpu_use"] != "-":
                        stats["gpu_use"] += "%"
                    mem_use = card.get("GPU memory use (%)", card.get("VRAM Activity", ""))
                    stats["gpu_vram"] = str(mem_use) if mem_use else "-"
                    if "%" not in stats["gpu_vram"] and stats["gpu_vram"] != "-":
                        stats["gpu_vram"] += "%"
                    temp = card.get("Temperature (Sensor edge) (C)", card.get("Temperature", ""))
                    stats["gpu_temp"] = str(temp) + "°C" if temp else "-"
        else:
            # Fallback: try sysfs on host
            import glob
            for prefix in [SYS, "/sys"]:
                for card in ["card0", "card1", "card2"]:
                    p = Path(f"{prefix}/class/drm/{card}/device/gpu_busy_percent")
                    if p.exists():
                        stats["gpu_use"] = p.read_text().strip() + "%"
                        break
                if stats["gpu_use"] != "-":
                    break
    except Exception:
        pass

    return stats


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/videos")
def api_videos():
    date_from = request.args.get("from")
    date_to = request.args.get("to")
    search = request.args.get("q", "").strip()
    limit = int(request.args.get("limit", 50))

    try:
        db = get_db()
        query = "SELECT * FROM published_videos WHERE 1=1"
        params = []

        if date_from:
            query += " AND date(created_at) >= date(?)"
            params.append(date_from)
        if date_to:
            query += " AND date(created_at) <= date(?)"
            params.append(date_to)
        if search:
            query += " AND (title LIKE ? OR topic LIKE ? OR description LIKE ?)"
            like = f"%{search}%"
            params.extend([like, like, like])

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = db.execute(query, params).fetchall()
        db.close()

        videos = []
        for r in rows:
            v = dict(r)
            if v.get("created_at"):
                v["created_at"] = str(v["created_at"])
            if v.get("published_at"):
                v["published_at"] = str(v["published_at"])
            videos.append(v)

        return jsonify(videos)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/status")
def api_status():
    stats = {}
    try:
        db = get_db()
        stats["total"] = db.execute("SELECT COUNT(*) FROM published_videos").fetchone()[0]
        stats["success"] = db.execute("SELECT COUNT(*) FROM published_videos WHERE status='success'").fetchone()[0]
        stats["failed"] = db.execute("SELECT COUNT(*) FROM published_videos WHERE status='failed'").fetchone()[0]
        stats["pending"] = db.execute("SELECT COUNT(*) FROM published_videos WHERE status='pending'").fetchone()[0]
        db.close()
    except Exception:
        pass

    gen_container = _find_generate_container()
    is_running = current_job["running"] or gen_container is not None

    system = _get_system_stats()

    return jsonify({
        "job": {
            **current_job,
            "running": is_running,
            "container": gen_container,
        },
        "stats": stats,
        "system": system,
    })


@app.route("/api/logs")
def api_logs():
    lines = int(request.args.get("lines", 100))
    try:
        result = subprocess.run(
            ["tail", "-n", str(lines), LOG_PATH],
            capture_output=True, text=True, timeout=5
        )
        return jsonify({"logs": result.stdout})
    except Exception as e:
        return jsonify({"logs": f"Error leyendo logs: {e}"})


def _queue_worker():
    """Worker that processes the generation queue one at a time."""
    while True:
        item = gen_queue.get()
        if item is None:
            break
        cname, queued_at = item["name"], item["queued_at"]
        item["status"] = "running"
        item["started_at"] = datetime.now().isoformat()
        try:
            subprocess.run(
                ["docker", "compose", "--profile", "manual", "run",
                 "--rm", "--name", cname, "generate-now"],
                cwd=COMPOSE_DIR,
                capture_output=True, text=True,
                timeout=3600
            )
            item["status"] = "done"
        except subprocess.TimeoutExpired:
            item["status"] = "timeout"
        except Exception as e:
            item["status"] = f"error: {e}"
        finally:
            item["finished_at"] = datetime.now().isoformat()
            gen_queue.task_done()


# Start queue worker thread
_worker_thread = threading.Thread(target=_queue_worker, daemon=True)
_worker_thread.start()


@app.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json(silent=True) or {}
    count = min(int(data.get("count", 1)), 5)  # max 5 en cola

    # Count active (running + queued)
    with gen_lock:
        active = [i for i in gen_queue_items if i["status"] in ("queued", "running")]
        if len(active) >= 5:
            return jsonify({"error": "Maximo 5 videos en cola"}), 409

    queued = []
    for i in range(count):
        suffix = datetime.now().strftime("%H%M%S") + f"-{i}"
        cname = f"videobot-gen-{suffix}"
        item = {
            "name": cname,
            "status": "queued",
            "queued_at": datetime.now().isoformat(),
            "started_at": None,
            "finished_at": None,
        }
        with gen_lock:
            gen_queue_items.append(item)
            # Keep only last 20 items
            if len(gen_queue_items) > 20:
                gen_queue_items[:] = gen_queue_items[-20:]
        gen_queue.put(item)
        queued.append(cname)

    return jsonify({
        "message": f"{len(queued)} video(s) en cola",
        "queued": queued,
        "queue_size": gen_queue.qsize(),
    })


@app.route("/api/queue")
def api_queue():
    """Show current queue state."""
    with gen_lock:
        items = []
        for item in gen_queue_items[-20:]:
            items.append({
                "name": item["name"],
                "status": item["status"],
                "queued_at": item["queued_at"],
                "started_at": item.get("started_at"),
                "finished_at": item.get("finished_at"),
            })
    running = _find_all_generate_containers()
    return jsonify({
        "items": items,
        "running_containers": running,
        "queue_pending": gen_queue.qsize(),
        "max_gpu_jobs": MAX_GPU_JOBS,
    })


@app.route("/api/live-logs")
def api_live_logs():
    lines = int(request.args.get("lines", 150))
    containers = _find_all_generate_containers()

    if not containers:
        return jsonify({"active": False, "jobs": [], "log": "", "step": "", "progress": 0})

    jobs = []
    for c in containers:
        try:
            result = subprocess.run(
                ["docker", "logs", "--tail", str(lines), "--timestamps", c],
                capture_output=True, text=True, timeout=10
            )
            log = result.stdout + result.stderr
            step, progress = parse_step(log)
            status = "Generando..."
            for label, sid in PIPELINE_STEPS:
                if sid == step:
                    status = label
                    break
            jobs.append({
                "container": c,
                "log": log,
                "step": step,
                "progress": progress,
                "status": status,
            })
        except Exception:
            jobs.append({"container": c, "log": "", "step": "init", "progress": 0, "status": "Iniciando..."})

    # For backwards compat, also set top-level fields from first job
    first = jobs[0] if jobs else {}
    return jsonify({
        "active": True,
        "jobs": jobs,
        "log": first.get("log", ""),
        "step": first.get("step", ""),
        "progress": first.get("progress", 0),
        "status": first.get("status", ""),
    })


@app.route("/api/job-log")
def api_job_log():
    return jsonify({"log": current_job["log"], "status": current_job["status"]})


# ─── Topic Ideas ───

@app.route("/api/topics")
def api_topics():
    estado = request.args.get("estado")  # pendiente/usado/descartado
    search = request.args.get("q", "").strip()
    try:
        db = get_db()
        query = "SELECT * FROM topic_ideas WHERE 1=1"
        params = []
        if estado:
            query += " AND estado = ?"
            params.append(estado)
        if search:
            query += " AND (tema LIKE ? OR enfoque LIKE ?)"
            like = f"%{search}%"
            params.extend([like, like])
        query += " ORDER BY CASE prioridad WHEN 'alta' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END, created_at DESC"
        rows = db.execute(query, params).fetchall()
        db.close()
        topics = []
        for r in rows:
            t = dict(r)
            if t.get("created_at"):
                t["created_at"] = str(t["created_at"])
            if t.get("used_at"):
                t["used_at"] = str(t["used_at"])
            topics.append(t)
        return jsonify(topics)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/topics", methods=["POST"])
def api_topics_add():
    """Acepta un JSON array de temas o un solo tema."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    # Normalizar: acepta objeto solo o array
    items = data if isinstance(data, list) else [data]

    db = get_db()
    added = 0
    skipped = 0
    for item in items:
        tema = item.get("tema", "").strip()
        if not tema:
            continue
        # Check duplicado
        existing = db.execute(
            "SELECT id FROM topic_ideas WHERE tema = ?", (tema,)
        ).fetchone()
        if existing:
            skipped += 1
            continue
        enfoque = item.get("enfoque", "").strip() or None
        titulo = item.get("titulo", "").strip() or None
        texto = item.get("texto", "").strip() or None
        hashtags = item.get("hashtags", "").strip() if isinstance(item.get("hashtags"), str) else None
        if isinstance(item.get("hashtags"), list):
            hashtags = " ".join(item["hashtags"])
        categoria = item.get("categoria", "finanzas").strip().lower()
        prioridad = item.get("prioridad", "normal").strip().lower()
        if prioridad not in ("alta", "normal", "baja"):
            prioridad = "normal"
        db.execute(
            "INSERT INTO topic_ideas (tema, enfoque, titulo, texto, hashtags, categoria, prioridad, estado, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'pendiente', ?)",
            (tema, enfoque, titulo, texto, hashtags, categoria, prioridad, datetime.now().isoformat())
        )
        added += 1
    db.commit()
    db.close()
    return jsonify({"added": added, "skipped": skipped, "total": added + skipped})


@app.route("/api/topics/<int:topic_id>", methods=["DELETE"])
def api_topics_delete(topic_id):
    db = get_db()
    db.execute("DELETE FROM topic_ideas WHERE id = ?", (topic_id,))
    db.commit()
    db.close()
    return jsonify({"ok": True})


@app.route("/api/topics/<int:topic_id>/estado", methods=["PATCH"])
def api_topics_update_estado(topic_id):
    data = request.get_json()
    estado = data.get("estado", "").strip()
    if estado not in ("pendiente", "usado", "descartado"):
        return jsonify({"error": "Estado invalido"}), 400
    db = get_db()
    db.execute("UPDATE topic_ideas SET estado = ? WHERE id = ?", (estado, topic_id))
    db.commit()
    db.close()
    return jsonify({"ok": True})


@app.route("/api/topics/stats")
def api_topics_stats():
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM topic_ideas").fetchone()[0]
    pendiente = db.execute("SELECT COUNT(*) FROM topic_ideas WHERE estado='pendiente'").fetchone()[0]
    usado = db.execute("SELECT COUNT(*) FROM topic_ideas WHERE estado='usado'").fetchone()[0]
    descartado = db.execute("SELECT COUNT(*) FROM topic_ideas WHERE estado='descartado'").fetchone()[0]
    db.close()
    return jsonify({"total": total, "pendiente": pendiente, "usado": usado, "descartado": descartado})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
