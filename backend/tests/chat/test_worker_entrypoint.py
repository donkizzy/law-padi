"""Exercise OS signals against the standalone entry point in a real process."""

import os
import signal
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("stop_signal", [signal.SIGTERM, signal.SIGINT])
def test_worker_signal_drains_active_work(tmp_path: Path, stop_signal: int) -> None:
    marker = tmp_path / "drained"
    script = """
import asyncio
import runpy
import sys
from pathlib import Path
from uuid import uuid4
from app.chat import runs
from app.core.config import settings

settings.CHAT_GENERATION_ENABLED = True
settings.CHAT_GENERATION_KILL_SWITCH = False
pending = [uuid4()]
runs.claim_run = lambda worker_id: pending.pop() if pending else None
runs.recover_expired = lambda: None
runs.expire_guest_conversations = lambda: None

async def execute(*args, **kwargs):
    print("running", flush=True)
    try:
        await asyncio.Event().wait()
    finally:
        Path(sys.argv[1]).write_text("drained")

runs.execute = execute
runpy.run_module("app.chat.worker", run_name="__main__")
"""
    process = subprocess.Popen(
        [sys.executable, "-u", "-c", script, str(marker)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "SENTRY_DSN": ""},
    )
    try:
        assert process.stdout is not None
        assert process.stdout.readline().strip() == "running"
        process.send_signal(stop_signal)
        stdout, stderr = process.communicate(timeout=15)
        assert process.returncode == 0, (stdout, stderr)
        assert marker.read_text() == "drained"
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()
