"""In-app analyst. The language model only routes: it reads the question plus a one-line catalogue of the
deterministic algorithms below and replies with which to run and their arguments, in one small call (~1K tokens).
The algorithms compute and word the judgment themselves (_SAY), so no pipeline data is ever sent to the model and
every number in the answer comes from the pipeline. Groq first (GROQ_API_KEY), Gemini keys as fallbacks.
UI steps (ui_*) are not executed here: they are handed back to the browser, which moves the map / calendar.
"""
import calendar
import json
import os
import re
import urllib.error
import urllib.request

import datetime as dt

from . import charts, news_more, outlook, tools

MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")   # an alias: follows Google's current Flash, so a retired version never breaks the analyst
FALLBACK = "gemini-flash-lite-latest"  # tried when the main model is overloaded or silent
# Groq's free tier allows 8K tokens/minute per model; a rate-limited model hands over to the next, then Gemini
GROQ_MODELS = [m.strip() for m in os.environ.get("GROQ_MODELS", "openai/gpt-oss-120b,openai/gpt-oss-20b,qwen/qwen3.8-27b").split(",") if m.strip()]
GROQ_MODEL = GROQ_MODELS[0]
MAX_STEPS = 4

CATALOGUE = """list_regions(): the built areas
region_summary(region_id): key findings, long-term trend, most active years
get_period(region_id, period): one finished month 'YYYY-MM' or ISO week 'YYYY-Www' against the same period in other years
find_anomalies(region_id, granularity='month'|'week'): the most unusual periods on record
evidence(region_id, period): daily detections, peak day, FIRMS map and Worldview links behind a period
reports(region_id, period): news and NASA EONET reports for one period
timeline_reports(region_id, start, end): reports month by month ('YYYY-MM') matched to the record
early_warning(region_id): the month in progress vs the same days in earlier years, and the usual next 4 weeks
check_watchlist(min_level='elevated'|'watch'|'normal'): built areas at or above a warning level
fire_cases(region_id, verdict?): fire cases heard by independent witnesses; verdict 'agency_only' = fires the record does not show
fire_case(region_id, case_id): one case and what each witness said
exposure(region_id, period?): people, hospitals, schools, roads, farmland in the cells where fire was detected
place_exposure(region_id, lat, lon): fire history at one point (a school, hospital or farm)
casebook_overview(): cases and exposure for every built area
place_risk(place): fire near any named place on Earth: last 7 days, usual season, 30-day outlook
find_place(query): locate a place and the built areas overlapping it
get_outlook(place?): climatological 30-day outlook in a place, or worldwide without a place
query_hotspots(place, start?, end?): raw detections per satellite in any place ('YYYY-MM-DD', default last 14 days)
annual_series(region_id): per year, harmonized hotspots vs raw detections
season_profile(region_id): typical season start/peak/end, season trends, year-to-date rank
compare_areas(region_ids): 2-6 built areas side by side
situation_brief(region_id): a full written brief
latest_fire_news(days=3): worldwide wildfire headlines of the last 1-30 days
show_chart(kind, region_id?, region_ids?, month?, place?, start?, end?): draw a chart; kind one of """ + "|".join(charts.KINDS) + """
ui_select_region(region_id) | ui_select_period(period) | ui_set_view(granularity?, scale?, tab?) | ui_show_cases(verdict?, case_id?): move the app's view"""

ROUTER = """You route questions in Kiln Watch, an app with a harmonized 2000-present record of NASA FIRMS satellite fire
detections per area. You never answer with numbers: you pick deterministic algorithms that compute the answer.
Reply with JSON only: {"steps":[{"algo":"<name>","args":{...}}],"note":"<optional one short sentence, no numbers>"}
- 1-4 steps. Use the open area and period from [state] when the question names no other.
- The month in progress needs early_warning, never get_period. "Recent" and "this month" are relative to today in [state].
- A place that is not a built area: place_risk, get_outlook or query_hotspots with "place".
- Add show_chart for trends, seasons or comparisons, and a ui_* step when moving the view helps.
- Greeting or a question about the app itself: no steps, answer in "note".
Algorithms:
""" + CATALOGUE


def _box(a):
    if all(a.get(k) is not None for k in ("west", "south", "east", "north")):
        return [a["west"], a["south"], a["east"], a["north"]]
    if a.get("place"):
        p = tools.find_place(a["place"])
        if p.get("found"):
            return p["bbox"]
        raise ValueError(f"place not found: {a['place']}")
    return None


