"""Heartbeat files that let a container health check see a worker loop progress.

A worker touches its file on every loop iteration, idle polls included. The
check command fails when the file is missing or older than a number of poll
intervals, which catches a loop that hangs while the process stays up:

    python -m app.core.heartbeat /tmp/worker.heartbeat --interval 5 --intervals 12
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

_logger = logging.getLogger(__name__)


class Heartbeat:
    """Touch a file; a missing path makes every beat a no-op."""

    def __init__(self, path: str | os.PathLike[str] | None) -> None:
        self.path = Path(path) if path else None
        self._warned = False

    def beat(self) -> None:
        if self.path is None:
            return
        try:
            self.path.touch()
        except OSError as exc:
            # A health check will report the stale file; the work goes on.
            if not self._warned:
                _logger.warning(
                    "heartbeat_write_failed",
                    extra={"path": str(self.path), "error_type": type(exc).__name__},
                )
                self._warned = True


def heartbeat_age(path: Path, *, now: float | None = None) -> float | None:
    """Seconds since the last beat, or None when the file does not exist."""
    try:
        modified = path.stat().st_mtime
    except FileNotFoundError:
        return None
    return max(0.0, (time.time() if now is None else now) - modified)


def stale_after(interval: float, intervals: float) -> float:
    # A loop configured not to sleep still takes time per poll; a one-second
    # floor keeps a zero interval from marking every check stale.
    return max(interval, 1.0) * intervals


def is_fresh(
    path: Path, *, interval: float, intervals: float, now: float | None = None
) -> bool:
    age = heartbeat_age(path, now=now)
    return age is not None and age <= stale_after(interval, intervals)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument(
        "--interval", type=float, required=True, help="worker poll interval, seconds"
    )
    parser.add_argument(
        "--intervals",
        type=float,
        default=12,
        help="poll intervals without a beat before the worker counts as stale",
    )
    args = parser.parse_args(argv)
    if args.interval < 0 or args.intervals <= 0:
        parser.error("--interval cannot be negative and --intervals must be positive")
    age = heartbeat_age(args.path)
    if age is None:
        sys.stderr.write(f"no heartbeat at {args.path}\n")
        return 1
    if age > stale_after(args.interval, args.intervals):
        sys.stderr.write(f"heartbeat is {age:.0f}s old\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
