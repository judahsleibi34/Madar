# Setup

## Prerequisites

- Docker and Docker Compose
- Node.js for frontend-only development
- Python for backend-only development

## Environment

Create the root `.env` file with the runtime values used by Docker Compose.
Keep `.env` local; it is ignored by Git.

Required values include:

```sh
FRONTEND_URLS=https://your-frontend-origin.example
VITE_API_URL=https://your-backend-origin.example
COOKIE_SECURE=true
COOKIE_SAMESITE=none
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_KEY=...
TRUSTED_PROXY_IPS=127.0.0.1,::1
```

`TRUSTED_PROXY_IPS` is a comma-separated list of reverse proxy or tunnel IPs/CIDR
ranges whose `X-Forwarded-For` and `X-Real-IP` headers may be trusted for rate
limits. In production, configure only the real proxy/tunnel peers and block
direct backend access with firewall or proxy rules.

## Full Stack

```sh
docker compose up -d --build
```

The backend runs from `backend/` and installs Python dependencies from
`backend/requirements.txt`. The frontend runs from `frontend/` and installs
dependencies from `frontend/package.json` and `frontend/package-lock.json`.

## Backend Only

```sh
cd backend
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn app:app --reload
```

On Windows PowerShell, activate the virtual environment with:

```powershell
.\.venv\Scripts\Activate.ps1
```

## Frontend Only

```sh
cd frontend
npm install
npm run dev
```