def _outlook(a):
    box = _box(a)
    return outlook.in_box(box, limit=15) if box else outlook.get()


def _hotspots(a):
    a.setdefault("end", str(dt.date.today()))
    a.setdefault("start", str(dt.date.fromisoformat(a["end"]) - dt.timedelta(days=13)))
    box = _box(a)
    if not box:
        raise ValueError("query_hotspots needs a place")
    return tools.global_hotspots(box, a["start"], a["end"])


_RUN = {
    "list_regions": lambda a: tools.list_regions(),
    "region_summary": lambda a: tools.region_summary(a["region_id"]),
    "get_period": lambda a: tools.get_period(a["region_id"], a["period"]),
    "find_anomalies": lambda a: tools.find_anomalies(a["region_id"], a.get("granularity", "month"),
                                                     float(a.get("min_percentile", 90.0)), int(a.get("top_n", 5))),
    "evidence": lambda a: tools.evidence(a["region_id"], a["period"]),
    "reports": lambda a: tools.reports(a["region_id"], a["period"]),
    "timeline_reports": lambda a: tools.timeline_reports(a["region_id"], a["start"], a["end"]),
    "early_warning": lambda a: tools.early_warning(a["region_id"]),
    "check_watchlist": lambda a: tools.warnings(a.get("min_level", "watch")),
    "fire_cases": lambda a: tools.list_cases(a["region_id"], a.get("verdict") or None, int(a.get("limit", 20))),
    "exposure": lambda a: tools.exposure(a["region_id"], a.get("period") or None),
    "place_exposure": lambda a: tools.exposure_place(a["region_id"], a["lat"], a["lon"]),
    "fire_case": lambda a: tools.get_case(a["region_id"], a["case_id"]),
    "casebook_overview": lambda a: tools.casebook_overview(),
    "place_risk": lambda a: tools.place_risk(query=a.get("place") or a.get("query"), facilities=False),
    "find_place": lambda a: tools.find_place(a.get("query") or a.get("place")),
    "get_outlook": _outlook,
    "query_hotspots": _hotspots,
    "annual_series": lambda a: tools.annual(a["region_id"]),
    "season_profile": lambda a: tools.season_profile(a["region_id"]),
    "compare_areas": lambda a: tools.compare_areas(a["region_ids"]),
    "situation_brief": lambda a: tools.briefing(a["region_id"]),
    "latest_fire_news": lambda a: news_more.latest(int(a.get("days", 3))),
}


# ---- the judgment: each algorithm's result in a few sentences, written from the result alone ----

def _n(x):
    return f"{x:,.0f}" if isinstance(x, (int, float)) else "n/a"


def _months(ms):
    return ", ".join(calendar.month_name[m] for m in ms or [])


def _trend(t):
    if not t or t.get("p") is None:
        return "Long-term trend: not enough data."
    y = f", {t['years'][0]}-{t['years'][1]}" if t.get("years") else ""
    return (f"Seasonal Mann-Kendall test on monthly harmonized hotspots{y}: Sen slope {t['sen_per_year']} per year, p = {t['p']}"
            + (" (no significant trend)." if t["p"] >= 0.05 else "."))


def _items(items, k=5):
    return [f"- [{i.get('title')}]({i['url']}) ({i.get('date')}, {i.get('outlet') or i.get('source')})" if i.get("url")
            else f"- {i.get('title')} ({i.get('date')}, {i.get('outlet') or i.get('source')})" for i in (items or [])[:k]]


def _failed(sources):
    bad = [s["name"] for s in sources or [] if s.get("error") or s.get("searched") is False]
    return [f"_Could not search: {', '.join(bad)} (unavailable, not 'nothing found')._"] if bad else []


def _say_period(r, a):
    v, h = r["hotspots_aqua_scale"], r.get("vs_history") or {}
    out = [f"**{r['period']}**: **{_n(v['value'])}** hotspots on the Aqua MODIS scale (95% interval {_n(v['ci95'][0])}-{_n(v['ci95'][-1])})."]
    if h.get("rank"):
        out.append(f"Median of the same period in other years: **{_n(h.get('median_same_period'))}**; rank **{h['rank']} of {h['of_years']}** "
                   f"({_n(h.get('percentile'))}th percentile).")
    out.append(f"Raw detections, all satellites: {_n(r.get('raw_detections_all_satellites'))} (not comparable across satellite eras).")
    if r.get("partial"):
        out.append("_This period is still in progress; the early warning compares the same days in earlier years._")
    return out


