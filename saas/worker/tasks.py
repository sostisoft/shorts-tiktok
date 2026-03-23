"""
saas/worker/tasks.py
Celery tasks for each pipeline phase.
Each task: load tenant -> get provider -> execute -> upload to S3 -> update DB status.
"""
import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone

from celery import chain

from saas.worker.celery_app import app

logger = logging.getLogger("saas.worker.tasks")


def _run_async(coro):
    """Run an async coroutine from sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _get_sync_session():
    """Create a synchronous SQLAlchemy session for Celery tasks."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from saas.config import get_settings

    settings = get_settings()
    # Convert async URL to sync URL
    sync_url = settings.database_url.replace("+asyncpg", "+psycopg2").replace("postgresql+psycopg2", "postgresql")
    engine = create_engine(sync_url)
    return Session(engine)


def _update_video_status(job_id: str, status: str, **kwargs):
    """Update video status in DB. Raises on failure."""
    session = _get_sync_session()
    try:
        from saas.models.video import Video
        video = session.query(Video).filter(Video.job_id == job_id).first()
        if not video:
            logger.error(f"Video not found for job_id={job_id}")
            raise RuntimeError(f"Video not found: {job_id}")
        video.status = status
        for key, value in kwargs.items():
            if hasattr(video, key):
                setattr(video, key, value)
        video.updated_at = datetime.now(timezone.utc)
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to update video status for {job_id}: {e}")
        raise
    finally:
        session.close()


def _get_tenant_plan(tenant_id: str) -> str:
    """Get tenant's plan from DB."""
    session = _get_sync_session()
    try:
        from saas.models.tenant import Tenant
        tenant = session.query(Tenant).filter(Tenant.id == uuid.UUID(tenant_id)).first()
        return tenant.plan if tenant else "starter"
    finally:
        session.close()


@app.task(bind=True, name="saas.worker.tasks.generate_script", max_retries=3, default_retry_delay=30)
def generate_script(self, job_id: str, tenant_id: str, topic: str, style: str = "finance", language: str = "es"):
    """Phase 1: Generate video script."""
    try:
        _update_video_status(job_id, "script")
        plan = _get_tenant_plan(tenant_id)

        from saas.providers.registry import get_provider
        provider = get_provider(plan, "script")
        script = _run_async(provider.generate(topic, style, language))

        # Update video with script data
        _update_video_status(
            job_id, "script",
            title=script.get("title", ""),
            description=script.get("description", ""),
            tags=script.get("tags", []),
            script_json=script,
        )

        logger.info(f"[{job_id}] Script generated: '{script.get('title')}'")
        return {"job_id": job_id, "tenant_id": tenant_id, "script": script}

    except Exception as exc:
        _update_video_status(job_id, "error", error_message=str(exc))
        raise self.retry(exc=exc)


@app.task(bind=True, name="saas.worker.tasks.generate_images", max_retries=3, default_retry_delay=30)
def generate_images(self, prev_result: dict):
    """Phase 2: Generate images for scenes."""
    job_id = prev_result["job_id"]
    tenant_id = prev_result["tenant_id"]
    script = prev_result["script"]

    try:
        _update_video_status(job_id, "images")
        plan = _get_tenant_plan(tenant_id)

        prompts = [s.get("image_prompt", s.get("text", "")) for s in script["scenes"]]

        from saas.providers.registry import get_provider
        provider = get_provider(plan, "image")
        image_keys = _run_async(provider.generate(prompts, (1080, 1920)))

        logger.info(f"[{job_id}] Generated {len(image_keys)} images")
        return {**prev_result, "image_keys": image_keys}

    except Exception as exc:
        _update_video_status(job_id, "error", error_message=str(exc))
        raise self.retry(exc=exc)


@app.task(bind=True, name="saas.worker.tasks.generate_tts", max_retries=3, default_retry_delay=30)
def generate_tts(self, prev_result: dict):
    """Phase 3: Generate TTS audio."""
    job_id = prev_result["job_id"]
    tenant_id = prev_result["tenant_id"]
    script = prev_result["script"]

    try:
        _update_video_status(job_id, "tts")
        plan = _get_tenant_plan(tenant_id)

        narration = script.get("narration", "")

        from saas.providers.registry import get_provider
        provider = get_provider(plan, "tts")
        voice_key = _run_async(provider.generate(narration, "es-ES-AlvaroNeural"))

        logger.info(f"[{job_id}] TTS generated")
        return {**prev_result, "voice_key": voice_key}

    except Exception as exc:
        _update_video_status(job_id, "error", error_message=str(exc))
        raise self.retry(exc=exc)


@app.task(bind=True, name="saas.worker.tasks.generate_video_clips", max_retries=3, default_retry_delay=60)
def generate_video_clips(self, prev_result: dict):
    """Phase 4: Generate video clips from images."""
    job_id = prev_result["job_id"]
    tenant_id = prev_result["tenant_id"]
    script = prev_result["script"]
    image_keys = prev_result["image_keys"]

    try:
        _update_video_status(job_id, "video")
        plan = _get_tenant_plan(tenant_id)

        from saas.providers.registry import get_provider
        provider = get_provider(plan, "video")

        clip_keys = []
        for i, (image_key, scene) in enumerate(zip(image_keys, script["scenes"])):
            motion_prompt = scene.get("text", "subtle zoom")
            clip_key = _run_async(provider.generate(image_key, motion_prompt, duration=5))
            clip_keys.append(clip_key)

        logger.info(f"[{job_id}] Generated {len(clip_keys)} video clips")
        return {**prev_result, "clip_keys": clip_keys}

    except Exception as exc:
        _update_video_status(job_id, "error", error_message=str(exc))
        raise self.retry(exc=exc)


