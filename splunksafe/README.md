# SplunkSafe

A virtual Linux filesystem simulator for practicing Splunk administration commands safely.
Nothing here ever touches your real filesystem — the "filesystem" lives entirely in a
SQLite database. Destructive commands (`rm`, `mv`, `chmod`) against critical paths like
`/opt/splunk` are flagged with a risk level and **blocked unless you explicitly force them**.

Tested end-to-end: 9/9 backend tests pass, frontend builds clean with TypeScript + Vite,
and the live API was hit with real HTTP requests before this was packaged.

---

## Option A — Run with Docker (easiest, fewest moving parts)

**Prerequisites:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running.

```bash
cd splunksafe
docker compose up --build
```

Open **http://localhost** in your browser. That's it — both backend and frontend start together.

To stop: `Ctrl+C`, then `docker compose down`
To fully reset the virtual filesystem: `docker compose down -v`

---

## Option B — Run in VS Code without Docker (two terminals)

**Prerequisites:**
- [Python 3.12+](https://www.python.org/downloads/)
- [Node.js 20+](https://nodejs.org/)
- [VS Code](https://code.visualstudio.com/)

### 1. Open the project
```bash
code splunksafe
```

### 2. Terminal 1 — Backend (FastAPI)
Open a terminal in VS Code (`` Ctrl+` ``):

```bash
cd backend
python -m venv .venv

# Activate the virtual environment:
# macOS/Linux:
source .venv/bin/activate
# Windows (PowerShell):
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

You should see `Uvicorn running on http://0.0.0.0:8000`.
Verify it's alive: open **http://localhost:8000/api/health** → should return `{"status":"ok"}`.

### 3. Terminal 2 — Frontend (React + Vite)
Open a **second** terminal (`+` icon in the terminal panel, or `` Ctrl+Shift+` ``):

```bash
cd frontend
npm install
npm run dev
```

You should see something like `Local: http://localhost:5173/`.

### 4. Open the app
Go to **http://localhost:5173** in your browser. The Vite dev server proxies all `/api/*`
calls to your backend on port 8000 automatically (see `frontend/vite.config.ts`), so no
extra configuration is needed.

Both terminals need to **stay running** while you use the app. Stop either with `Ctrl+C`.

---

## VS Code tips

- Install the **Python** and **ESLint** extensions for inline linting.
- Add a `.vscode/launch.json` if you want to debug the FastAPI backend with breakpoints —
  point it at `uvicorn` with `app.main:app --reload --port 8000` as the run args.
- The two-terminal split (`Terminal: Split Terminal`, or drag a new terminal beside the
  first) is the cleanest way to watch backend logs and frontend logs side by side.

---

## Project structure

```
splunksafe/
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py            FastAPI app, CORS, lifespan/seed hook
│   │   ├── database.py        SQLAlchemy engine/session
│   │   ├── models.py          FileNode ORM model
│   │   ├── schemas.py         Pydantic request/response models
│   │   ├── seed.py            Seeds /opt/splunk virtual tree on first boot
│   │   ├── api/routes.py      /api/health, /api/execute, /api/analyze
│   │   ├── commands/
│   │   │   ├── parser.py      Tokenizes raw command strings
│   │   │   ├── risk.py        Scores destructive commands SAFE→CRITICAL
│   │   │   └── executor.py    Dispatches parsed commands to handlers
│   │   └── fs/
│   │       ├── repository.py  DB queries (CRUD on FileNode tree)
│   │       └── service.py     Filesystem semantics (mkdir/cp/mv/rm)
│   └── tests/test_executor.py 9 tests incl. the CRITICAL-block guarantee
└── frontend/
    ├── Dockerfile
    ├── nginx.conf              Production reverse proxy to backend
    ├── package.json
    ├── vite.config.ts          Dev-mode proxy to localhost:8000
    └── src/
        ├── App.tsx
        ├── components/
        │   ├── Terminal.tsx     Main terminal UI, history, quick-commands
        │   └── RiskBadge.tsx    SAFE/LOW/MEDIUM/HIGH/CRITICAL badge
        └── api/client.ts        fetch wrapper for /api/execute, /api/analyze
```

## How the risk system works

Every `rm`, `mv`, or `chmod` against a path is scored before it runs:

| Level | Trigger |
|---|---|
| SAFE | Normal operation, no special conditions |
| LOW | Directory operation missing `-r` |
| MEDIUM | Recursive op affecting 50+ objects |
| HIGH | Recursive op affecting 1000+ objects |
| CRITICAL | Targets a protected path (`/opt/splunk`, `/etc`, `/var`, etc.) |

**CRITICAL is blocked outright** unless the `force` checkbox in the UI (or `force: true` in
the API body) is set. Note: a command's own `-f` flag (e.g. `rm -rf`) does **not** count as
force on its own — only the explicit UI/API force flag can authorize a CRITICAL operation.
This was caught and fixed by the test suite before packaging.

## Running tests

```bash
cd backend
source .venv/bin/activate   # if not already active
pytest -v
```

## Resetting the virtual filesystem

- **Docker:** `docker compose down -v` (deletes the named volume)
- **Local:** delete `backend/splunksafe.db` and restart the backend
