import { useEffect, useMemo, useState } from "react";
import { ExposureResponse, Facility, Farmland, MONTH_SHORT, MONTHS, PlaceExposure, api, fmt, periodLabel } from "./api";
import { compact } from "./casebook";
import { saveAlerts, savedAlerts } from "./pages/shared";

// The exposure sections of the Cases & exposure page: which schools and hospitals sit where fire is detected, what
// farmland sees, and a lookup for one place. Every number comes from /exposure and /exposure/place. Context, never
// impact: a cell counts when one detection fell anywhere in its 11 km, so nothing here says a place was hit.

const EMBER = "#EA7329";   // fire data only (styles.css --ember)
const when = (p: string | null | undefined) => (p ? periodLabel(p) : "–");
const share = (n: number | undefined, of: number | undefined) => (n != null && of ? `${fmt((n / of) * 100, 0)}%` : "–");

/** Named schools or hospitals in cells with fire, the most often first, with a name filter. */
export function FacilityTable({ kind, rows, total, named, months, onCheck }: {
  kind: "schools" | "hospitals"; rows: Facility[]; total: number | null; named: number | null | undefined; months?: number;
  onCheck: (lat: number, lon: number, label: string) => void;
}) {
  const [q, setQ] = useState("");
  const [all, setAll] = useState(false);
  const hits = useMemo(() => { const t = q.trim().toLowerCase(); return t ? rows.filter((r) => r.name.toLowerCase().includes(t)) : rows; }, [q, rows]);
  const shown = all ? hits : hits.slice(0, 10);
  if (total == null) return <p className="muted small">The OpenStreetMap query for {kind} failed for this area, so they are missing here (shown as "–", never as zero).</p>;
  if (!rows.length) return <p className="muted small">{fmt(total)} {kind} lie in cells with fire, but none of them has a name in OpenStreetMap to list.</p>;
  return (
    <div className="ex-fac">
      <p className="small muted">
        {fmt(total)} {kind} lie in 11 km cells where fire was detected since 2000{named != null && named < total ? `. ${fmt(named)} have a name in OpenStreetMap` : ""}.
        {" "}Listed by how many months fire was seen in their cell{months ? ` (out of ${fmt(months)} months in the record)` : ""}.
      </p>
      <label className="ex-search"><span className="sr-only">Find a {kind === "schools" ? "school" : "hospital"} by name</span>
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={`Find a ${kind === "schools" ? "school" : "hospital"} by name…`} />
      </label>
      <div className="scroll">
        <table className="tbl click">
          <thead><tr><th scope="col">Name</th>{kind === "schools" && <th scope="col">Kind</th>}<th scope="col">Months with fire in its cell</th><th scope="col">Last seen</th><th scope="col"><span className="sr-only">Check</span></th></tr></thead>
          <tbody>{shown.map((r) => (
            <tr key={`${r.name}${r.lat}${r.lon}`} onClick={() => onCheck(r.lat, r.lon, r.name)}>
              <td>{r.name}</td>{kind === "schools" && <td className="small muted">{r.kind === "kindergarten" ? "kindergarten" : "school"}</td>}
              <td className="num">{fmt(r.months_with_fire ?? 0)}</td><td className="num">{when(r.last_fire)}</td>
              <td><button className="link small" onClick={(e) => { e.stopPropagation(); onCheck(r.lat, r.lon, r.name); }}>Fire history ›</button></td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      {hits.length === 0 && <p className="muted small">No {kind === "schools" ? "school" : "hospital"} in the list matches "{q}". The list holds the named ones in the cells with fire most often; check a place by its coordinates below.</p>}
      {hits.length > 10 && <button className="link small" onClick={() => setAll(!all)} aria-expanded={all}>{all ? "Show the first 10" : `Show all ${fmt(hits.length)}`}</button>}
    </div>
  );
}

/** People, schools and hospitals in cells with fire: built like FarmSection (stats, when, where, then the named places). */
export function PeopleSection({ e, onCheck }: { e: ExposureResponse; onCheck: (lat: number, lon: number, label: string) => void }) {
  const [tab, setTab] = useState<"schools" | "hospitals">("schools");
  return (
    <div className="ex-people">
      <h3 className="ex-first">Schools and hospitals where fire is detected most often</h3>
      <div className="ex-tabs" role="tablist" aria-label="Schools or hospitals">
        {(["schools", "hospitals"] as const).map((k) => (
          <button key={k} role="tab" aria-selected={tab === k} className={`btn ghost${tab === k ? " on" : ""}`} onClick={() => setTab(k)}>
            {k === "schools" ? `Schools${e.schools == null ? "" : ` · ${fmt(e.schools)}`}` : `Hospitals${e.hospitals == null ? "" : ` · ${fmt(e.hospitals)}`}`}
          </button>
        ))}
      </div>
      {tab === "schools"
        ? <FacilityTable key="s" kind="schools" rows={e.school_list ?? []} total={e.schools} named={e.schools_named} months={e.months_in_record} onCheck={onCheck} />
        : <FacilityTable key="h" kind="hospitals" rows={e.hospital_list} total={e.hospitals} named={null} months={e.months_in_record} onCheck={onCheck} />}
      <p className="muted small">{e.population_source?.source} ({e.population_source?.vintage}, modelled) for people; OpenStreetMap for schools and hospitals. A place is listed when fire was detected somewhere in its 11 km cell: a reason to look, not a sign it was reached. Smoke travels further; there is no smoke model here. {e.caveat}</p>
    </div>
  );
}

/** Twelve bars: hotspots per year on farmland cells, by calendar month. Hover or focus a bar to read it. */
function SeasonBars({ rows }: { rows: NonNullable<Farmland["by_month"]> }) {
  const [hover, setHover] = useState<number | null>(null);
  const W = 640, H = 180, L = 40, B = 22, T = 10, bw = (W - L) / 12;
  const max = Math.max(1e-9, ...rows.map((r) => r.hotspots_per_year ?? 0));
  const y = (v: number) => T + (1 - v / max) * (H - T - B);
  const hv = hover == null ? null : rows[hover];
  return (
    <figure className="cx-fig">
      <svg viewBox={`0 0 ${W} ${H}`} className="cx-line" role="img" aria-label="Hotspots per year on farmland cells, by calendar month. A table is in the text below." onMouseLeave={() => setHover(null)}>
        {[0, max / 2, max].map((t) => <g key={t}><line x1={L} x2={W} y1={y(t)} y2={y(t)} className="gridline" /><text x={L - 6} y={y(t) + 3} className="axis" textAnchor="end">{fmt(t, t < 10 ? 1 : 0)}</text></g>)}
        {rows.map((r, i) => {
          const v = r.hotspots_per_year ?? 0;
          return (
            <g key={r.month} onMouseEnter={() => setHover(i)} onFocus={() => setHover(i)} tabIndex={0} aria-label={`${MONTHS[i]}: ${fmt(v, 1)} hotspots per year`}>
              <rect x={L + i * bw} y={T} width={bw} height={H - T - B} fill="transparent" />
              <rect x={L + i * bw + 3} y={y(v)} width={bw - 6} height={Math.max(0, H - B - y(v))} fill={EMBER} opacity={hover == null || hover === i ? 0.9 : 0.4} rx={1.5} />
              <text x={L + i * bw + bw / 2} y={H - 6} className="axis" textAnchor="middle">{MONTH_SHORT[i]}</text>
            </g>
          );
        })}
      </svg>
      <figcaption className="small" aria-live="polite">
        {hv ? <><b>{MONTHS[hv.month - 1]}</b>: on average <b>{fmt(hv.hotspots_per_year ?? 0, 1)}</b> hotspots a year on farmland cells, and fire in <b>{fmt(hv.farm_cells_with_fire_per_year ?? 0, 1)}</b> farmland cells a year ({fmt(hv.record_years)} years of record).</>
          : "Point at a month to read it."}
      </figcaption>
    </figure>
  );
}

/** For farm owners: how much farmland lies in cells with fire, the months fire is detected on farmland, and where. */
export function FarmSection({ f, fireCells, onCheck }: { f: Farmland | null | undefined; fireCells: number; onCheck: (lat: number, lon: number, label: string) => void }) {
  if (f === undefined) return <p className="muted small">Farmland has not been added to this area's exposure layer yet.</p>;
  if (f === null) return <p className="muted small">The land-cover read failed for this area, so farmland is missing here (shown as "–", never as zero).</p>;
  const peak = f.by_month ? [...f.by_month].sort((a, b) => (b.hotspots_per_year ?? 0) - (a.hotspots_per_year ?? 0)).filter((m) => (m.hotspots_per_year ?? 0) > 0).slice(0, 2) : [];
  return (
    <div className="ex-farm">
      <div className="cx-stats">
        <div className="cx-stat"><span>Farmland in fire cells</span><b>{compact(f.cropland_km2)} km²</b></div>
        <div className="cx-stat"><span>Cells that are mostly farmland</span><b>{fmt(f.farm_cells)}</b></div>
        <div className="cx-stat"><span>Share of fire cells</span><b>{share(f.farm_cells, fireCells)}</b></div>
        <div className="cx-stat"><span>Main burning months</span><b>{peak.length ? peak.map((m) => MONTH_SHORT[m.month - 1]).join(", ") : "–"}</b></div>
      </div>
      {f.farm_cells > 0 && f.by_month && <>
        <h3>When fire is detected on farmland</h3>
        <SeasonBars rows={f.by_month} />
        <p className="small muted">Farmland cells: {f.farm_rule}. Hotspots are on the Aqua MODIS scale, averaged over the years of record for each month.</p>
      </>}
      {f.top_cells && f.top_cells.length > 0 && <>
        <h3>Farmland where fire is detected most often</h3>
        <div className="scroll">
          <table className="tbl click">
            <thead><tr><th scope="col">Cell</th><th scope="col">Cropland</th><th scope="col">Months with fire</th><th scope="col">Usual month</th><th scope="col">Last seen</th></tr></thead>
            <tbody>{f.top_cells.slice(0, 8).map((c) => (
              <tr key={`${c.lat},${c.lon}`} onClick={() => onCheck(c.lat + 0.05, c.lon + 0.05, `Farmland cell ${c.lat.toFixed(1)}°, ${c.lon.toFixed(1)}°`)}>
                <td className="num">{c.lat.toFixed(1)}°, {c.lon.toFixed(1)}°</td><td className="num">{fmt(c.cropland_km2, 0)} km²</td>
                <td className="num">{fmt(c.months_with_fire)}</td><td className="num">{MONTHS[c.peak_month - 1]}</td><td className="num">{when(c.last_fire)}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      </>}
      <p className="muted small">{f.source?.source}. {f.source?.note}</p>
    </div>
  );
}

/** One place's fire history: type coordinates, click a cell on the map, or pick a school, hospital or farm above. */
export function PlaceCheck({ regionId, bbox, target }: { regionId: string; bbox: number[]; target: { lat: number; lon: number; label: string; n: number } | null }) {
  const [text, setText] = useState("");
  const [label, setLabel] = useState("");
  const [data, setData] = useState<PlaceExposure | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const look = (lat: number, lon: number, name: string) => {
    setBusy(true); setErr(""); setLabel(name);
    api.exposurePlace(regionId, lat, lon).then(setData).catch((e) => { setData(null); setErr(e.message); }).finally(() => setBusy(false));
  };
  useEffect(() => { setData(null); setErr(""); setText(""); }, [regionId]);
  useEffect(() => { if (target) { setText(`${target.lat.toFixed(4)}, ${target.lon.toFixed(4)}`); look(target.lat, target.lon, target.label); } }, [target?.n]);   // eslint-disable-line react-hooks/exhaustive-deps
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const m = text.match(/(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)/);
    if (!m) { setErr("Type latitude and longitude, for example 30.90, 75.85."); return; }
    look(+m[1], +m[2], "Your place");
  };
  const d = data;
  return (
    <div className="ex-place" id="ex-place">
      <form onSubmit={submit} className="ex-form">
        <label htmlFor="ex-ll" className="small">Latitude, longitude of your farm, school or hospital</label>
        <div className="row"><input id="ex-ll" value={text} onChange={(e) => setText(e.target.value)} placeholder={`e.g. ${((bbox[1] + bbox[3]) / 2).toFixed(2)}, ${((bbox[0] + bbox[2]) / 2).toFixed(2)}`} inputMode="decimal" />
          <button className="btn" type="submit" disabled={busy}>{busy ? "Checking…" : "Check"}</button></div>
        <p className="muted small">Or click any cell on the map above, or a row in the tables. The area runs {bbox[1]}° to {bbox[3]}° latitude and {bbox[0]}° to {bbox[2]}° longitude.</p>
      </form>
      {err && <p className="muted" role="alert">{err}</p>}
      {d && (
        <article className="ex-card" aria-live="polite">
          <h3>{label} <span className="muted small">· cell {d.cell[0].toFixed(1)}°, {d.cell[1].toFixed(1)}° ({fmt(d.cell_km2)} km²)</span></h3>
          {!d.in_record ? <>
            <p><b>No fire has been detected in this 11 km cell since 2000.</b>{d.nearest_fire_cell_km != null && <> The nearest cell with fire is about {fmt(d.nearest_fire_cell_km, 0)} km away.</>}</p>
            {d.neighbours_with_fire > 0 && <p className="small">{d.neighbours_with_fire} of the 8 cells around it have had fire, most recently in {when(d.neighbours_last_fire)}.</p>}
          </> : <>
            <div className="cx-stats">
              <div className="cx-stat"><span>Months with fire</span><b>{fmt(d.months_with_fire ?? 0)}<small className="muted"> / {fmt(d.months_in_record)}</small></b></div>
              <div className="cx-stat"><span>Last seen</span><b>{when(d.last_fire)}</b></div>
              <div className="cx-stat"><span>Cells around with fire</span><b>{d.neighbours_with_fire} / 8</b></div>
              <div className="cx-stat"><span>Farmland in the cell</span><b>{d.cropland_km2 == null ? "–" : `${fmt(d.cropland_km2, 0)} km²`}</b></div>
            </div>
            {d.by_month && <>
              <h4>Which months fire is detected here</h4>
              <ol className="ex-season" aria-label="Years with fire in this cell, by calendar month">
                {d.by_month.map((m) => {
                  const t = m.record_years ? m.years_with_fire / m.record_years : 0;
                  return <li key={m.month} title={`${MONTHS[m.month - 1]}: fire in ${m.years_with_fire} of ${m.record_years} years`}>
                    <i style={{ background: EMBER, opacity: t ? 0.15 + 0.85 * t : 0.06 }} /><span>{MONTH_SHORT[m.month - 1]}</span><b>{m.years_with_fire}/{m.record_years}</b>
                  </li>;
                })}
              </ol>
              <p className="muted small">Each month shows in how many years fire was detected in this cell that month. Darker means more years.</p>
            </>}
            <p className="small">In this cell: about <b>{compact(d.population)}</b> people, <b>{d.schools == null ? "–" : fmt(d.schools)}</b> schools, <b>{d.hospitals == null ? "–" : fmt(d.hospitals)}</b> hospitals and <b>{d.clinics == null ? "–" : fmt(d.clinics)}</b> clinics.</p>
            {d.school_list && d.school_list.length > 0 && <details className="cx-more"><summary>Schools in this cell ({fmt(d.school_list.length)} named)</summary>
              <ul className="plain small ex-names">{d.school_list.map((s) => <li key={`${s.name}${s.lat}`}>{s.name}{s.kind === "kindergarten" && <span className="muted"> · kindergarten</span>}</li>)}</ul></details>}
            {d.hospital_list && d.hospital_list.length > 0 && <details className="cx-more"><summary>Hospitals in this cell ({fmt(d.hospital_list.length)} named)</summary>
              <ul className="plain small ex-names">{d.hospital_list.map((s) => <li key={`${s.name}${s.lat}`}>{s.name}</li>)}</ul></details>}
            {d.recent && d.recent.length > 0 && <p className="muted small">Recent months with fire: {d.recent.slice(0, 6).map((r) => `${periodLabel(r.period)} (${fmt(r.hotspots, r.hotspots < 1 ? 2 : 0)})`).join(", ")}. Hotspots on the Aqua MODIS scale.</p>}
          </>}
          <PlaceAlert lat={d.lat} lon={d.lon} label={label} />
          <p className="muted small">The cell counts when one detection fell anywhere in its 11 km. This is how often fire is detected near the place, not a sign the place or its crops burned.</p>
        </article>
      )}
    </div>
  );
}

const RADII = [5, 10, 25];

/** Alert for this one place: fire detected nearby (checked every few hours) and its usual fire season starting. */
function PlaceAlert({ lat, lon, label }: { lat: number; lon: number; label: string }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState(label);
  const [email, setEmail] = useState("");
  const [radius, setRadius] = useState(10);
  const [nearby, setNearby] = useState(true);
  const [season, setSeason] = useState(true);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<{ status: string | null | undefined } | null>(null);
  const [err, setErr] = useState("");
  const [emailOn, setEmailOn] = useState<boolean | null>(null);
  useEffect(() => { setName(label); setDone(null); setErr(""); }, [label, lat, lon]);
  useEffect(() => { if (open && emailOn == null) api.health().then((h) => setEmailOn(!!h.email)).catch(() => setEmailOn(null)); }, [open, emailOn]);
  if (!open) return <button className="btn ghost ex-alert-open" onClick={() => setOpen(true)}>Alert me about this place</button>;
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const triggers = [...(nearby ? ["nearby" as const] : []), ...(season ? ["season" as const] : [])];
    if (!triggers.length) { setErr("Pick at least one kind of alert."); return; }
    setBusy(true); setErr("");
    api.createAlert({ ratio: 1, name: name || undefined, email: email.trim() || undefined, triggers, place: { lat, lon, radius_km: radius, label: name || label } })
      .then((a) => { saveAlerts([...savedAlerts().filter((s) => s.token !== a.token), { token: a.token, name: name || label }]); setDone({ status: a.email_status }); })
      .catch((x) => setErr(x.message)).finally(() => setBusy(false));
  };
  if (done) return (
    <div className="ex-alert ok" role="status">
      <b>{done.status === "confirmation_sent" ? "Check your inbox" : "Alert created"}</b>
      <p className="small">{done.status === "confirmation_sent" ? <>We sent a confirmation link to <b>{email}</b>. Nothing is sent before you click it, and every email has a one-click unsubscribe.</>
        : email ? <>The confirmation email could not be sent ({done.status?.replace("not_sent: ", "")}). The alert still works through n8n.</>
          : <>No email given: see it under My alerts, or connect it to n8n.</>}</p>
      <a className="link small" href="#pg=warning">Open My alerts ›</a>
    </div>
  );
  return (
    <form className="ex-alert" onSubmit={submit}>
      <b>Alert me about this place</b>
      <label className="small">Name<input value={name} onChange={(e) => setName(e.target.value)} maxLength={120} /></label>
      <label className="small">Email (optional)<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" autoComplete="email" /></label>
      <fieldset className="small"><legend>Tell me when</legend>
        <label><input type="checkbox" checked={nearby} onChange={(e) => setNearby(e.target.checked)} /> fire is detected within{" "}
          <select value={radius} onChange={(e) => setRadius(+e.target.value)} aria-label="Distance">{RADII.map((r) => <option key={r} value={r}>{r} km</option>)}</select>{" "}
          (checked every few hours, each detection once)</label>
        <label><input type="checkbox" checked={season} onChange={(e) => setSeason(e.target.checked)} /> a month that usually has fire nearby is a week away (history, not a forecast)</label>
      </fieldset>
      {emailOn === false && <p className="muted small">This server has no email settings (SMTP) yet, so emails cannot go out. The alert still works through n8n or under My alerts.</p>}
      {err && <p className="error small" role="alert">{err}</p>}
      <div className="row"><button className="btn" type="submit" disabled={busy}>{busy ? "Saving…" : "Create alert"}</button>
        <button className="btn ghost" type="button" onClick={() => setOpen(false)}>Cancel</button></div>
      <p className="muted small">Satellites see heat a few hours after it happens and miss small or cloud-covered fires. This is an early hint, not an official warning: in an emergency, call your local fire service.</p>
    </form>
  );
}