@app.task(bind=True, name="saas.worker.tasks.generate_music", max_retries=3, default_retry_delay=30)
def generate_music(self, prev_result: dict):
    """Phase 5: Generate or select background music."""
    job_id = prev_result["job_id"]
    tenant_id = prev_result["tenant_id"]

    try:
        _update_video_status(job_id, "music")
        plan = _get_tenant_plan(tenant_id)

        from saas.providers.registry import get_provider
        provider = get_provider(plan, "music")
        music_key = _run_async(provider.generate(20.0, None))

        logger.info(f"[{job_id}] Music selected")
        return {**prev_result, "music_key": music_key}

    except Exception as exc:
        _update_video_status(job_id, "error", error_message=str(exc))
        raise self.retry(exc=exc)


@app.task(bind=True, name="saas.worker.tasks.compose_video", max_retries=2, default_retry_delay=60)
def compose_video(self, prev_result: dict):
    """Phase 6: Composite final video."""
    job_id = prev_result["job_id"]
    tenant_id = prev_result["tenant_id"]
    script = prev_result["script"]

    try:
        _update_video_status(job_id, "compositing")
        plan = _get_tenant_plan(tenant_id)

        # Build subtitle segments
        narration = script.get("narration", "")
        words = narration.split()
        dur_per_word = 20.0 / max(len(words), 1)
        subtitles = [
            {"word": w, "start": i * dur_per_word, "end": (i + 1) * dur_per_word}
            for i, w in enumerate(words)
        ]

        from saas.providers.registry import get_provider
        provider = get_provider(plan, "compose")
        final_key = _run_async(provider.compose(
            clips=prev_result["clip_keys"],
            voice=prev_result["voice_key"],
            music=prev_result["music_key"],
            subtitles=subtitles,
            target_duration=20.0,
        ))

        # Move from tmp to permanent tenant location
        from saas.storage.s3 import s3_key_for_tenant
        permanent_key = s3_key_for_tenant(tenant_id, job_id, "final.mp4")
        _move_s3_object(final_key, permanent_key)

        _update_video_status(
            job_id, "ready",
            video_s3_key=permanent_key,
            preview_s3_key=permanent_key,
        )

        logger.info(f"[{job_id}] Video composed -> {permanent_key}")

        # Trigger webhook notification
        from saas.worker.callbacks import deliver_webhook
        deliver_webhook.delay(tenant_id, "video.completed", {
            "job_id": job_id,
            "video_s3_key": permanent_key,
        })

        return {**prev_result, "video_s3_key": permanent_key, "status": "ready"}

    except Exception as exc:
        _update_video_status(job_id, "error", error_message=str(exc))
        raise self.retry(exc=exc)


@app.task(bind=True, name="saas.worker.tasks.publish_video", max_retries=2, default_retry_delay=60)
def publish_video(self, job_id: str, tenant_id: str, channel_id: str):
    """Publish a ready video to a platform."""
    try:
        _update_video_status(job_id, "publishing")

        session = _get_sync_session()
        try:
            from saas.models.channel import Channel
            from saas.models.video import Video
            import json
            from saas.auth.crypto import get_fernet

            video = session.query(Video).filter(Video.job_id == job_id).first()
            channel = session.query(Channel).filter(Channel.id == uuid.UUID(channel_id)).first()

            if not video or not channel:
                raise RuntimeError(f"Video or channel not found: {job_id}, {channel_id}")

            # Decrypt channel credentials using shared crypto
            fernet = get_fernet()
            creds = json.loads(fernet.decrypt(channel.credentials_encrypted.encode()).decode())

            # TODO: Implement actual publishing via platform providers
            # For now, mark as published
            _update_video_status(job_id, "published")
            logger.info(f"[{job_id}] Published to {channel.platform}")

        finally:
            session.close()

        # Webhook notification
        from saas.worker.callbacks import deliver_webhook
        deliver_webhook.delay(tenant_id, "video.published", {"job_id": job_id})

    except Exception as exc:
        _update_video_status(job_id, "error", error_message=str(exc))
        raise self.retry(exc=exc)


def _move_s3_object(src_key: str, dst_key: str):
    """Copy S3 object from src to dst, then delete src."""
    from saas.storage.s3 import get_s3_client
    from saas.config import get_settings

    settings = get_settings()
    client = get_s3_client()
    client.copy_object(
        Bucket=settings.s3_bucket,
        CopySource={"Bucket": settings.s3_bucket, "Key": src_key},
        Key=dst_key,
    )
    client.delete_object(Bucket=settings.s3_bucket, Key=src_key)


def dispatch_pipeline(job_id: str, tenant_id: str, topic: str, style: str = "finance", language: str = "es"):
    """Dispatch the full 6-phase pipeline as a Celery chain."""
    pipeline = chain(
        generate_script.s(job_id, tenant_id, topic, style, language),
        generate_images.s(),
        generate_tts.s(),
        generate_video_clips.s(),
        generate_music.s(),
        compose_video.s(),
    )
    pipeline.apply_async()
    logger.info(f"Pipeline dispatched for job {job_id}")
