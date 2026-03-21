Resume a failed or interrupted video generation job using the checkpoint system.

Steps:
1. Run `python main.py status` from `/home/gmktec/projects/shorts` (using the venv) to list all jobs and their current state
2. Identify failed or incomplete jobs (status = "failed" or "running" with a stuck updated_at)
3. Look at the checkpoint file in `output/jobs/<job_id>/checkpoint.json` to understand which phase failed and why
4. If a specific job_id is mentioned by the user, resume that one: `./run.sh resume <job_id>`
5. If no job_id specified, resume the most recent incomplete: `./run.sh resume`
6. Monitor the output for errors
7. If the job fails again at the same phase, investigate the error and suggest fixes

Key checkpoint phases:
- Phase 1: Script generation (LLM)
- Phase 2: Image generation (FLUX Schnell - GPU)
- Phase 3: TTS voice synthesis
- Phase 4: Video generation (Ken Burns or Wan2.1 - GPU)
- Phase 5: Background music
- Phase 6: Final compositing (FFmpeg)

Common failure causes:
- Phase 2/4: GPU out of memory -- suggest reducing batch size or restarting
- Phase 3: TTS engine not responding -- check edge-tts or chatterbox service
- Phase 5: No music tracks in assets/music/tracks/ -- check directory
- Phase 6: FFmpeg error -- check if all input files exist in the job directory
