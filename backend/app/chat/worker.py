"""Standalone chat worker entry point. Run with python -m app.chat.worker."""

import asyncio
import signal

from app.chat.runtime import run_forever


async def serve() -> None:
    loop = asyncio.get_running_loop()
    task = asyncio.current_task()
    assert task is not None
    # Cancellation drains active runs through run_worker and the pipeline's
    # existing handback/settlement paths, just as the asyncio SIGINT handler does.
    loop.add_signal_handler(signal.SIGTERM, task.cancel)
    try:
        await run_forever()
    finally:
        loop.remove_signal_handler(signal.SIGTERM)


def main() -> None:
    try:
        asyncio.run(serve())
    except asyncio.CancelledError, KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