def _say_warning(r, a):
    nx, out = r.get("next_4_weeks") or {}, [f"**{r['name']}**: early-warning level **{r['level'].upper()}**. {r['headline']}"]
    if nx.get("median") is not None:
        out.append(f"The next four weeks usually bring **{_n(nx['median'])}** hotspots (10th-90th percentile {_n(nx['p10'])}-{_n(nx['p90'])}).")
    if (y := r.get("year_to_date")) and y.get("rank"):
        out.append(f"Fire year so far: **{_n(y['value'])}** hotspots, rank {y['rank']} of {y['n']} (median {_n(y['median'])}).")
    return out + ["_Climatological outlook from history, not a forecast or an official alert._"]


def _say_cases(r, a):
    c = r["counts"]
    out = [f"**{r['total']}** fire cases: " + ", ".join(f"{k.replace('_', ' ')} **{v}**" for k, v in c.items() if v) + "."]
    out += [f"- {x['title']} ({x['date']}): {x.get('verdict_label') or x['verdict']} [case {x['id']}]" for x in r["cases"][:5]]
    return out + _failed(r.get("sources")) + [f"_{r['caveat']}_"]


def _say_case(r, a):
    w = r.get("witnesses") or {}
    seen = [f"{k.replace('_', ' ')}: {v.get('state')}" for k, v in w.items() if isinstance(v, dict) and v.get("state")]
    out = [f"**{r['title']}** ({r['date']}): verdict **{r.get('verdict_label') or r['verdict']}**.", "Witnesses: " + ("; ".join(seen) or "none reported") + "."]
    if isinstance(w.get("unavailable"), dict) and w["unavailable"]:
        out.append("Could not look: " + "; ".join(f"{k} ({v})" for k, v in w["unavailable"].items()) + ".")
    return out + ([r["note"]] if r.get("note") else [])


def _say_exposure(r, a):
    when = f" in {r['period']}" if r.get("period") else " since 2000"
    return [f"Cells with fire detected{when}: **{_n(r['fire_cells'])}**. They hold **{_n(r['population'])}** people (modelled 2020), "
            f"**{_n(r.get('hospitals'))}** hospitals, {_n(r.get('clinics'))} clinics, **{_n(r.get('schools'))}** schools and "
            f"{_n(r.get('major_roads') if not isinstance(r.get('major_roads'), list) else len(r['major_roads']))} major roads.",
            f"_{r['caveat']}_"]


def _say_place_exposure(r, a):
    if not r.get("in_record"):
        return ["That point is outside the area's record."]
    return [f"In this {r['cell_km2']} km² cell, fire was detected in **{r['months_with_fire']} of {r['months_in_record']}** months, "
            f"last in **{r.get('last_fire') or 'never'}**; {r['neighbours_with_fire']} neighbouring cells also had fire.",
            f"The cell holds {_n(r.get('population'))} people (modelled 2020), {_n(r.get('hospitals'))} hospitals, "
            f"{_n(r.get('schools'))} schools and {_n(r.get('cropland_km2'))} km² of cropland.", f"_{r['caveat']}_"]


def _say_outlook(r, a):
    c = r["counts"]
    out = [f"30-day outlook from {r['next_30_days'][0]}: **{_n(c.get('watch'))}** watch cells (season ahead and already above normal), "
           f"{_n(c.get('above'))} above normal, {_n(c.get('season'))} in an active season."]
    out += [f"- {g['name']}: {g['watch_cells']} watch cells" for g in (r.get("regions") or [])[:5]]
    return out + ["_What the next 30 days usually bring, from history; not a forecast._"]


def _say_hotspots(r, a):
    t = r["totals_by_satellite"]
    out = [f"Raw detections {r['start']} to {r['end']}: " + ", ".join(f"{s} **{_n(v['vegetation'])}**" for s, v in t.items()) + "."]
    out += [f"- Busiest cell {c['lat']}, {c['lon']}: {c['detections']} detections" for c in r.get("top_cells", [])[:3]]
    return out + [f"_{r['note']}_"]


def _say_reports(r, a):
    s = r["assessment"]
    return ([f"**{s['label']}** (record rank {s.get('rank')} of {s.get('of_years')}); **{s.get('reports_found', 0)}** reports found."]
            + _items(r.get("items")) + _failed(r.get("sources")) + [f"_{s.get('caveat', '')}_"])


