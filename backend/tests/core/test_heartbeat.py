import logging
import os
import time
from pathlib import Path

import pytest

from app.core.heartbeat import Heartbeat, heartbeat_age, is_fresh, main


def _aged(path: Path, seconds: float) -> None:
    path.touch()
    then = time.time() - seconds
    os.utime(path, (then, then))


def test_a_beat_creates_and_refreshes_the_file(tmp_path: Path) -> None:
    path = tmp_path / "worker.heartbeat"
    heartbeat = Heartbeat(path)
    heartbeat.beat()
    assert path.exists()
    _aged(path, 100)
    heartbeat.beat()
    age = heartbeat_age(path)
    assert age is not None and age < 5


def test_without_a_path_beats_do_nothing(tmp_path: Path) -> None:
    Heartbeat(None).beat()
    assert list(tmp_path.iterdir()) == []


def test_a_failed_write_warns_once(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    heartbeat = Heartbeat(tmp_path / "missing" / "worker.heartbeat")
    with caplog.at_level(logging.WARNING, logger="app.core.heartbeat"):
        heartbeat.beat()
        heartbeat.beat()
    assert [r.getMessage() for r in caplog.records] == ["heartbeat_write_failed"]


def test_staleness_is_measured_in_poll_intervals(tmp_path: Path) -> None:
    path = tmp_path / "worker.heartbeat"
    assert not is_fresh(path, interval=5, intervals=12)
    _aged(path, 59)
    assert is_fresh(path, interval=5, intervals=12)
    _aged(path, 61)
    assert not is_fresh(path, interval=5, intervals=12)
    # A zero poll interval counts as one second per interval.
    _aged(path, 10)
    assert is_fresh(path, interval=0, intervals=12)
    assert not is_fresh(path, interval=0, intervals=5)


def test_the_check_command_exit_codes(tmp_path: Path) -> None:
    path = tmp_path / "worker.heartbeat"
    args = [str(path), "--interval", "2", "--intervals", "30"]
    assert main(args) == 1
    _aged(path, 30)
    assert main(args) == 0
    _aged(path, 61)
    assert main(args) == 1
    with pytest.raises(SystemExit):
        main([str(path), "--interval", "-1"])
