# verifier-service

FastAPI microservice that verifies (partner, topic) relevance using an LLM with strict JSON output.
Supports OpenAI or Ollama backends.

## Install
```powershell
cd verifier-service
pip install -r requirements.txt
cd ..\shared-contracts
pip install -e .
cd ..\verifier-service
```

## Run

Use one provider configuration below, then start the service. The OpenAI option requires your own key; never commit it.
```powershell
# OpenAI
$env:LLM_PROVIDER = "openai"
$env:OPENAI_API_KEY = "<your key>"
$env:LLM_MODEL = "gpt-4o-mini"

# or Ollama
$env:LLM_PROVIDER = "ollama"
$env:OLLAMA_ENDPOINT = "http://localhost:11434"
$env:LLM_MODEL = "llama3.2:1b"

uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```
