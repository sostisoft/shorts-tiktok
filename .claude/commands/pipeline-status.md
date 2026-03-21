Check the current pipeline status, running jobs, and recent errors.

Run all of these diagnostic commands from `/home/gmktec/projects/shorts`:

1. **Job status**: Run `venv/bin/python3 main.py status` to list all jobs with their checkpoint state (phase progress, failed phase, timestamps)

2. **Recent logs**: Read the last 50 lines of `logs/videobot.log` to check for recent activity or errors

3. **Pending videos**: List files in `output/pending/` to see videos waiting to be published

4. **Database status**: Run a quick SQLite query to count videos by status:
   ```
   sqlite3 db/videobot.db "SELECT status, COUNT(*) FROM videos GROUP BY status;"
   ```

5. **System resources**: Check if GPU/CPU are under load with:
   - `cat /sys/class/drm/card0/device/gpu_busy_percent` (GPU usage)
   - Free memory overview

6. **Scheduler process**: Check if the scheduler or webui are running:
   ```
   ps aux | grep -E "main.py|webui/app.py" | grep -v grep
   ```

7. **Active checkpoints**: List directories in `output/jobs/` that have active (non-done) checkpoints

Report a summary covering:
- How many videos are pending/published/failed
- Whether any job is currently running
- Any errors in recent logs
- System resource state (GPU busy, memory)
