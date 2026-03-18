# 06 — Scheduler, base de datos y main.py

## Módulos

- `db/models.py` — SQLAlchemy models + helpers (PublishedVideo)
- `scheduler/runner.py` — Ciclo completo: decide → genera → publica → registra
- `main.py` — Punto de entrada con APScheduler (10:00 y 18:00 Madrid)

## Ejecución como servicio systemd

```bash
sudo cp videobot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable videobot
sudo systemctl start videobot
sudo journalctl -u videobot -f
```

Ver código completo en los ficheros fuente.
