# Solar Monitor web (PWA)

Mobile-friendly UI for the local monitoring API.

## Dev

With the API on port 8000:

```powershell
cd c:\Users\tony\Projects\solar-monitor\apps\web
npm install
npm run dev
```

Open http://127.0.0.1:5173 — Vite proxies `/api` → `http://127.0.0.1:8000`.

## Docker

```powershell
docker compose up --build -d web
```

Open http://127.0.0.1:3080
