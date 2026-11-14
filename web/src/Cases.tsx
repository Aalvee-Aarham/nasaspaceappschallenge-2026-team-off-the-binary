import { useEffect, useState } from "react";
import { CaseVerdict, CasesResponse, ExposureResponse, FireCase, Region, SHORT, api, fmt, periodLabel } from "./api";

const ORDER: CaseVerdict[] = ["agency_only", "corroborated", "reported", "satellite_only", "abstained", "insufficient"];
const LABEL: Record<CaseVerdict, string> = {
  corroborated: "Two independent witnesses agree", reported: "Reported, not seen by the satellites", satellite_only: "Only the satellites saw it",
  agency_only: "The record missed it", abstained: "The record could not see", insufficient: "Nobody saw anything",
};
const SHORT_LABEL: Record<CaseVerdict, string> = {
  corroborated: "corroborated", reported: "reported", satellite_only: "satellites only", agency_only: "record missed it", abstained: "could not see", insufficient: "nobody saw",
};

/** The verdict is always text, with a colour as a second cue. */
const Verdict = ({ v }: { v: CaseVerdict }) => <span className={`vd ${v}`}>{SHORT_LABEL[v]}</span>;

function satText(c: FireCase) {
  const s = c.witnesses.satellite;
  if (s.state === "abstain") return "could not see";
  if (s.state === "quiet") return "quiet";
  return `${fmt(s.cell_hotspots, 1)} in cell`;
}

function Witnesses({ c }: { c: FireCase }) {
  const { satellite: s, cross_family: x, agency, disaster_system: d, press } = c.witnesses;
  return (
    <div className="witness" aria-live="polite">
      <h4>{c.title} <span className="muted small">{c.date}</span></h4>
      <dl className="wl">
        <dt>NASA EONET</dt><dd>{agency ? <>wildfire event, {agency.date} {agency.url && <a href={agency.url} target="_blank" rel="noreferrer">source ↗</a>}</> : "no event record found in the searched source"}</dd>
        <dt>GDACS</dt><dd>{d ? <>{d.alert ? `${d.alert} alert` : "alert"}{d.burned_area_ha != null && `, ${fmt(d.burned_area_ha)} ha burned`} {d.url && <a href={d.url} target="_blank" rel="noreferrer">source ↗</a>}</> : "no event record found in the searched source"}</dd>
        <dt>The press</dt><dd>{press ? <>{fmt(press.count)} articles ({press.source}){press.outlets?.length ? `, ${press.outlets.join(", ")}` : ""}{press.sample_urls?.[0] && <> <a href={press.sample_urls[0]} target="_blank" rel="noreferrer">sample ↗</a></>}</> : "no reports found in the searched sources (not evidence that nothing happened)"}</dd>
        <dt>The record</dt>
        <dd>
          {s.state === "abstain" ? <>could not see: {s.reason}</> : s.state === "quiet" ? <>no fire in this 0.1° cell in {periodLabel(c.period)}</> : <>{fmt(s.cell_hotspots, 1)} hotspots in the 0.1° cell</>}
          <br />Area total {fmt(s.area_hotspots)}{s.ci95 && s.ci95[0] != null ? ` (95%: ${fmt(s.ci95[0])}–${fmt(s.ci95[1])})` : ""}
          {s.percentile != null && <>, {fmt(s.percentile, 0)}th percentile of {fmt(s.of_years)} years{s.rank != null && `, rank ${fmt(s.rank)}`}</>}
          <br />Coverage {s.coverage == null ? "–" : `${fmt(s.coverage * 100, 0)}%`} of days · satellites observing: {s.sensors.length ? s.sensors.map((k) => SHORT[k] ?? k).join(", ") : "–"}
        </dd>
        <dt>Cross-check</dt>
        <dd>{x.state === "abstain" ? <>could not check: {x.reason}</> : <>MODIS-only {fmt(x.modis_only, 1)} · VIIRS-only {fmt(x.viirs_only, 1)}{x.ratio != null && ` (×${x.ratio.toFixed(2)})`} · {x.agrees === false ? "the two instrument families differ by more than 25%" : x.agrees ? "they agree" : ""}</>}</dd>
      </dl>
      <p><b>Verdict:</b> {LABEL[c.verdict]}</p>
      {c.verdict === "agency_only" && <p className="warn small">An event record exists here and the harmonized record shows no fire in that cell and month. That is a fire below the detection threshold or outside the cell, or a gap in the record. This tells you which witness is missing, not which one is wrong.</p>}
      {c.flags.includes("faint_cell_signal") && <p className="muted small">The cell value is below one Aqua-scale hotspot: a faint signal.</p>}
      {c.note && <p className="muted small">{c.note}</p>}
    </div>
  );
}

