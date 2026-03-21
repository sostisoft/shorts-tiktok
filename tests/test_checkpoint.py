"""
Tests for scheduler/checkpoint.py — pure Python, no GPU required.
Covers: create, save, load, phase tracking, resume logic.
"""
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

# Patch JOBS_DIR before importing the module so tests use a temp directory
import scheduler.checkpoint as cp_module
from scheduler.checkpoint import JobCheckpoint, PHASE_NAMES


class TestJobCheckpointCreate:
    """Tests for creating new checkpoints."""

    def test_create_checkpoint(self, tmp_dir, sample_script):
        """Creating a checkpoint should write checkpoint.json to disk."""
        with patch.object(cp_module, "JOBS_DIR", tmp_dir):
            cp = JobCheckpoint.create("abc123", "Test Title", sample_script)

        assert cp.job_id == "abc123"
        assert cp.data["title"] == "Test Title"
        assert cp.data["status"] == "running"
        assert cp.data["script"] == sample_script
        assert cp.data["phases"] == {}
        assert (cp.job_dir / "checkpoint.json").exists()

    def test_create_writes_valid_json(self, tmp_dir, sample_script):
        """The checkpoint file on disk should be valid JSON."""
        with patch.object(cp_module, "JOBS_DIR", tmp_dir):
            cp = JobCheckpoint.create("abc123", "Test Title", sample_script)

        with open(cp.job_dir / "checkpoint.json") as f:
            data = json.load(f)

        assert data["job_id"] == "abc123"
        assert data["title"] == "Test Title"

    def test_create_makes_job_directory(self, tmp_dir, sample_script):
        """Creating a checkpoint should create the job directory."""
        with patch.object(cp_module, "JOBS_DIR", tmp_dir):
            cp = JobCheckpoint.create("newjob", "New Job", sample_script)

        assert cp.job_dir.is_dir()
        assert cp.job_dir.name == "newjob"


class TestJobCheckpointLoad:
    """Tests for loading checkpoints from disk."""

    def test_load_existing(self, tmp_dir, sample_script):
        """Loading an existing checkpoint should restore all data."""
        with patch.object(cp_module, "JOBS_DIR", tmp_dir):
            original = JobCheckpoint.create("load01", "Load Test", sample_script)
            original.complete_phase(1, "script.json", 2.5)

            loaded = JobCheckpoint.load("load01")

        assert loaded.job_id == "load01"
        assert loaded.data["title"] == "Load Test"
        assert loaded.is_phase_done(1)

    def test_load_nonexistent_raises(self, tmp_dir):
        """Loading a non-existent checkpoint should raise FileNotFoundError."""
        with patch.object(cp_module, "JOBS_DIR", tmp_dir):
            with pytest.raises(FileNotFoundError):
                JobCheckpoint.load("doesnotexist")

    def test_load_latest_incomplete_returns_none_when_empty(self, tmp_dir):
        """When no jobs exist, load_latest_incomplete should return None."""
        with patch.object(cp_module, "JOBS_DIR", tmp_dir):
            result = JobCheckpoint.load_latest_incomplete()

        assert result is None

    def test_load_latest_incomplete_finds_failed_job(self, tmp_dir, sample_script):
        """load_latest_incomplete should find a failed job."""
        with patch.object(cp_module, "JOBS_DIR", tmp_dir):
            cp = JobCheckpoint.create("fail01", "Failed Job", sample_script)
            cp.complete_phase(1, "script.json", 1.0)
            cp.fail_phase(2, "GPU out of memory")

            result = JobCheckpoint.load_latest_incomplete()

        assert result is not None
        assert result.job_id == "fail01"
        assert result.data["status"] == "failed"

    def test_load_latest_incomplete_skips_done_jobs(self, tmp_dir, sample_script):
        """load_latest_incomplete should skip completed jobs."""
        with patch.object(cp_module, "JOBS_DIR", tmp_dir):
            cp = JobCheckpoint.create("done01", "Done Job", sample_script)
            # Mark all 6 phases as done
            for i in range(1, 7):
                cp.complete_phase(i, f"output_{i}", 1.0)

            result = JobCheckpoint.load_latest_incomplete()

        assert result is None

    def test_load_latest_incomplete_picks_most_recent(self, tmp_dir, sample_script):
        """When multiple incomplete jobs exist, pick the most recently updated."""
        with patch.object(cp_module, "JOBS_DIR", tmp_dir):
            cp1 = JobCheckpoint.create("old01", "Old Failed", sample_script)
            cp1.fail_phase(1, "error1")

            cp2 = JobCheckpoint.create("new01", "New Failed", sample_script)
            cp2.complete_phase(1, "script.json", 1.0)
            cp2.fail_phase(2, "error2")

            result = JobCheckpoint.load_latest_incomplete()

        assert result is not None
        assert result.job_id == "new01"


