"""DubGuard API: text verification plus authenticated audio/review workflow."""

from typing import Literal
import asyncio
from contextlib import asynccontextmanager
from starlette.concurrency import run_in_threadpool
from fastapi import Header
from .review import reviewer
from .quick import router as quick_router, cleanup, recover_interrupted

from fastapi import FastAPI, Query
from fastapi.responses import PlainTextResponse

from .engine import verify
from .evaluation import evaluate, markdown_report
from .schemas import ReviewResult, ScriptPolicy, VerificationRequest
from .review import router as review_router

@asynccontextmanager
async def lifespan(app):
    await run_in_threadpool(recover_interrupted)
    async def sweep():
        while True:
            await run_in_threadpool(cleanup)
            await asyncio.sleep(60)
    task = asyncio.create_task(sweep())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(lifespan=lifespan, title="DubGuard — Industrial Narration Review", version="0.5.0",
              description="English single-speaker text review. PASS_CANDIDATE is not safety certification or release approval.")
app.include_router(review_router)
app.include_router(quick_router)


@app.middleware("http")
async def private_responses(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.get("/health")
def health():
    return {"status": "ok", "asr_integrated": True, "amd_inference_integrated": True,
            "note": "ASR requires optional local audio dependencies and a Whisper model."}


@app.post("/validate")
def validate_policy(payload: ScriptPolicy):
    return {"valid": True, "script_id": payload.script.id, "policy_id": payload.policy.id,
            "notice": "Structural/policy validation only; reviewer identity and industrial correctness are not authenticated."}


@app.post("/verify", response_model=ReviewResult)
def verify_transcript(payload: VerificationRequest, mode: Literal["deterministic", "hybrid"] = "deterministic", authorization: str | None = Header(default=None)):
    if mode == "hybrid":
        reviewer(authorization)
    return verify(payload, hybrid=mode == "hybrid")


@app.get("/evaluation/reports")
def evaluation_reports(format: Literal["json", "markdown"] = Query("json")):
    # Read-only local report. Never initiate remote calls from a GET endpoint.
    report = evaluate()
    return PlainTextResponse(markdown_report(report), media_type="text/markdown") if format == "markdown" else report