def _say_timeline(r, a):
    v = r["verdict"]
    out = [f"**{v['label']}**."] + _items([i for i in r["items"] if i.get("relevant") is not False])
    if v.get("sources_failed"):
        out.append(f"_Could not search: {', '.join(v['sources_failed'])} (unavailable, not 'nothing found')._")
    return out


def _say_place_risk(r, a):
    return [f"**{r['place']['name']}**: level **{r['level']}**. {r['headline']}", *[f"- {x}" for x in r.get("reasons") or []], f"_{r['caveat']}_"]


def _say_compare(r, a):
    return [f"- **{x['name']}**: {x['level']}; peaks in {_months(x.get('peak_months'))}. {_trend(x.get('trend_full_harmonized'))}"
            for x in r["areas"]]


def _say_season(r, a):
    w, y = r.get("typical_season_iso_weeks") or {}, r.get("year_to_date") or {}
    out = [f"**{r['name']}**: peak months {_months(r.get('peak_months'))} hold {r.get('peak_share_pct')}% of a year's hotspots."]
    if w:
        out.append(f"Typical season: starts ISO week {w['start']}, peaks week {w['peak']}, ends week {w['end']} ({r.get('season_length_weeks')} weeks).")
    if y.get("rank"):
        out.append(f"Fire year so far: rank {y['rank']} of {y['n']}.")
    return out


def _say_annual(r, a):
    full = [x for x in r if x.get("complete", True)]
    top = sorted(full, key=lambda x: -x["harmonized"])[:3]
    return ["Most active complete years (harmonized): " + ", ".join(f"**{x['year']}** ({_n(x['harmonized'])})" for x in top) + ".",
            "Last years: " + ", ".join(f"{x['year']} {_n(x['harmonized'])}" for x in r[-6:]) + ".",
            "_Raw detection counts grow with each new satellite and are not comparable across eras; the harmonized values are._"]


_SAY = {
    "list_regions": lambda r, a: ["Built areas: " + ", ".join(f"**{x['name']}** (`{x['id']}`)" for x in r) + "."],
    "region_summary": lambda r, a: [f"**{r['name']}**", *[f"- {s}" for s in r["answers"]], f"- {_trend((r.get('trend_full') or {}).get('harmonized'))}"],
    "get_period": _say_period,
    "find_anomalies": lambda r, a: ["Most unusual periods:", *[
        f"- **{x['period']}**: {_n(x['hotspots_aqua_scale']['value'])} hotspots, {(x['vs_history'].get('ratio_to_median') or 0):.1f}x the median, "
        f"{_n(x['vs_history'].get('percentile'))}th percentile" for x in r]],
    "evidence": lambda r, a: [f"Peak day **{r['peak_day']['date']}** with {r['peak_day']['detections']} detections; "
                              f"{r['low_confidence_excluded']['excluded']} of {r['low_confidence_excluded']['of']} low-confidence detections excluded.",
                              f"[FIRMS map]({r['links']['firms_map']}) · [Worldview]({r['links']['worldview']})", f"_{r['note']}_"],
    "reports": _say_reports,
    "timeline_reports": _say_timeline,
    "early_warning": _say_warning,
    "check_watchlist": lambda r, a: [f"**{r['count']}** areas at this level or above:",
                                     *[f"- **{x['name']}**: {x['level']}. {x['headline']}" for x in r["alerts"]], f"_{r['disclaimer']}_"],
    "fire_cases": _say_cases,
    "fire_case": _say_case,
    "exposure": _say_exposure,
    "place_exposure": _say_place_exposure,
    "casebook_overview": lambda r, a: [f"- **{x['name']}**: {x['cases']['total']} cases, {x['cases']['counts'].get('agency_only', 0)} not in the record; "
                                       f"{_n((x.get('exposure') or {}).get('population'))} people in fire cells" for x in r["areas"]] + [f"_{r['caveat']}_"],
    "place_risk": _say_place_risk,
    "find_place": lambda r, a: [f"**{r['display_name']}** ({r['lat']}, {r['lon']})." + (
        " Built areas here: " + ", ".join(f"`{b['id']}`" for b in r["built_areas_overlapping"]) if r.get("built_areas_overlapping") else
        " No built area covers it.")] if r.get("found") else ["Place not found."],
    "get_outlook": _say_outlook,
    "query_hotspots": _say_hotspots,
    "annual_series": _say_annual,
    "season_profile": _say_season,
    "compare_areas": _say_compare,
    "situation_brief": lambda r, a: [r["markdown"]],
    "latest_fire_news": lambda r, a: ["Latest wildfire headlines:", *_items(r.get("items"), 8)],
}


