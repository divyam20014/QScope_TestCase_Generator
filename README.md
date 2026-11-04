# QScope Test Case Generator

A locally-run, database-free QA platform that ingests requirement documents
(BRD/FRD/SRS/specs), extracts and classifies requirements, and generates
traceable, categorized test cases using Google Gemini. All persistent state
lives on your filesystem as JSON (+ FAISS index files) under `local_data/` -
no database to install, no cloud service required except Gemini itself. See
[ARCHITECTURE.md](ARCHITECTURE.md) for how it's built and
[DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) /
[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) for what's done so far.

## Prerequisites

- **Python 3.11+** ([python.org](https://www.python.org/downloads/) - during
  install, check "Add python.exe to PATH")
- **Node.js 20+** ([nodejs.org](https://nodejs.org/)) - includes `npm`
- A **Google Gemini API key** (free tier) from
  [aistudio.google.com/apikey](https://aistudio.google.com/apikey) - optional
  to start: everything through document upload, RAG search, and the test
  case repository works without one; only requirement extraction, test
  generation, and the Gemini quality-review pass need it.

## Windows setup

Open PowerShell (or Command Prompt) in the repository root.

### 1. Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

The first install downloads a local embedding model and ML libraries
(PyTorch, FAISS) and can take several minutes.

### 2. Configure your API key

```powershell
cd ..
copy .env.example .env
notepad .env
```

Fill in `GEMINI_API_KEY=` with your key and save. Never commit `.env` - it's
already in `.gitignore`.

### 3. Frontend

```powershell
cd frontend
npm install
```

### 4. Run it

In one terminal (with the backend venv activated):

```powershell
cd backend
.venv\Scripts\activate
python -m uvicorn app.main:app --reload
```

In a second terminal:

```powershell
cd frontend
npm run dev
```

Open the URL Vite prints (default `http://localhost:5173`) - its dev server
proxies `/api` to the backend on `http://127.0.0.1:8000`, so you only need
the one browser tab. The backend binds to `127.0.0.1` by default
(configurable in `.env`) - this app is not designed to be exposed beyond
your own machine.

## Running the tests

```powershell
cd backend
.venv\Scripts\activate
pytest
```

```powershell
cd frontend
npx tsc -b
npm run lint
npm run build
```

Gemini is mocked in all automated backend tests - they never make a real
network call or require an API key. Only using the app live (extraction,
generation, quality review) needs a real key in `.env`.

## Your data

Everything you create - projects, documents, requirements, test cases,
exports - lives under `local_data/` in the repository root. It's gitignored
and never committed. To back up your work, copy that folder; to reset
everything, delete it (the app recreates the structure it needs on next
start).

## Project structure

```
backend/    FastAPI app (app/ai, app/rag, app/requirements, app/generator,
            app/coverage, app/validators, app/exporters, ...)
frontend/   React + TypeScript + Vite SPA
local_data/ Your projects' data (gitignored, created on first run)
```