function ExposurePanel({ id, period, online }: { id: string; period: string | null; online: boolean }) {
  const [ex, setEx] = useState<ExposureResponse | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    if (!online) return;
    let live = true;
    setEx(null); setErr("");
    api.exposure(id, period ?? undefined).then((r) => live && setEx(r)).catch((e) => live && setErr(e.message));
    return () => { live = false; };
  }, [id, period, online]);
  if (!online) return <p className="muted small">The exposure context needs the Kiln Watch API.</p>;
  if (err) return <p className="muted small">Exposure context: {err}</p>;
  if (!ex) return <div className="skeleton" />;
  const hosp = ex.hospital_list.slice(0, 5), roads = ex.road_list.slice(0, 5);
  return (
    <section className="exposure">
      <h3>Exposure <span className="muted small">{period ? periodLabel(period) : "every cell with fire since 2000"}</span></h3>
      {ex.fire_cells === 0 ? <p>No fire recorded in this month, so there is nothing to join.</p> : (
        <p className="expo-nums"><b>{fmt(ex.fire_cells)}</b> fire cells · about <b>{fmt(ex.population)}</b> people · <b>{ex.hospitals == null ? "–" : fmt(ex.hospitals)}</b> hospitals (plus <b>{ex.clinics == null ? "–" : fmt(ex.clinics)}</b> clinics and doctors) · <b>{ex.major_roads == null ? "–" : fmt(ex.major_roads)}</b> named major roads</p>
      )}
      {ex.errors?.hospitals && <p className="warn small">OpenStreetMap query failed: hospitals are missing from this view.</p>}
      {ex.errors?.roads && <p className="warn small">OpenStreetMap query failed: roads are missing from this view.</p>}
      <p className="warn small">{ex.caveat} Population is {ex.population_source.source}, {ex.population_source.vintage}: modelled, not a census.</p>
      {hosp.length > 0 && <>
        <h4>Some named hospitals in these cells</h4>
        <ul className="plain small">{hosp.map((h, i) => <li key={i}>{h.name} <span className="muted">{h.lat.toFixed(2)}, {h.lon.toFixed(2)}</span></li>)}</ul>
      </>}
      {roads.length > 0 && <>
        <h4>Named major roads crossing these cells</h4>
        <ul className="plain small">{roads.map((r, i) => <li key={i}>{r.name} <span className="muted">{r.kind}</span></li>)}</ul>
      </>}
    </section>
  );
}

export function Cases({ r, online, sel, onSel, onCases }: { r: Region; online: boolean; sel: string | null; onSel: (id: string | null) => void; onCases: (c: FireCase[] | null) => void }) {
  const id = r.meta.id;
  const [data, setData] = useState<CasesResponse | null>(null);
  const [err, setErr] = useState("");
  const [filter, setFilter] = useState<CaseVerdict | null>(null);
  useEffect(() => {
    if (!online) return;
    let live = true;
    setData(null); setErr(""); onSel(null); setFilter(null);
    api.cases(id).then((d) => { if (live) { setData(d); onCases(d.cases); } }).catch((e) => live && setErr(e.message));
    return () => { live = false; onCases(null); };
  }, [id, online]);

  if (!online) return <p className="muted">The casebook needs the Kiln Watch API.</p>;
  if (err) return <p className="muted">The casebook is not built for this area ({err}).</p>;
  if (!data) return <div className="skeleton tall" />;
  const rows = data.cases.filter((c) => !filter || c.verdict === filter);
  const chosen = data.cases.find((c) => c.id === sel) ?? null;
  return (
    <div className="stack">
      <section>
        <h3>Fire cases and their witnesses</h3>
        <p className="small">{data.cases.length} cases, each heard by the harmonized record, a MODIS-against-VIIRS cross-check, NASA EONET, GDACS and the press. {data.counts.agency_only ? <b>{data.counts.agency_only} of them are fires the record does not show.</b> : "No case here has an agency record that the harmonized record misses."}</p>
        <div className="seg" role="radiogroup" aria-label="Filter by verdict">
          <button role="radio" aria-checked={!filter} className={!filter ? "on" : ""} onClick={() => setFilter(null)}>all {data.cases.length}</button>
          {ORDER.filter((v) => data.counts[v] > 0).map((v) => (
            <button key={v} role="radio" aria-checked={filter === v} className={filter === v ? "on" : ""} onClick={() => setFilter(v)}>{SHORT_LABEL[v]} {data.counts[v]}</button>
          ))}
        </div>
        <ul className="srcline small muted">
          {data.sources.map((s) => <li key={s.name}>{s.name}: {s.error ? `not searched, ${s.error}` : s.searched ? `${fmt(s.count)} found` : `not searched: ${s.note ?? ""}`}</li>)}
        </ul>
        <div className="scroll">
          <table className="tbl click">
            <thead><tr><th>Date</th><th>Case</th><th>The record</th><th>Other witnesses</th><th>Verdict</th></tr></thead>
            <tbody>{rows.map((c) => (
              <tr key={c.id} className={c.id === sel ? "on" : ""} onClick={() => onSel(c.id)}>
                <td className="num">{c.date}</td>
                <td><button className="link" onClick={() => onSel(c.id)} aria-pressed={c.id === sel}>{c.title}</button></td>
                <td>{satText(c)}</td>
                <td className="small">{[c.witnesses.agency && "EONET", c.witnesses.disaster_system && "GDACS", c.witnesses.press && `press ${fmt(c.witnesses.press.count)}`].filter(Boolean).join(", ") || "none found"}</td>
                <td><Verdict v={c.verdict} /></td>
              </tr>
            ))}</tbody>
          </table>
        </div>
        {chosen && <Witnesses c={chosen} />}
        <p className="muted small">{data.caveat} Built {data.as_of.slice(0, 10)}; data through {data.data_through ?? "–"}.</p>
      </section>
      <ExposurePanel id={id} period={chosen?.period ?? null} online={online} />
    </div>
  );
}
