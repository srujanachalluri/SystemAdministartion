"""app.py — the Verse Helper API. A small FastAPI service that sits in front of a
local LLM (Ollama) and answers Bible-passage questions over the OpenAI-compatible API.

The point: the SAME code works with any OpenAI-compatible backend (Ollama, vLLM,
llama.cpp, NIM). To switch backends you change only the OLLAMA_URL value — nothing else.

Run locally:  uvicorn app:app --reload
In the stack:  docker compose up -d   (see compose.yaml)
"""
import os
import json
import urllib.request

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Verse Helper", version="1.0")

# Backend URL and model name come from the environment at RUNTIME (set in compose.yaml),
# never hard-coded into the image. Inside the compose network this is http://ollama:11434.
BACKEND = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
MODEL = os.environ.get("MODEL", "llama3.2:3b")


class Ask(BaseModel):
    reference: str = Field(..., min_length=1, max_length=80)
    question: str = Field(..., min_length=1, max_length=500)


@app.get("/health")
def health():
    """Liveness endpoint. The Dockerfile HEALTHCHECK and smoke test both hit this."""
    return {"status": "ok", "backend": BACKEND, "model": MODEL}


@app.post("/explain")
def explain(body: Ask):
    """Forward the question to the local model using the OpenAI-compatible API."""
    payload = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You explain Bible passages plainly. Quote only the ESV."},
            {"role": "user", "content": f"{body.reference}: {body.question}"},
        ],
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        f"{BACKEND}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": "Bearer not-needed"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
    except Exception as exc:  # surface backend failures clearly as a 502
        raise HTTPException(status_code=502, detail=f"backend unreachable: {exc}")
    # "verified": false is deliberate — the model is confident but can be wrong.
    # A human still owns whether the answer is trustworthy.
    return {"answer": data["choices"][0]["message"]["content"], "verified": False}
