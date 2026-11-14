# Plan 016: Backend small fixes from the code scan

> **Executor instructions**: Ten independent small fixes. Do them in order, one commit each, and run the step's
> verification before the next. Each step stands alone: if one hits a STOP condition, skip it, note it in the status
> row and carry on with the next. When done, update the status row for this plan in `docs/plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat 1e99c85..HEAD -- server/kw/ server/tests/ Dockerfile web/src/pages/Warning.tsx web/src/api.ts`
> Before each step compare its excerpt with the live code; on a mismatch, skip that step and note it.

## Status

- **Priority**: P1 for steps 1–4 (visible to judges or wrong on the Warning page), P2 for the rest
- **Effort**: S (each step ≤ 15 lines)
- **Risk**: LOW
- **Depends on**: none. Steps 1 and 10 change `build.py` output, so land them before plan 003's rebuild; step 6
  matters once plan 008 turns email on.
- **Category**: bugs
- **Planned at**: commit `1e99c85`, 2026-11-13 (code-scan findings B5, S7, B15, B14, B7, B11, B1, B8, B12, S14, B6, B4 — all re-read and confirmed)

## Commands

| Purpose | Command | Expected |
|---|---|---|
| Python env | `cd server && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt` | exit 0 |
| Tests | `python server/tests/test_science.py && python server/tests/test_alerts.py` | all `ok`, exit 0 |
| Web typecheck | `cd web && npm ci && npx tsc --noEmit` | exit 0 |
| Syntax | `python -c "import ast,sys;[ast.parse(open(f).read()) for f in sys.argv[1:]]" server/kw/*.py` | no output |

## Scope

**In scope**: `server/kw/build.py`, `tools.py`, `alerts.py`, `news.py`, `agent.py`, `mcp_server.py`,
`server/tests/test_alerts.py`, `Dockerfile`, `web/src/Record.tsx` (one line), `web/src/api.ts` (one type),
`web/src/pages/Warning.tsx` (one line).
**Out of scope**: anything scientific beyond step 2's anchor; no new dependencies; no data edited by hand.

## Steps

### Step 1 (B5): provenance "source" is written twice

`server/kw/build.py` ~804 and ~811, inside `"provenance": {`:
```python
            "source": "NASA FIRMS active fire detections (MODIS C6.1, VIIRS 375 m C2), standard + NRT",
            ...
            "build_seconds": round(time.time() - t0, 1), "source": source,
```
The second key overwrites the first, so the Method/provenance box shows "Source: detections" (seen in punjab and
se-australia). Rename the second key to `"build_source": source`. No reader uses the second meaning
(`grep -rn "provenance" server/kw web/src` shows only `Record.tsx:589` printing `m.provenance.source`).

**Verify**: `grep -n '"build_source": source' server/kw/build.py` → 1 hit; syntax check passes.

### Step 2 (S7): "next four weeks" is one week off from the season card

`server/kw/tools.py:238-252` `_next_weeks(b, k=4)` anchors on the **current partial week**:
```python
    y0, w0 = int(b["periods"][-1][:4]), int(b["periods"][-1][6:])
```
while `build._season(weekly, full_weeks[-1])` (`build.py:742`) computes `next_4_weeks_share_pct` from the **last
complete week**. The Warning tile shows both, so the two "next four weeks" are different weeks. Anchor
`_next_weeks` on the last complete week too:
```python
    last = max((i for i, p in enumerate(b["partial"]) if not p), default=len(b["periods"]) - 1)
    y0, w0 = int(b["periods"][last][:4]), int(b["periods"][last][6:])
```
**Verify**: `cd server && python -c "from kw import tools; print(tools.early_warning('punjab').get('next_weeks') or tools._next_weeks(tools._read('punjab','weekly')))"`
→ a dict whose `weeks` starts right after the last complete week (compare with `weekly.json` `partial`).
If `tools._read` has a different signature, read the weekly file with `json.load` instead.

### Step 3 (B15): `sensor_status` hard-codes sensor facts in prose

`server/kw/tools.py:523-533` ends with:
```python
            "note": "Derived from the data (latest detection per satellite across all areas). Suomi-NPP's active-fire "
                    "stream ended in November 2026; Terra and Aqua orbits are drifting."}
```
This breaks the project rule "sensor availability is measured from data, never hard-coded end dates". Replace the note with:
```python
            "note": "Derived from the data: the latest detection per satellite across all built areas. "
                    "silent_over_3_days lists satellites with no detection in the 3 days before the newest one."}
```
**Verify**: `grep -n "ended in November" server/kw/tools.py` → no hits.

### Step 4 (B14): `region_summary` crashes when Suomi-NPP has no validation row