class TestPhaseTracking:
    """Tests for phase start/complete/fail/query methods."""

    def test_start_phase(self, tmp_dir, sample_script):
        """Starting a phase should mark it as running."""
        with patch.object(cp_module, "JOBS_DIR", tmp_dir):
            cp = JobCheckpoint.create("ph01", "Phase Test", sample_script)
            cp.start_phase(1)

        assert cp.data["phases"]["1"]["status"] == "running"
        assert cp.data["phases"]["1"]["name"] == "script"
        assert not cp.is_phase_done(1)

    def test_complete_phase(self, tmp_dir, sample_script):
        """Completing a phase should mark it as done with output and duration."""
        with patch.object(cp_module, "JOBS_DIR", tmp_dir):
            cp = JobCheckpoint.create("ph02", "Phase Test", sample_script)
            cp.start_phase(1)
            cp.complete_phase(1, "script.json", 3.7)

        assert cp.is_phase_done(1)
        assert cp.get_phase_output(1) == "script.json"
        phase = cp.data["phases"]["1"]
        assert phase["duration_seconds"] == 3.7
        assert "completed_at" in phase

    def test_fail_phase(self, tmp_dir, sample_script):
        """Failing a phase should mark both the phase and job as failed."""
        with patch.object(cp_module, "JOBS_DIR", tmp_dir):
            cp = JobCheckpoint.create("ph03", "Phase Test", sample_script)
            cp.start_phase(2)
            cp.fail_phase(2, "CUDA out of memory")

        assert cp.data["phases"]["2"]["status"] == "failed"
        assert cp.data["phases"]["2"]["error"] == "CUDA out of memory"
        assert cp.data["status"] == "failed"
        assert cp.data["failed_phase"] == 2

    def test_fail_phase_truncates_long_errors(self, tmp_dir, sample_script):
        """Error messages longer than 500 chars should be truncated."""
        with patch.object(cp_module, "JOBS_DIR", tmp_dir):
            cp = JobCheckpoint.create("ph04", "Phase Test", sample_script)
            long_error = "x" * 1000
            cp.fail_phase(1, long_error)

        assert len(cp.data["phases"]["1"]["error"]) == 500

    def test_is_phase_done_false_for_unstarted(self, tmp_dir, sample_script):
        """is_phase_done should return False for phases that haven't started."""
        with patch.object(cp_module, "JOBS_DIR", tmp_dir):
            cp = JobCheckpoint.create("ph05", "Phase Test", sample_script)

        assert not cp.is_phase_done(1)
        assert not cp.is_phase_done(6)

    def test_get_phase_output_none_for_incomplete(self, tmp_dir, sample_script):
        """get_phase_output should return None for incomplete phases."""
        with patch.object(cp_module, "JOBS_DIR", tmp_dir):
            cp = JobCheckpoint.create("ph06", "Phase Test", sample_script)
            cp.start_phase(1)

        assert cp.get_phase_output(1) is None

    def test_next_phase(self, tmp_dir, sample_script):
        """next_phase should return the first incomplete phase number."""
        with patch.object(cp_module, "JOBS_DIR", tmp_dir):
            cp = JobCheckpoint.create("ph07", "Phase Test", sample_script)

        assert cp.next_phase() == 1

        with patch.object(cp_module, "JOBS_DIR", tmp_dir):
            cp.complete_phase(1, "s.json", 1.0)
        assert cp.next_phase() == 2

        with patch.object(cp_module, "JOBS_DIR", tmp_dir):
            cp.complete_phase(2, "images", 2.0)
            cp.complete_phase(3, "voice.wav", 1.0)
        assert cp.next_phase() == 4

    def test_all_phases_done_marks_job_done(self, tmp_dir, sample_script):
        """Completing all 6 phases should set job status to done."""
        with patch.object(cp_module, "JOBS_DIR", tmp_dir):
            cp = JobCheckpoint.create("ph08", "Phase Test", sample_script)
            for i in range(1, 7):
                cp.complete_phase(i, f"out_{i}", 1.0)

        assert cp.data["status"] == "done"
        assert cp.next_phase() == 7


