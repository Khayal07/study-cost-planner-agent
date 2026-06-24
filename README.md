# Study Cost Planning Agent

A multi-agent system that helps students decide **where to study abroad** based on the
**total real cost** — tuition **plus** living, insurance, visa, transport and hidden costs —
not tuition alone. Every figure is **grounded in a cited source** (no invented numbers).

Two ways in:
1. **Structured budget form** — enter budget, country/field preferences, lifestyle.
2. **Chat** — natural language ("I want to study CS in Germany, my budget is €8000/year").

Both paths run the **same grounded agent pipeline** and produce the same cited results.

> AI Engineering course capstone. Design principle: **LLM for language, Python for math.**
> All cost/currency/budget calculations are deterministic Python; the LLM only handles
> intent extraction, scenario narration and verification summaries.

## Architecture

```
Form / Chat → Intake → Candidate Retrieval (SQL + pgvector)
   → Tuition + Living Cost (DB, cited)
   → Currency (normalize + FX risk)
   → Scenario (frugal / moderate / comfortable)
   → Budget Matching (rank, compute gap)
   → Verifier (source + calculation checks)
   → Output (UI JSON + PDF)
```

Six agents coordinate through a deterministic orchestrator over a typed shared
`PlanningContext`. See `app/agents/` and the plan in `.claude/plans/`.

## Tech stack

| Layer | Choice |
|-------|--------|
| Frontend | Next.js (App Router) + TypeScript + Tailwind + Recharts |
| Backend | FastAPI + Pydantic v2 |
| Database | PostgreSQL 16 + pgvector |
| LLM | OpenRouter (OpenAI-compatible), free models |
| Embeddings | fastembed (ONNX, local) |
| Currency | frankfurter.app (ECB), cached |
| PDF | WeasyPrint + Matplotlib |

## Quick start (Docker)

```bash
cp .env.example .env
# edit .env → set OPENROUTER_API_KEY (free key from https://openrouter.ai/keys)
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API + docs: http://localhost:8000/docs
- The backend runs migrations and seeds curated data on boot (idempotent).

## Local development (without Docker)

Backend:
```bash
cd backend
python -m venv .venv && source .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# point DATABASE_URL at a local Postgres with the vector extension, then:
python -m app.cli migrate && python -m app.cli seed
uvicorn app.main:app --reload
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

## Roadmap (phases)

0. Scaffold (this commit) — docker-compose, FastAPI + Next skeleton, `/health`.
1. Data layer — schema, pgvector, curated seed with source URLs.
2. Core agents + orchestrator — tuition, living, currency; form path.
3. Scenario + budget matching + verifier.
4. Chat + RAG grounded answers.
5. Outputs — comparison charts + PDF export.
6. Polish — tests, docs, Docker finishing.

## License

Course project — for educational use.
