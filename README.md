# Mashnu Content Engine (phase 1)

Founder note -> LangGraph (insight, draft, critique, retry) -> drafts DB -> Telegram approval.

```
pip install -r requirements.txt
cp .env.example .env        # add ANTHROPIC_API_KEY (runs on a stub LLM without it)
uvicorn app.main:app --reload
pytest
```

Endpoints (header `x-api-key`):
- POST /content/generate        {note, platforms}
- POST /content/sync-notion     call from n8n/cron daily
- GET  /content/drafts?status=pending
- POST /content/drafts/{id}/approve|reject

Before first real run: put 10-15 of your best posts into `app/agents/content/prompts/voice.md`.