# ---- model calls: Groq first, then each Gemini key ----

def available():
    return bool(os.environ.get("GROQ_API_KEY") or _keys())


def _groq(payload):
    """Groq's OpenAI-compatible API, taking and returning the Gemini payload shape the rest of this file uses."""
    msgs = [{"role": "system", "content": payload["systemInstruction"]["parts"][0]["text"]}] if "systemInstruction" in payload else []
    msgs += [{"role": "assistant" if c.get("role") == "model" else "user", "content": "".join(p.get("text", "") for p in c.get("parts", []))}
             for c in payload["contents"]]
    body = {"messages": msgs, "temperature": payload.get("generationConfig", {}).get("temperature", 0.2)}
    for n, model in enumerate(GROQ_MODELS):
        req = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions", data=json.dumps({**body, "model": model}).encode(),
                                     headers={"Content-Type": "application/json", "User-Agent": "kiln-watch",
                                              "Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                text = json.load(r)["choices"][0]["message"].get("content") or ""
            break
        except urllib.error.HTTPError as ex:
            if ex.code not in (429, 498, 500, 502, 503) or n == len(GROQ_MODELS) - 1:  # rate limit or overload: next model
                raise
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()  # qwen inlines its reasoning
    if payload.get("generationConfig", {}).get("responseMimeType") == "application/json":  # cut code fences / prose around the JSON
        lo, hi = min((text.find(b) for b in "[{" if b in text), default=0), max(text.rfind("]"), text.rfind("}"))
        text = text[lo:hi + 1] if hi >= lo else text
    return {"candidates": [{"content": {"role": "model", "parts": [{"text": text}]}}], "_model": f"groq/{model}"}


def _keys():
    """GEMINI_API_KEY first, then GEMINI_API_KEY_FALLBACK, then GEMINI_API_KEYS (comma-separated), duplicates dropped."""
    extra = (os.environ.get("GEMINI_API_KEYS") or "").replace(";", ",").split(",")
    keys = (os.environ.get("GEMINI_API_KEY"), os.environ.get("GEMINI_API_KEY_FALLBACK"), *extra)
    return [k for k in dict.fromkeys((k or "").strip() for k in keys) if k]


def _post(payload):
    groq_err = None
    if os.environ.get("GROQ_API_KEY"):
        try:
            return _groq(payload)
        except (urllib.error.HTTPError, OSError, KeyError, IndexError, ValueError) as ex:  # any Groq failure: fall back to Gemini
            groq_err = f"{ex} {ex.read().decode('utf-8', 'replace')[:200]}" if isinstance(ex, urllib.error.HTTPError) else ex
    try:
        return _post_gemini(payload)
    except RuntimeError as ex:
        raise RuntimeError(f"{ex} (Groq: {groq_err})" if groq_err else str(ex)) from None


def _post_gemini(payload):
    body = json.dumps(payload).encode()
    keys, why = _keys(), []
    if not keys:
        raise RuntimeError("no Gemini fallback key is set")
    for key in keys:  # the next key when this one is out of quota (429), overloaded (503) or refused (401/403)
        try:
            return _post_key(body, key)
        except _NextKey as ex:
            why.append(str(ex))
    if why and all(w == "429" for w in why):
        raise RuntimeError(f"Gemini free-tier rate limit reached on all {len(keys)} keys. Wait a minute and retry.")
    raise RuntimeError(f"Gemini is busy or refused every key ({', '.join(why)}). Try again in a minute.")


class _NextKey(Exception):
    pass


def _post_key(body, key):
    for model in dict.fromkeys((MODEL, FALLBACK)):
        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", data=body,
            headers={"Content-Type": "application/json", "x-goog-api-key": key})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                res = json.load(r)
                res["_model"] = model
                return res
        except urllib.error.HTTPError as ex:
            detail = ex.read().decode("utf-8", "replace")[:300]
            if ex.code in (404, 503) and model != FALLBACK:   # retired or overloaded model: try the fallback model
                continue
            if ex.code in (401, 403, 429, 503):
                raise _NextKey(str(ex.code)) from None
            raise RuntimeError(f"Gemini error {ex.code}: {detail}") from None
        except OSError as ex:  # timeouts, URLError, SSL EOF and RemoteDisconnected (not a URLError) all land here
            if model != FALLBACK:
                continue
            raise RuntimeError(f"Gemini did not answer in time ({ex}).") from None


