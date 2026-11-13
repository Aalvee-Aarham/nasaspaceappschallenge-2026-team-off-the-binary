import { useEffect, useState } from "react";
import { CaseVerdict, CasebookOverview, ExposureResponse, api, fmt } from "../api";
import { CaseCard, CellMap, Icon, LABEL, VerdictChips, compact, peopleShade, useCases, useExposure } from "../casebook";
import { AreaSelect, Offline, PageHead, PageProps } from "./shared";

/** People living in the cells that had fire, per year: one series, hover to read, a table on demand. */
function PeopleByYear({ rows }: { rows: NonNullable<ExposureResponse["by_year"]> }) {
  const [table, setTable] = useState(false);
  const [hover, setHover] = useState<number | null>(null);
  const W = 640, L = 46, R = 10, T = 12, B = 24, H = 200;
  const max = Math.max(1, ...rows.map((r) => r.population));
  const px = (i: number) => L + (rows.length > 1 ? (i / (rows.length - 1)) * (W - L - R) : 0);
  const py = (v: number) => T + (1 - v / max) * (H - T - B);
  const pts = rows.map((r, i) => `${px(i)},${py(r.population)}`).join(" ");
  const hv = hover == null ? null : rows[hover];
  return (
    <figure className="cx-fig">
      <svg viewBox={`0 0 ${W} ${H}`} className="cx-line" role="img" aria-label="People living in the cells that had fire, per year. A table is available below."
        onMouseLeave={() => setHover(null)}
        onMouseMove={(ev) => { const b = ev.currentTarget.getBoundingClientRect(); const fx = ((ev.clientX - b.left) / b.width) * W; setHover(Math.max(0, Math.min(rows.length - 1, Math.round(((fx - L) / (W - L - R)) * (rows.length - 1))))); }}>
        {[0, max / 2, max].map((t) => <g key={t}><line x1={L} x2={W - R} y1={py(t)} y2={py(t)} className="gridline" /><text x={L - 6} y={py(t) + 3} className="axis" textAnchor="end">{compact(t)}</text></g>)}
        <polygon points={`${px(0)},${py(0)} ${pts} ${px(rows.length - 1)},${py(0)}`} fill="#3987e5" opacity={0.16} />
        <polyline points={pts} fill="none" stroke="#3987e5" strokeWidth={2} />
        {[0, Math.floor(rows.length / 2), rows.length - 1].map((i) => <text key={i} x={px(i)} y={H - 6} className="axis" textAnchor={i === 0 ? "start" : i === rows.length - 1 ? "end" : "middle"}>{rows[i].year}</text>)}
        {hv && <g><line x1={px(hover!)} x2={px(hover!)} y1={T} y2={H - B} stroke="#97A3B3" /><circle cx={px(hover!)} cy={py(hv.population)} r={4} fill="#3987e5" stroke="#030508" strokeWidth={2} /></g>}
      </svg>
      <figcaption>
        <p className="small" aria-live="polite">{hv ? <><b>{hv.year}</b>: about <b>{fmt(hv.population)}</b> people in {fmt(hv.fire_cells)} cells with fire.</> : "Point at the chart to read a year."}</p>
        <button className="link small" onClick={() => setTable(!table)} aria-expanded={table}>{table ? "Hide" : "Show"} as a table</button>
        {table && <div className="scroll"><table className="tbl"><thead><tr><th>Year</th><th>Cells with fire</th><th>People</th><th>Hospitals</th></tr></thead>
          <tbody>{rows.map((r) => <tr key={r.year}><td>{r.year}</td><td className="num">{fmt(r.fire_cells)}</td><td className="num">{fmt(r.population)}</td><td className="num">{fmt(r.hospitals)}</td></tr>)}</tbody></table></div>}
      </figcaption>
    </figure>
  );
}

