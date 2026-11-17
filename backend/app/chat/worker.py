"""Standalone chat worker entry point. Run with python -m app.chat.worker."""

import asyncio

from app.chat.runtime import run_forever

if __name__ == "__main__":
    asyncio.run(run_forever())