def _text(res):
    parts = ((res.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [{}]
    return "".join(p.get("text", "") for p in parts if not p.get("thought"))


def classify_headlines(titles, area):
    """The model labels each headline: does it report a vegetation fire (wildfire, forest, grass, crop, peat) burning in
    or near the area? Returns a list of True/False in input order. Only filters what is counted; never adds data.
    Asks for the numbers of the matching headlines (robust to long lists), 60 headlines per request."""
    labels, model = [], MODEL
    for off in range(0, len(titles), 60):
        chunk = titles[off:off + 60]
        numbered = "\n".join(f"{i}. {(t or '')[:160]}" for i, t in enumerate(chunk))
        prompt = (f"Area: {area}.\nWhich of the numbered news headlines below report a vegetation fire (wildfire, forest, "
                  "bush, grass, crop/stubble or peat fire, or its smoke, evacuations or firefighting) in or near this area? "
                  "Exclude house or industrial fires, other places, politics and retrospectives without a current fire. "
                  f"Reply with only a JSON array of the matching headline numbers (0 to {len(chunk) - 1}).\n\n{numbered}")
        res = _post({"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                     "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}})
        hits = json.loads(_text(res) or "[]")
        if not isinstance(hits, list):
            raise RuntimeError("the model did not return a list of headline numbers")
        keep = {int(x) for x in hits if isinstance(x, (int, float, str)) and str(x).strip().isdigit()}
        labels += [i in keep for i in range(len(chunk))]
        model = res.get("_model", MODEL)
    return labels, model


# ---- the analyst ----

def route(message, history=None, context=None):
    """One model call: which algorithms answer this question. Sends only the catalogue, the area list, the screen
    state and the last question - never pipeline data."""
    state = {"today": str(dt.date.today()), **{k: v for k, v in (context or {}).items() if isinstance(v, (str, int, float)) and len(str(v)) < 80}}
    areas = "; ".join(f"{r['id']}={r['name']}" for r in tools.list_regions())
    prev = [m["text"][:200] for m in (history if isinstance(history, list) else []) if isinstance(m, dict) and m.get("role") == "user" and m.get("text")][-1:]
    msg = f"[state] {json.dumps(state)}\n[built areas] {areas}\n" + (f"[previous question] {prev[0]}\n" if prev else "") + f"[question] {message[:1000]}"
    res = _post({"systemInstruction": {"parts": [{"text": ROUTER}]}, "contents": [{"role": "user", "parts": [{"text": msg}]}],
                 "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}})
    try:
        plan = json.loads(_text(res))
    except ValueError:
        raise RuntimeError("the model did not return a plan") from None
    steps = [s for s in (plan.get("steps") or []) if isinstance(s, dict) and isinstance(s.get("algo"), str)][:MAX_STEPS]
    return steps, str(plan.get("note") or "")[:300], res.get("_model", MODEL)


def ask(message, history=None, context=None):
    if not available():
        raise RuntimeError("Set GROQ_API_KEY (free at https://console.groq.com/keys) or GEMINI_API_KEY to enable the analyst.")
    steps, note, model = route(message, history, context)
    rid = (context or {}).get("region_id")
    trace, actions, shown, calls_made, blocks = [], [], [], [], [note] if note else []
    for s in steps:
        name, args = s["algo"], s.get("args") if isinstance(s.get("args"), dict) else {}
        if rid and name in _RUN:
            args.setdefault("region_id", rid)  # the open area, when the router named none
        ok = True
        try:
            if name.startswith("ui_"):
                actions.append({"name": name, "args": args})
            elif name == "show_chart":
                shown.append(charts.build(args.get("kind"), args.get("region_id") or rid, args.get("month"), _box(args),
                                          args.get("start"), args.get("end"), args.get("region_ids")))
            elif name in _RUN:
                r = _RUN[name](args)
                calls_made.append((name, args))
                blocks.append("\n".join(_SAY[name](r, args)))
            else:
                ok = False
                blocks.append(f"_Unknown algorithm {name}._")
        except Exception as ex:
            ok = False
            blocks.append(f"_{name} could not run: {ex}_")
        trace.append({"tool": name, "args": args, "ok": ok})
    answer = "\n\n".join(b for b in blocks if b) or "I could not match that to an algorithm. Try naming an area and a month."
    return {"answer": answer, "trace": trace, "actions": actions, "model": model, "charts": (shown or charts.auto(calls_made))[:2]}