export default function CasesPage({ regions, online, area }: PageProps) {
  const presets = regions.filter((r) => r.preset);
  const [rid, setRid] = useState("");
  const id = rid || (area && presets.some((r) => r.id === area) ? area : null) || presets[0]?.id || null;
  const info = regions.find((r) => r.id === id);
  const cs = useCases(id, online), ex = useExposure(id, null, online);
  const [all, setAll] = useState<CasebookOverview | null>(null);
  const [filter, setFilter] = useState<CaseVerdict | null>(null);
  const [sel, setSel] = useState<string | null>(null);
  useEffect(() => { if (online) api.casebook().then(setAll).catch(() => setAll(null)); }, [online]);
  useEffect(() => { setSel(null); setFilter(null); }, [id]);

  const data = cs.data, e = ex.data;
  const rows = (data?.cases ?? []).filter((c) => !filter || c.verdict === filter);
  const chosen = data?.cases.find((c) => c.id === sel) ?? null;
  const roadsFailed = (all?.areas ?? []).filter((a) => a.exposure?.errors?.roads).map((a) => a.name);

  return (
    <>
      <PageHead kicker="Casebook" title="Cases & exposure"
        lead="Each fire is checked against other sources: which fires the satellites confirmed, which they missed, and how many people live nearby." />

      {!online ? <Offline what="This page" /> : <>
        <div className="cx-pick">
          {id && <AreaSelect regions={presets.length ? presets : regions} value={id} onChange={setRid} />}
          {info?.story && <p className="muted small">{info.story}</p>}
        </div>

        <div className="cx-stats" aria-live="polite">
          <div className="cx-stat"><span>Fire cases</span><b>{data ? fmt(data.cases.length) : "…"}</b></div>
          <div className="cx-stat"><span>Record missed it</span><b>{data ? fmt(data.counts.agency_only) : "…"}</b></div>
          <div className="cx-stat"><span>People in fire cells</span><b>{e ? compact(e.population) : ex.err ? "–" : "…"}</b></div>
          <div className="cx-stat"><span>Hospitals in them</span><b>{e ? (e.hospitals == null ? "–" : fmt(e.hospitals)) : "…"}</b></div>
          <div className="cx-stat"><span>Schools in them</span><b>{e ? (e.schools == null ? "–" : fmt(e.schools)) : "…"}</b></div>
        </div>

        {cs.err && <p className="muted">No cases for this area yet.</p>}

        {data && info && (
          <section className="cx-wide" aria-labelledby="cx-map-h">
            <h2 id="cx-map-h">Map and cases</h2>
            <div className="cx-split">
              <figure className="cx-fig">
                {e?.map_cells ? <CellMap bbox={info.bbox} cells={e.map_cells} cases={rows} sel={sel} onSel={setSel} /> : <div className="skeleton tall" />}
                {e?.map_cells && (
                  <figcaption className="cx-key">
                    <span className="cx-ramp"><i style={{ background: `linear-gradient(90deg, ${peopleShade(0, 1e6)}, ${peopleShade(1e3, 1e6)}, ${peopleShade(1e6, 1e6)})` }} />lighter cell = more people</span>
                    <span>Each square is an 11 km cell where fire was seen since 2000.</span>
                  </figcaption>
                )}
              </figure>
              <div className="cx-side">
                <VerdictChips counts={data.counts} active={filter} onPick={(v) => { setFilter(v); setSel(null); }} />
                {chosen ? <CaseCard c={chosen} onClose={() => setSel(null)} /> : (
                  <ul className="cp-list tall" aria-label="Cases">
                    {rows.map((c) => <li key={c.id}><button onClick={() => setSel(c.id)}><Icon v={c.verdict} /><span className="t">{c.title}</span><span className="d">{c.date.slice(0, 7)} · {LABEL[c.verdict]}</span></button></li>)}
                  </ul>
                )}
              </div>
            </div>
          </section>
        )}

        {e && (
          <section aria-labelledby="cx-p-h">
            <h2 id="cx-p-h">People, hospitals and schools near fire</h2>
            {e.by_year && e.by_year.length > 1 && <>
              <h3>People living in the cells with fire, each year</h3>
              <PeopleByYear rows={e.by_year} />
            </>}
            {e.top_cells && e.top_cells.length > 0 && <>
              <h3>Places with the most people: look here first</h3>
              <div className="scroll">
                <table className="tbl">
                  <thead><tr><th scope="col">Cell</th><th scope="col">People</th><th scope="col">Months with fire</th><th scope="col">Hospitals</th><th scope="col">Schools</th></tr></thead>
                  <tbody>{e.top_cells.slice(0, 5).map((c) => <tr key={`${c.lat},${c.lon}`}><td className="num">{c.lat.toFixed(1)}°, {c.lon.toFixed(1)}°</td><td className="num">{fmt(c.population)}</td><td className="num">{fmt(c.months_with_fire)}</td><td className="num">{fmt(c.hospitals)}</td><td className="num">{c.schools == null ? "–" : fmt(c.schools)}</td></tr>)}</tbody>
                </table>
              </div>
            </>}
            <p className="muted small">{e.caveat}</p>
          </section>
        )}

        <section aria-labelledby="cx-a-h">
          <h2 id="cx-a-h">About this data</h2>
          <details className="cx-more">
            <summary>What the verdicts mean, and the limits</summary>
            <ul className="plain small">
              <li><b>Five witnesses</b> are asked about each fire: the satellite record, a MODIS-against-VIIRS check, NASA EONET, GDACS and the news. A witness that could not see says so; missing news is never read as "no fire".</li>
              <li><b>All nine areas</b> have cases and exposure. People: WorldPop 2020 (modelled). Hospitals, schools and roads: OpenStreetMap, which maps some places far better than others, so a low count can mean few mappers.</li>
              {roadsFailed.length > 0 && <li><b>Roads are missing</b> for {roadsFailed.join(", ")}: the OpenStreetMap query failed. Shown as "–", never as zero.</li>}
              <li><b>Context, not impact.</b> A cell counts if one detection fell anywhere in its 11 km. There is no fire outline, smoke or spread model.</li>
              <li><b>How it fits the challenge:</b> the cases test the harmonized record against outside sources. Exposure is built on top of the record, not part of it.</li>
            </ul>
          </details>
          {all && (
            <details className="cx-more">
              <summary>All nine areas</summary>
              <div className="scroll">
                <table className="tbl">
                  <thead><tr><th scope="col">Area</th><th scope="col">Cases</th><th scope="col">Record missed it</th><th scope="col">People in fire cells</th><th scope="col">Hospitals</th><th scope="col">Schools</th><th scope="col">Roads</th><th scope="col">Failed sources</th></tr></thead>
                  <tbody>{all.areas.map((a) => (
                    <tr key={a.id} className={a.id === id ? "on" : ""}>
                      <th scope="row"><button className="link" onClick={() => setRid(a.id)}>{a.name}</button></th>
                      <td className="num">{a.cases ? fmt(a.cases.total) : "–"}</td>
                      <td className="num">{a.cases ? fmt(a.cases.counts.agency_only) : "–"}</td>
                      <td className="num">{a.exposure ? compact(a.exposure.population) : "–"}</td>
                      <td className="num">{a.exposure?.hospitals == null ? "–" : fmt(a.exposure.hospitals)}</td>
                      <td className="num">{a.exposure?.schools == null ? "–" : fmt(a.exposure.schools)}</td>
                      <td className="num">{a.exposure?.major_roads == null ? "–" : fmt(a.exposure.major_roads)}</td>
                      <td className="small">{[...(a.cases?.failed_sources ?? []), ...Object.keys(a.exposure?.errors ?? {}).map((k) => `OpenStreetMap ${k}`)].join(", ") || "none"}</td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            </details>
          )}
        </section>
      </>}
    </>
  );
}