`server/kw/tools.py:50`:
```python
    val = next(v for v in m["validation"]["veg_det_D"] if v["sensor"] == "VIIRS_SNPP")
```
raises `StopIteration` (HTTP 500) for an area without that row. Change to
`val = next((v for v in m["validation"]["veg_det_D"] if v["sensor"] == "VIIRS_SNPP"), None)`.
`strip(None)` already returns `{}` (`(d or {})`).

**Verify**: syntax check passes; `cd server && python -c "from kw import tools; print(tools.region_summary('punjab')['id'])"` → `punjab`.

### Step 5 (B7): a total news outage reads as "no matching reports found"

`server/kw/news.py` `assess(hist, n_items, sources)`:
```python
    elif pct >= 90:
        label, tone = "Unusually high compared with the same period in other years; no matching reports found", "unverified"
```
When every source failed, `searched` is empty and nothing was looked at. Insert before that branch:
```python
    elif pct >= 90 and not searched:
        label, tone = "Unusually high compared with the same period in other years; couldn't check the news: no source answered", "neutral"
```
(Missing news is not evidence of absence — project guardrail.)

**Verify**: `cd server && python -c "from kw.news import assess; print(assess({'percentile': 95}, 0, [{'name':'GDELT','searched':True,'error':'HTTP 500'}])['label'])"`
→ ends with `no source answered`. (If importing `kw.news` fails without duckdb, run inside the venv.)

### Step 6 (B1): a failed alert email is recorded as delivered

`server/kw/alerts.py` `check(token, once=False)` marks `last_notified` / `last_outlook` / `events_seen` (block with
the comment `# ponytail: marked before delivery; a failed send is not retried`, ~line 278) **before**
`send_now` calls `send_email`. If SMTP fails, the alert never fires again. The n8n poll route marks on poll on
purpose (n8n sends the mail itself) and must keep doing so.

1. Move the marking into a function and drive it from `check`'s output:
   ```python
   def _mark(token, st):
       """Record what was reported, so the next scheduled poll does not repeat it."""
       with _lock:
           d = _load()
           if token not in d:
               return
           if st.get("triggered") and st.get("month"):
               d[token]["last_notified"] = st["month"]["period"]
           if st.get("outlook_triggered") and st.get("outlook"):
               d[token]["last_outlook"] = st["outlook"]["as_of"]
           if st.get("new_events"):
               d[token]["events_seen"] = ((d[token].get("events_seen") or []) + [x["title"] for x in st["new_events"]])[-200:]
           _save(d)
   ```
2. Give `check` a parameter: `def check(token, once=False, mark=True):`. Delete the old marking block and, just
   before `return out` in the ready path, add `if once and mark: _mark(token, out)`.
   (`out["triggered"]` is `new` and `out["outlook_triggered"]` is `ol_new` when `once`, so the same things are marked.)
3. In `send_now`: `st = check(token, once=not force, mark=False)`, and right after the
   `send_email(...)` line add `if not force: _mark(token, st)`.
4. Test, in `server/tests/test_alerts.py`:
   ```python
   def test_failed_send_is_retried():
       alerts.FILE = Path(tempfile.mkdtemp()) / "alerts.json"
       ok = lambda *a, **k: None  # noqa: E731
       alerts.send_email, real = ok, alerts.send_email
       alerts.smtp_ready, real_ready = (lambda: True), alerts.smtp_ready
       try:
           a = alerts.create(region_id="punjab", ratio=0.5, min_hotspots=0, email="test@example.com", base_url="http://x")
           d = alerts._load(); d[a["token"]]["confirmed"] = True; alerts._save(d)
           def boom(*a, **k): raise RuntimeError("SMTP unreachable")
           alerts.send_email = boom
           try:
               alerts.send_now(a["token"])
           except RuntimeError:
               pass
           assert alerts.check(a["token"], once=True)["triggered"] is True   # still due after the failure
       finally:
           alerts.send_email, alerts.smtp_ready = real, real_ready
   ```
**Verify**: `python server/tests/test_alerts.py` → all `ok` including `test_failed_send_is_retried` and
`test_poll_notifies_once_per_month_and_workflow_has_token` (proves the n8n path still marks).
STOP this step if `create` with an email needs more than `smtp_ready`/`send_email` patched (report what it calls).

### Step 7 (B11): an EONET outage shows nothing at all

`server/kw/alerts.py` `_events` returns `None` on any exception, and `check` puts it in `"events_in_box": evs`;
`web/src/pages/Warning.tsx:446` renders `{ok?.events_in_box && …}`, so "EONET is down" looks like an empty panel.
1. In `check`, in the `extra = {...}` dict add
   `"events_error": "NASA EONET is unavailable right now" if "events" in trig and evs is None else None,`
2. `web/src/api.ts:122`: add `events_error?: string | null;` next to `events_in_box`.
3. `web/src/pages/Warning.tsx`, right after line 446 add
   `{ok?.events_error && <div className="small muted">{ok.events_error}</div>}`