class TestAtomicSave:
    """Tests for the atomic save mechanism."""

    def test_save_creates_no_tmp_file(self, tmp_dir, sample_script):
        """After save, there should be no .tmp file left behind."""
        with patch.object(cp_module, "JOBS_DIR", tmp_dir):
            cp = JobCheckpoint.create("sv01", "Save Test", sample_script)

        tmp_file = cp.job_dir / "checkpoint.json.tmp"
        assert not tmp_file.exists()
        assert (cp.job_dir / "checkpoint.json").exists()

    def test_save_persists_changes(self, tmp_dir, sample_script):
        """Changes saved to disk should survive a reload."""
        with patch.object(cp_module, "JOBS_DIR", tmp_dir):
            cp = JobCheckpoint.create("sv02", "Save Test", sample_script)
            cp.data["custom_field"] = "custom_value"
            cp.save()

            loaded = JobCheckpoint.load("sv02")

        assert loaded.data["custom_field"] == "custom_value"


class TestListAll:
    """Tests for listing all jobs."""

    def test_list_all_empty(self, tmp_dir):
        """list_all should return empty list when no jobs exist."""
        with patch.object(cp_module, "JOBS_DIR", tmp_dir):
            result = JobCheckpoint.list_all()

        assert result == []

    def test_list_all_returns_summaries(self, tmp_dir, sample_script):
        """list_all should return job summaries without full script data."""
        with patch.object(cp_module, "JOBS_DIR", tmp_dir):
            JobCheckpoint.create("ls01", "Job 1", sample_script)
            JobCheckpoint.create("ls02", "Job 2", sample_script)

            result = JobCheckpoint.list_all()

        assert len(result) == 2
        job_ids = {j["job_id"] for j in result}
        assert "ls01" in job_ids
        assert "ls02" in job_ids
        # Should not contain full script
        for j in result:
            assert "script" not in j

    def test_list_all_handles_corrupt_checkpoint(self, tmp_dir, sample_script):
        """list_all should skip corrupt checkpoint files gracefully."""
        with patch.object(cp_module, "JOBS_DIR", tmp_dir):
            JobCheckpoint.create("good01", "Good Job", sample_script)

            # Create a corrupt checkpoint
            bad_dir = tmp_dir / "bad01"
            bad_dir.mkdir()
            (bad_dir / "checkpoint.json").write_text("not valid json {{{")

            result = JobCheckpoint.list_all()

        assert len(result) == 1
        assert result[0]["job_id"] == "good01"


class TestDelete:
    """Tests for deleting job checkpoints."""

    def test_delete_removes_directory(self, tmp_dir, sample_script):
        """delete() should remove the entire job directory."""
        with patch.object(cp_module, "JOBS_DIR", tmp_dir):
            cp = JobCheckpoint.create("del01", "Delete Test", sample_script)
            job_dir = cp.job_dir
            assert job_dir.exists()

            cp.delete()

        assert not job_dir.exists()
