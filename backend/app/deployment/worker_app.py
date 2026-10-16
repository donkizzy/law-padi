"""Private Cloud Run HTTP worker, invoked by an IAM-authenticated task.

Deploy this app as a separate service with Cloud Run's invoker IAM check enabled.
The public API/Cloudflare proxy must never route requests to this service. Header
names supplied by a client do not establish service identity.
"""

import asyncio
import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlmodel import Session

from app.chat import worker
from app.chat.schemas import ExplanationAnswer
from app.core.config import settings
from app.core.db import engine
from app.deployment.chat_dispatch import reconcile_dispatches
from app.legal.models import GenerationRun

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


class RunTask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: uuid.UUID


class TaskResult(BaseModel):
    status: str


def _status(run_id: uuid.UUID) -> str:
    with Session(engine) as session:
        run = session.get(GenerationRun, run_id)
        return run.status if run else "deleted"


@app.post("/internal/chat/run")
async def run_chat(body: RunTask) -> TaskResult:
    # Recover with the existing uncertainty policy before claiming. In
    # particular, an expired post-provider lease is finished, never regenerated.
    await asyncio.to_thread(worker.recover_expired)
    current = await asyncio.to_thread(_status, body.run_id)
    if current not in ("pending", "running"):
        return TaskResult(status=current)
    identity = f"task-{uuid.uuid4()}"
    claimed = await asyncio.to_thread(worker._claim_run, identity, run_id=body.run_id)
    if claimed is None:
        current = await asyncio.to_thread(_status, body.run_id)
        if current not in ("pending", "running"):
            return TaskResult(status=current)
        # An active lease or concurrent lock must remain retryable. A successful
        # response would discard the delivery while its owning process may die.
        raise HTTPException(status_code=503, detail="Generation lease is active")
    if (
        not settings.CHAT_ENABLED
        or not settings.CHAT_GENERATION_ENABLED
        or settings.CHAT_GENERATION_KILL_SWITCH
    ):
        await asyncio.to_thread(
            worker._finish,
            claimed,
            identity,
            ExplanationAnswer(outcome="cancelled", notice=worker._NOTICE["disabled"]),
        )
    else:
        # Await completion inside the billed request. No detached task survives
        # acknowledgement or relies on CPU while Cloud Run is idle.
        await worker.process_run(claimed, identity)
    current = await asyncio.to_thread(_status, body.run_id)
    if current in ("pending", "running"):
        raise HTTPException(status_code=503, detail="Generation did not finish")
    return TaskResult(status=current)


@app.post("/internal/reconcile")
async def reconcile() -> dict[str, int]:
    return {"published": await asyncio.to_thread(reconcile_dispatches)}


@app.post("/internal/backup")
async def backup() -> dict[str, str | int]:
    from app.cloud_backup import run_backup

    return await asyncio.to_thread(run_backup)