**Verify**: `cd web && npx tsc --noEmit` → exit 0.

### Step 8 (B8): a rejected alert still starts an area build

`server/kw/alerts.py:151-161`: `rid = tools.start_aoi(bbox, name)["id"]` runs before the `MAX_ALERTS`,
`MAX_PER_EMAIL` and "3 unconfirmed" checks. Move those three checks into
```python
def _check_limits(d, email):
    if len(d) >= MAX_ALERTS:
        raise ValueError("alert limit reached")
    if email and sum(s.get("email") == email for s in d.values()) >= MAX_PER_EMAIL:
        raise ValueError(f"at most {MAX_PER_EMAIL} alerts per email address")
    if email and sum(s.get("email") == email and not s.get("confirmed") for s in d.values()) >= 3:
        raise ValueError("this address has 3 unconfirmed alerts: confirm those first (check the inbox)")  # anti-spam
```
call `with _lock: _check_limits(_load(), email)` **before** the `if region_id:` block, and keep a second
`_check_limits(d, email)` call where the checks were (inside the creation lock, so two parallel requests cannot both pass).

**Verify**: `python server/tests/test_alerts.py` → all `ok`.

### Step 9 (B12): the analyst's `find_place` does not return what it declares

`server/kw/agent.py:66` declares "centre, a 0.5-4 degree box …, built areas overlapping it", but
`_RUN["find_place"]` (`agent.py:112`) is `news_more.geocode(a["query"]) or {"found": False}` — no overlap list.
The MCP tool (`mcp_server.py:40-50`) does it right. Move the MCP body into `tools.py`:
```python
def find_place(query):
    """Any place name -> centre, box and the built areas overlapping it (shared by MCP and the analyst)."""
    from . import news_more  # local import: news_more is only needed here
    g = news_more.geocode(query)
    if not g:
        return {"found": False, "query": query}
    w, s, e, n = g["bbox"]
    near = [r for r in list_regions() if not (r["bbox"][2] < w or r["bbox"][0] > e or r["bbox"][3] < s or r["bbox"][1] > n)]
    return {"found": True, **g, "built_areas_overlapping": [{"id": r["id"], "name": r["name"]} for r in near]}
```
Then `mcp_server.find_place` body becomes `return tools.find_place(query)` (keep its decorator and docstring), and
`agent.py` `"find_place": lambda a: tools.find_place(a["query"]),`.

**Verify**: syntax check passes; `cd server && python -c "from kw import mcp_server, agent; print('ok')"` → `ok`.

### Step 10 (S14, B6, B4): traceability and test hygiene

- **S14** `server/kw/build.py:73-78` `_code_version` uses `git rev-parse --short HEAD`, so a build from uncommitted
  code is stamped with a commit it did not come from, and 8 of 9 published areas say `unversioned`. Use
  `["git", "describe", "--always", "--dirty"]`. (The values in the files only change on the next rebuild.)
- **B6** `server/tests/test_alerts.py` can exit 134 after all tests pass: `alerts.check` calls
  `tools.refresh_if_stale`, which starts a background rebuild thread (DuckDB) that is killed at interpreter exit.
  After `from kw import alerts, tools` add `tools.SERVERLESS = True  # no background rebuilds in tests`
  (`refresh_if_stale` returns early when `SERVERLESS`). If the test then fails because a code path refuses to run
  when serverless, revert this bullet and note it.
- **B4** `Dockerfile` copies `data/regions/` and `data/global/outlook.json` but not the tracked
  `data/sensor_days.parquet` (read by `server/kw/firms.py:100`), so a container re-derives it on first use. After
  the line `COPY data/global/outlook.json data/global/outlook.json` add
  `COPY data/sensor_days.parquet data/sensor_days.parquet`.

**Verify**: `python server/tests/test_alerts.py; echo "exit $?"` → `exit 0`; `grep -n sensor_days Dockerfile` → 1 hit.

## Done criteria

- [ ] `python server/tests/test_science.py && python server/tests/test_alerts.py` exit 0
- [ ] `cd web && npx tsc --noEmit` exits 0
- [ ] `grep -n "ended in November" server/kw/tools.py` → no hits; `grep -c '"source"' server/kw/build.py` → 1 inside provenance
- [ ] `docs/plans/README.md` row 016 updated, listing any skipped step

## STOP conditions

- Any existing test starts failing after a step: revert that step and note it.
- Step 6: see its own STOP line.

## Maintenance notes

- Plan 008 enables SMTP on Vercel; Vercel has no delivery loop (`deliver_all` runs only in a long-lived API), so
  step 6 matters for the Docker/uvicorn deployment and for n8n users sending mail through `send_now`.
- Step 9 makes `tools.find_place` the single place for this lookup; new callers should use it.
