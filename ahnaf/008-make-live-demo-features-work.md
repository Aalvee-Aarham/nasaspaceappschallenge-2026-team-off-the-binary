# Plan 008: Every feature a judge clicks on the live site works or says why not

> **Executor instructions**: Follow this plan step by step. Steps marked **[HUMAN]** need a team member with the
> Vercel account and secrets; an executor model must not invent, request or print secret values — it stops at those
> steps and lists them in its report. Run every verification command. If anything in "STOP conditions" occurs, stop
> and report. When done, update the status row for this plan in `docs/plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat 1e99c85..HEAD -- server/kw/api.py web/src/pages/Warning.tsx web/src/api.ts api/index.py vercel.json`
> On a mismatch with the excerpts below, STOP.

## Status

- **Priority**: P1
- **Effort**: S (code) + S (human configuration)
- **Risk**: LOW
- **Depends on**: plan 001 (deploy from a clean checkout)
- **Category**: ops / security (hardening)
- **Planned at**: commit `1e99c85`, 2026-11-13

## Why this matters

The README advertises an AI analyst and email alerts. On the live site (`https://kiln-watch-seven.vercel.app`)
`/api/health` currently returns `"agent": false, "email": false`: no Gemini key and no SMTP settings. A judge who
opens the Analyst gets the fallback text, and a judge who subscribes gets "could not be sent". On Vercel,
alerts live in `/tmp` and vanish when the function cold-starts. Without `PUBLIC_URL`, confirmation links are built
from the request's Host header, so a forged Host header could point a confirmation email at another domain.
After this plan, the analyst and email work live, links always use the real domain, and the page says plainly what
the hosted demo keeps and for how long.

## Current state

- `server/kw/api.py:57-62`:
  ```python
  @app.get("/api/health")
  def health():
      regions = tools.list_regions()
      return {"ok": True, "agent": agent.available(), "model": agent.MODEL if agent.available() else None,
              "email": alerts.smtp_ready(),
              "regions": len(regions), "data_through": max((r["data_through"] for r in regions), default=None)}
  ```
- `server/kw/api.py:211-212`:
  ```python
  def _public_base(request: Request):
      return os.environ.get("PUBLIC_URL") or str(request.base_url)
  ```
- Env vars read by the server: `GEMINI_API_KEY` (and optional `GEMINI_API_KEY_FALLBACK`, `GEMINI_MODEL`) in
  `server/kw/agent.py`; `SMTP_HOST`, `SMTP_PORT` (default 587), `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`,
  `SMTP_TLS` in `server/kw/alerts.py`; `PUBLIC_URL` in `api.py` and `mcp_server.py`.
- `server/kw/tools.py:23`: `SERVERLESS = bool(os.environ.get("KW_SERVERLESS"))` (set by `api/index.py` on Vercel).
- `server/kw/api.py` `lifespan`: on serverless the periodic email delivery loop is skipped (comment explains why).
- `web/src/pages/Warning.tsx:34`: `api.health().then((h) => setEmailOn(!!h.email))`; line ~268 shows a note when
  `emailOn === false`. `web/src/api.ts` has `export type Health = {...}` (find it with `grep -n "type Health" web/src/api.ts`).
- Deploy: `vercel.json` (build copies `data/regions` into `web/dist/data/regions`; Python function `api/index.py`).

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Typecheck | `cd web && npx tsc --noEmit` | exit 0 |
| Local API | `cd server && uvicorn kw.api:app --port 8000` | serves |
| Health | `curl -s localhost:8000/api/health` | JSON |
| Live health | `curl -s https://kiln-watch-seven.vercel.app/api/health` | JSON |

## Scope

**In scope**: `server/kw/api.py` (`health`, `_public_base`), `web/src/api.ts` (`Health` type),
`web/src/pages/Warning.tsx` (the email note), Vercel project settings **[HUMAN]**.
**Out of scope**: adding a database or KV store (not for a hackathon demo); `alerts.py` logic; `api/index.py`.

## Git workflow

Branch `advisor/008-live-demo`; commit `Report serverless limits and pin the public URL`; `graphify update .` if installed; no push.

## Steps

### Step 1: Health tells the UI whether this is the short-lived hosted demo

In `health()` add `"serverless": tools.SERVERLESS,` to the returned dict. In `web/src/api.ts` add
`serverless?: boolean;` to the `Health` type.

**Verify**: `curl -s localhost:8000/api/health` → contains `"serverless":false`; `cd web && npx tsc --noEmit` → exit 0

### Step 2: Never build links from the Host header in production

```python
def _public_base(request: Request):
    # Links in emails must point at our own domain; the Host header is caller-controlled.
    if os.environ.get("PUBLIC_URL"):
        return os.environ["PUBLIC_URL"]
    if alerts.smtp_ready():
        raise HTTPException(503, "PUBLIC_URL must be set on a server that sends email")
    return str(request.base_url)
```
**Verify**: with SMTP vars unset locally, `curl -s -X POST localhost:8000/api/alerts -H 'content-type: application/json' -d '{"region_id":"punjab","ratio":1}'` → JSON with a `token` (still works without email).

### Step 3: Say what the hosted demo keeps

In `web/src/pages/Warning.tsx`, store the health result (extend the existing `api.health().then(...)` to also keep
`h.serverless`) and, next to the existing `emailOn === false` note, render when serverless:
```tsx
<p className="muted small">This hosted demo keeps alerts only while its server stays warm (minutes to hours). The
  confirmation and "send test" emails work here; for alerts that last, run Kiln Watch with Docker (see the README) or use n8n.</p>
```
**Verify**: `cd web && npx tsc --noEmit` → exit 0

### Step 4 [HUMAN]: Configure Vercel

In the Vercel dashboard → Project → Settings → Environment Variables (Production), add:
- `GEMINI_API_KEY` — a free key from Google AI Studio.
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` — e.g. a free Brevo SMTP account (sender
  address verified there), port 587.
- `PUBLIC_URL` = `https://kiln-watch-seven.vercel.app`
Never commit these values or paste them into issues or chat.

### Step 5 [HUMAN]: Redeploy from a clean checkout

From a fresh clone of the merged `main` (so no local `data/regions/aoi-*` folders ship — see plan 001):
`vercel --prod`.

**Verify**: `curl -s https://kiln-watch-seven.vercel.app/api/health` → `"agent":true`, `"email":true`, `"serverless":true`, `"regions":9`

### Step 6 [HUMAN]: Click test

On the live site: open Explorer → Analyst → ask "Is this November unusual in Punjab?" → an answer with a tool trace.
Early warning → subscribe your own address to Punjab → confirmation email arrives → confirm → "Send test" → email arrives.

## Test plan

- Steps 1–3 verified locally with curl and `tsc`.
- Step 6 is the end-to-end check (human).

## Done criteria

- [ ] `cd web && npx tsc --noEmit` exits 0
- [ ] Local `/api/health` includes `serverless`
- [ ] **[HUMAN]** Live `/api/health` shows `agent: true`, `email: true`, `regions: 9`
- [ ] **[HUMAN]** Step 6 completed
- [ ] `docs/plans/README.md` row 008 updated

## STOP conditions

- You are asked to handle a secret value (stop; that is a human step).
- Live health shows `regions` other than 9 after redeploy (local folders shipped; redeploy from a clean clone).

## Maintenance notes

- If the team wants lasting alerts on the hosted demo, the cheapest route is the existing `Dockerfile` on a
  Hugging Face Space (port 7860), where the email loop in `lifespan` runs. Not needed for judging.
- Rotate the Gemini key and SMTP password after the hackathon if they were ever shared in chat.
