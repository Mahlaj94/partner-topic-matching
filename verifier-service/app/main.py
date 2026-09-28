import os, json
import re
from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any
import httpx

from shared_contracts import Topic
MODEL = "llama3"


app = FastAPI(title="LLM Verifier", version="0.1.0")

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "ollama")
LLM_MODEL = os.environ.get("LLM_MODEL", "llama3.1")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", None)
OLLAMA_ENDPOINT = os.environ.get("OLLAMA_ENDPOINT", "http://localhost:11434")

class Snippet(BaseModel):
    text: str
    url: str
    title: Optional[str] = None

class VerifyRequest(BaseModel):
    partner_id: str
    topic: Topic
    snippets: List[Snippet]

class EvidenceItem(BaseModel):
    quote: str
    url: str

class VerifyResponse(BaseModel):
    label: Literal["Yes","Weak","No"]
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    evidence: List[EvidenceItem]

SYS_PROMPT = """Assess whether the snippets show that the partner works on the topic.
Return one JSON object with: label (Yes, Weak, or No), confidence (0 to 1),
rationale (at most 80 words), and evidence (up to three quote and url objects).
Yes means direct evidence; Weak means indirect or ambiguous evidence; No means no
supporting evidence. Use only the snippets. Copy evidence quotes exactly from
the snippet associated with each URL. For No, return empty evidence.
Output JSON only."""
timeout = httpx.Timeout(connect=30.0, read=600.0, write=30.0, pool=30.0)

def build_user_prompt(
    partner_id: str,
    topic: Topic,
    snippets: List[Snippet],
    sc_inputs: List[str],
    sc_outputs: List[str],
) -> str:
    lines = []

    lines.append(f"SUPPLY CHAIN: {topic.name}")

    if topic.definition:
        lines.append(f"Description: {topic.definition}")

    if sc_inputs:
        lines.append("SUPPLY CHAIN INPUTS:")
        for i in sc_inputs:
            lines.append(f"- {i}")

    if sc_outputs:
        lines.append("SUPPLY CHAIN OUTPUTS:")
        for o in sc_outputs:
            lines.append(f"- {o}")

    lines.append("PARTNER: " + partner_id)
    lines.append("SNIPPETS:")

    for i, s in enumerate(snippets, 1):
        text = s.text.replace("\n", " ").strip()
        lines.append(f"[{i}] URL: {s.url}")
        lines.append(f"Text: {text}")

    lines.append("Respond with a single JSON object only.")
    return "\n".join(lines)


async def call_openai(prompt: str) -> str:
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYS_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "response_format": {"type": "json_object"},
    }
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]

async def call_ollama(prompt: str) -> str:
    url = f"{OLLAMA_ENDPOINT}/api/chat"
    #print("DEBUG OLLAMA_ENDPOINT =", OLLAMA_ENDPOINT)
    print("DEBUG url =", url)
    print("DEBUG LLM_MODEL =", LLM_MODEL)
    async with httpx.AsyncClient(timeout=timeout) as client:
        
        r = await client.post(
            f"{OLLAMA_ENDPOINT}/api/chat",
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": SYS_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "format": "json",
                "options": {"temperature": 0},
            },
        )
        r.raise_for_status()
        data = r.json()
        return data["message"]["content"]



def coerce_json(text: str) -> dict:
    """
    Robustly extract the first JSON object from LLM output.
    """
    if not text:
        raise ValueError("Empty model output.")

    # Remove code fences if present
    text = re.sub(r"^```(?:json)?", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"```$", "", text.strip())

    # Try direct parse
    try:
        return json.loads(text)
    except Exception:
        pass

    # Extract first {...} block
    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:
        candidate = text[start:end+1]
        try:
            return json.loads(candidate)
        except Exception:
            pass

    raise ValueError(f"Model did not return valid JSON.\nRaw output:\n{text}")


@app.post("/verify", response_model=VerifyResponse)
async def verify(req: VerifyRequest):
    topic = req.topic

    topic_data = topic.model_dump()
    sc_inputs = topic_data.get("inputs", [])
    sc_outputs = topic_data.get("outputs", [])

    prompt = build_user_prompt(
        req.partner_id,
        topic,
        req.snippets,
        sc_inputs,
        sc_outputs,
    )



    if LLM_PROVIDER == "openai":
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY not set")
        raw = await call_openai(prompt)
    else:
        raw = await call_ollama(prompt)

    data = coerce_json(raw)

    label = str(data.get("label", "No")).strip().title()
    if label not in {"Yes", "Weak", "No"}:
        label = "No"

    conf = float(data.get("confidence", 0.5))
    conf = min(1.0, max(0.0, conf))
    rationale = str(data.get("rationale","")).strip()[:400]

    #label = str(data.get("label","")).strip().title()
    #if label not in {"Yes","Weak","No"}:
    #    label = "Weak"
    #conf = float(data.get("confidence", 0.5))
    #conf = min(1.0, max(0.0, conf))
    #rationale = str(data.get("rationale","")).strip()[:400]
    evs = data.get("evidence", []) or []
    evidence = []
    snippet_by_url = {s.url: s.text for s in req.snippets}
    for e in evs[:3]:
        q = str(e.get("quote","")).strip()
        u = str(e.get("url","")).strip()
        if q and u in snippet_by_url and q in snippet_by_url[u]:
            evidence.append({"quote": q, "url": u})
    return VerifyResponse(
    label=label,
    confidence=conf,
    rationale=rationale,
    evidence=evidence
    )

    #return VerifyResponse(label=label, confidence=conf, rationale=rationale, evidence=evidence)
