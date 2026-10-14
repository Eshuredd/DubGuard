"""CPU-local API; no upload, transcription, release, or approval endpoints."""

from typing import Literal

from fastapi import FastAPI, Query
from fastapi.responses import PlainTextResponse

from .engine import verify
from .evaluation import evaluate, markdown_report
from .schemas import ReviewResult, ScriptPolicy, VerificationRequest

app = FastAPI(title="DubGuard — Industrial Narration Review", version="0.1.0",
              description="English single-speaker text review. PASS_CANDIDATE is not safety certification or release approval.")


@app.get("/health")
def health():
    return {"status": "ok", "asr_integrated": False, "amd_inference_integrated": False}


@app.post("/validate")
def validate_policy(payload: ScriptPolicy):
    return {"valid": True, "script_id": payload.script.id, "policy_id": payload.policy.id,
            "notice": "Structural/policy validation only; reviewer identity and industrial correctness are not authenticated."}


@app.post("/verify", response_model=ReviewResult)
def verify_transcript(payload: VerificationRequest, mode: Literal["deterministic", "hybrid"] = "deterministic"):
    return verify(payload, hybrid=mode == "hybrid")


@app.get("/evaluation/reports")
def evaluation_reports(format: Literal["json", "markdown"] = Query("json")):
    # Read-only local report. Never initiate remote calls from a GET endpoint.
    report = evaluate()
    return PlainTextResponse(markdown_report(report), media_type="text/markdown") if format == "markdown" else report
