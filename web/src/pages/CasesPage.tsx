import { useEffect, useState } from "react";
import { CaseVerdict, CasebookOverview, api, fmt } from "../api";
import { CaseCard, CellMap, Icon, LABEL, VerdictChips, compact, peopleShade, useCases, useExposure } from "../casebook";
import { FarmSection, PeopleSection, PlaceCheck } from "../exposure";
import { AreaSelect, Offline, PageHead, PageProps } from "./shared";

export default function CasesPage({ regions, online, area }: PageProps) {
  const presets = regions.filter((r) => r.preset);
  const [rid, setRid] = useState("");
  const id = rid || (area && presets.some((r) => r.id === area) ? area : null) || presets[0]?.id || null;
  const info = regions.find((r) => r.id === id);
  const cs = useCases(id, online), ex = useExposure(id, null, online);
  const [all, setAll] = useState<CasebookOverview | null>(null);
  const [filter, setFilter] = useState<CaseVerdict | null>(null);
  const [sel, setSel] = useState<string | null>(null);
  const [place, setPlace] = useState<{ lat: number; lon: number; label: string; n: number } | null>(null);
  const [side, setSide] = useState<"cases" | "people">("cases");
  const [hi, setHi] = useState<[number, number] | null>(null);
  const check = (lat: number, lon: number, label: string) => {
    setPlace((p) => ({ lat, lon, label, n: (p?.n ?? 0) + 1 }));
    requestAnimationFrame(() => document.getElementById("ex-place")?.scrollIntoView({ behavior: "smooth", block: "start" }));
  };
  useEffect(() => { if (online) api.casebook().then(setAll).catch(() => setAll(null)); }, [online]);
  useEffect(() => { setSel(null); setFilter(null); setPlace(null); setSide("cases"); setHi(null); }, [id]);

  const data = cs.data, e = ex.data;
  const rows = (data?.cases ?? []).filter((c) => !filter || c.verdict === filter);
  const chosen = data?.cases.find((c) => c.id === sel) ?? null;
  const roadsFailed = (all?.areas ?? []).filter((a) => a.exposure?.errors?.roads).map((a) => a.name);

  return (
    <>
      <PageHead kicker="Exposure" title="Cases & exposure"
        lead="Who lives, learns and farms where fire is detected: people, schools, hospitals and farmland in every 11 km cell that has had fire since 2000." />

      {!online ? <Offline what="This page" /> : <>
        <div className="cx-pick">
          {id && <AreaSelect regions={presets.length ? presets : regions} value={id} onChange={setRid} />}
          {info?.story && <p className="muted small">{info.story}</p>}
        </div>

        {info && (
          <section className="cx-wide" aria-labelledby="cx-map-h">
            <h2 id="cx-map-h">Where fire meets people</h2>
            <div className="cx-split">
              <figure className="cx-fig">
                {e?.map_cells ? <CellMap fill={0.8} bbox={info.bbox} cells={e.map_cells} cases={side === "cases" ? rows : []} hi={hi} sel={sel} onSel={setSel} onCell={(la, lo) => check(la, lo, `Cell ${(la - 0.05).toFixed(1)}°, ${(lo - 0.05).toFixed(1)}°`)} /> : ex.err ? <p className="muted">No exposure data for this area yet.</p> : <div className="skeleton tall" />}
              </figure>
              <div className="cx-side"><div className="cx-side-in">
                {e && <p className="small cx-sum">Fire was detected in <b>{fmt(e.fire_cells)}</b> cells here, home to about <b>{compact(e.population)}</b> people, <b>{e.schools == null ? "–" : fmt(e.schools)}</b> schools and <b>{e.hospitals == null ? "–" : fmt(e.hospitals)}</b> hospitals.</p>}
                <div className="cx-panel">
                  <div className="cx-tabs" role="tablist" aria-label="What the map shows">
                    <button role="tab" aria-selected={side === "cases"} className={side === "cases" ? "on" : ""} onClick={() => { setSide("cases"); setHi(null); }}>Fire cases{data ? ` · ${fmt(data.cases.length)}` : ""}</button>
                    <button role="tab" aria-selected={side === "people"} className={side === "people" ? "on" : ""} onClick={() => { setSide("people"); setSel(null); }}>Most people</button>
                  </div>
                  {side === "cases" ? <>
                    <p className="muted small">Known fires, checked against NASA EONET, GDACS and the news.{data && data.counts.agency_only > 0 && <> The satellite record missed <b>{fmt(data.counts.agency_only)}</b>.</>}</p>
                    {cs.err ? <p className="muted small">No cases for this area yet.</p> : !data ? <div className="skeleton" /> : <>
                      <VerdictChips counts={data.counts} active={filter} onPick={(v) => { setFilter(v); setSel(null); }} />
                      {chosen ? <CaseCard c={chosen} onClose={() => setSel(null)} /> : (
                        <ul className="cp-list" aria-label="Cases">
                          {rows.map((c) => <li key={c.id}><button onClick={() => setSel(c.id)}><Icon v={c.verdict} /><span className="t">{c.title}</span><span className="d">{c.date.slice(0, 7)} · {LABEL[c.verdict]}</span></button></li>)}
                        </ul>
                      )}
                    </>}
                  </> : <>
                    <p className="muted small">Cells with fire where the most people live. Point at one to find it on the map; click for its fire history.</p>
                    {e?.top_cells?.length ? (
                      <ul className="cp-list" aria-label="Cells with the most people" onMouseLeave={() => setHi(null)}>
                        {e.top_cells.slice(0, 10).map((c) => (
                          <li key={`${c.lat},${c.lon}`}><button onMouseEnter={() => setHi([c.lat, c.lon])} onFocus={() => setHi([c.lat, c.lon])}
                            onClick={() => check(c.lat + 0.05, c.lon + 0.05, `Cell ${c.lat.toFixed(1)}°, ${c.lon.toFixed(1)}°`)}>
                            <span className="cx-rank">{compact(c.population)}</span><span className="t">people in cell {c.lat.toFixed(1)}°, {c.lon.toFixed(1)}°</span>
                            <span className="d">fire in {fmt(c.months_with_fire)} months · {c.schools == null ? "–" : fmt(c.schools)} {c.schools === 1 ? "school" : "schools"} · {fmt(c.hospitals)} {c.hospitals === 1 ? "hospital" : "hospitals"}</span>
                          </button></li>
                        ))}
                      </ul>
                    ) : <p className="muted small">No populated cells with fire here.</p>}
                  </>}
                </div>
              </div></div>
            </div>
            {e?.map_cells && (
              <p className="cx-key">
                <span className="cx-ramp"><i style={{ background: `linear-gradient(90deg, ${peopleShade(0, 1e6)}, ${peopleShade(1e3, 1e6)}, ${peopleShade(1e6, 1e6)})` }} />brighter cell = more people</span>
                <span>Each square is an 11 km cell where fire was seen since 2000. Click one for its fire history.</span>
              </p>
            )}
          </section>
        )}

        {e && (
          <section aria-labelledby="cx-p-h">
            <h2 id="cx-p-h">For families: people, schools and hospitals near fire</h2>
            <PeopleSection key={id ?? ""} e={e} onCheck={check} />
          </section>
        )}

        {e && (
          <section aria-labelledby="cx-c-h">
            <h2 id="cx-c-h">For farm owners: fire on farmland</h2>
            <FarmSection f={e.farmland} fireCells={e.fire_cells} onCheck={check} />
          </section>
        )}

        {e && info && id && (
          <section aria-labelledby="cx-x-h">
            <h2 id="cx-x-h">Check your place</h2>
            <PlaceCheck regionId={id} bbox={info.bbox} target={place} />
          </section>
        )}

        <section aria-labelledby="cx-a-h">
          <h2 id="cx-a-h">About this data</h2>
          <details className="cx-more">
            <summary>What the verdicts mean, and the limits</summary>
            <ul className="plain small">
              <li><b>Six witnesses</b> are asked about each fire: the satellite record, a MODIS-against-VIIRS check, NASA EONET, GDACS, MODIS burned area and the news. A witness that could not look says so and gives the reason (a failed search, GDELT before 2017, GDACS before 2021); missing news is never read as "no fire".</li>
              <li><b>Farmland:</b> ESA WorldCover 2021 cropland, one year of land cover. It does not say what was growing the month of a fire, and fire on farmland is often residue burning by the farmers themselves.</li>
              <li><b>Where an event meets the record.</b> An EONET or GDACS point is one spot on a fire that can span several cells, so it is matched to hotspots in its 11 km cell and the 8 around it, in the event month and the next. Burned area is the burn scar MODIS mapped in the same block; it is guided by MODIS hotspots, so it is not fully independent of the record.</li>
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
