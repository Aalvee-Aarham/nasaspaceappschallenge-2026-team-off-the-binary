import { useEffect, useState } from "react";
import { KilnEvidence, Num, api, fmt } from "../api";
import { compact, useExposure } from "../casebook";
import { PageHead, PageProps, useRegion } from "./shared";

// ponytail: English only. A Bangla toggle needs strings written or reviewed by a native speaker; add { en, bn } here then.
export default function Bangladesh({ go, openRegion, online }: PageProps) {
  const { region, err } = useRegion("dhaka-kilns");
  const [k, setK] = useState<KilnEvidence | null>(null);
  const [kerr, setKerr] = useState("");
  useEffect(() => {
    if (!online) return;
    let live = true;
    api.kilns("dhaka-kilns").then((x) => live && setK(x)).catch((e) => live && setKerr(e.message));
    return () => { live = false; };
  }, [online]);
  const ex = useExposure("dhaka-kilns", null, online).data;
  const m = region?.meta;
  const st = m?.steps.VIIRS_SNPP;

  return (
    <>
      <PageHead kicker="Local impact" title="Bangladesh" lead="The brick-kiln belt around Dhaka: thousands of small, steady fires. NASA's fire product sees only a few of them, so Kiln Watch counts kilns from a published kiln map and checks it against night lights." />
      {err && <p className="error">{err}</p>}
      {!region && !err && <div className="skeleton tall" />}
      {region && m && (
        <>
          <section>
            <h2>Why Dhaka</h2>
            <p>When VIIRS arrived in {st?.period.slice(0, 4)}, raw detection counts here rose to <b>{times(st?.raw_all_sensors_excess)}</b> what Aqua MODIS alone would imply, while the harmonized record changed by <b>{times(st?.harmonized_excess)}</b>. Without harmonizing, a change of satellite looks like a change of fire. That matters most here, where the sharper sensor picks up many small, steady heat sources.</p>
            <p className="muted small">{m.story}</p>
          </section>

          <section>
            <h2>Counting kilns without FIRMS</h2>
            {kerr && <p className="muted">The kiln evidence is not available here: {kerr}</p>}
            {online && !k && !kerr && <div className="skeleton tall" />}
            {k && <Kilns k={k} />}
          </section>

          {ex && (
            <section>
              <h2>Who lives where fire is seen</h2>
              <div className="cx-stats">
                <div className="cx-stat"><span>Cells with fire since 2000</span><b>{fmt(ex.fire_cells)}</b></div>
                <div className="cx-stat"><span>People living in them</span><b>{compact(ex.population)}</b></div>
                <div className="cx-stat"><span>Hospitals</span><b>{ex.hospitals == null ? "–" : fmt(ex.hospitals)}</b></div>
                <div className="cx-stat"><span>Schools</span><b>{ex.schools == null ? "–" : fmt(ex.schools)}</b></div>
              </div>
              <p className="muted small">People (WorldPop 2020, modelled), hospitals and schools (OpenStreetMap) inside the 11 km cells where the harmonized record shows any vegetation-fire detection since 2000. Around Dhaka those cells include the city, so this is context, not the number of people affected by fire or by kiln smoke. {ex.caveat}</p>
            </section>
          )}

          <section>
            <h2>What you can do with it</h2>
            <p className="row">
              <button className="btn" onClick={() => openRegion("dhaka-kilns")}>Open the Dhaka calendar</button>
              <button className="btn ghost" onClick={() => go("cases")}>Cases &amp; exposure</button>
              <button className="btn ghost" onClick={() => go("download")}>Download the CSV</button>
            </p>
          </section>
        </>
      )}
    </>
  );
}

const times = (v: Num | undefined) => (v == null ? "–" : `×${fmt(v, 1)}`);
const pc = (v: Num | undefined) => (v == null ? "–" : `${fmt(v, 0)}%`);

function Kilns({ k }: { k: KilnEvidence }) {
  const f = k.firms, nl = k.night_lights, inv = k.inventory;
  const seen = k.kilns.filter((r) => r[4] && r[5] > 0).length, labelled = k.kilns.filter((r) => r[4]).length;
  return (
    <>
      <p>A kiln is a small, steady heat source. In the {f.season[0].slice(0, 4)}–{f.season[1].slice(2, 4)} dry season NASA FIRMS flagged a VIIRS hotspot within {f.viirs_radius_m} m of only <b>{pc(f.mapped_kilns.viirs_any_pct)}</b> of the {fmt(f.mapped_kilns.n)} mapped kilns, and a MODIS hotspot within {fmt(f.modis_radius_m / 1000)} km of <b>{pc(f.mapped_kilns.modis_any_pct)}</b>. Random places away from kilns scored {pc(f.random_places.viirs_any_pct)} and {pc(f.random_places.modis_any_pct)}. So the fire product cannot count kilns, and Kiln Watch does not use it to.</p>

      <div className="cx-stats">
        <div className="cx-stat"><span>Mapped kilns here</span><b>{fmt(inv.n_on_labelled_kiln)}</b></div>
        <div className="cx-stat"><span>With a VIIRS hotspot</span><b>{pc(f.mapped_kilns.viirs_any_pct)}</b></div>
        <div className="cx-stat"><span>With a MODIS hotspot</span><b>{pc(f.mapped_kilns.modis_any_pct)}</b></div>
        <div className="cx-stat"><span>Heat sources on a kiln</span><b>{fmt(f.static_sources.within_500m_of_mapped_kiln)} of {fmt(f.static_sources.n)}</b></div>
      </div>

      <KilnMap k={k} />
      <p className="muted small">Each dot is a kiln structure seen in Sentinel-2 imagery. Orange: FIRMS also saw a VIIRS hotspot within {f.viirs_radius_m} m that season ({fmt(seen)} of {fmt(labelled)} on a labelled kiln). Blue: it did not. Hollow grey: detected but not on a human-labelled kiln, so less certain. Diamonds: the FIRMS persistent heat sources.</p>
      <p>Only <b>{fmt(f.static_sources.within_500m_of_mapped_kiln)} of the {fmt(f.static_sources.n)}</b> FIRMS persistent heat sources lie within 500 m of a mapped kiln ({fmt(f.static_sources.within_1km_of_mapped_kiln)} within 1 km). An earlier version of Kiln Watch labelled them "likely kilns"; the inventory does not support that, so they are now called persistent heat sources.</p>

      <h3>Night lights: a second, independent witness</h3>
      <p>Kilns fire in the dry months with lamps and night shifts, and stand idle in the monsoon. NASA Black Marble should therefore read brighter at a kiln from December to February than in July and August. {nl.mapped_kilns_rural.n ? <>Away from city lights, across {fmt(nl.mapped_kilns_rural.n)} mapped kilns the median dry-to-monsoon brightness ratio is <b>{nl.mapped_kilns_rural.median_ratio}</b>, against <b>{nl.random_rural.median_ratio}</b> for random places; <b>{pc(nl.mapped_kilns_rural.above_random_75th_pct)}</b> of kilns are above the random 75th percentile (25% would be chance). That is a consistent sign of kiln season, not proof: kilns sit on town edges that also brighten in the dry season.</> : "Too few kilns away from city lights to say."}</p>
      <p className="muted small">{nl.note} Source: {nl.band}.</p>

      {k.radar && <>
        <h3>Radar: a third witness</h3>
        <p>Brick stacks fill a kiln's yard in the dry months; in the monsoon the yard stands empty or flooded. Sentinel-1 radar sees that as a change in how much a kiln stands out from the ground around it. From the monsoon to the dry season, a mapped kiln's contrast with its surroundings rose by a median <b>{fmt(k.radar.mapped_kilns.median_rise_db, 2)} dB</b>, against <b>{fmt(k.radar.random_places.median_rise_db, 2)} dB</b> at random places; <b>{pc(k.radar.mapped_kilns.rise_above_random_75th_pct)}</b> of kilns are above the random 75th percentile (25% would be chance).</p>
        <p className="muted small">{k.radar.contrast}; {k.radar.collection}, {k.radar.orbit}, {k.radar.scenes.kiln_season} dry-season and {k.radar.scenes.monsoon} monsoon scenes. {k.radar.note}</p>
      </>}

      <h3>What this does not tell you</h3>
      <ul className="plain small">
        <li><b>Structures, not firing.</b> {inv.not_seen}</li>
        <li><b>Not all are kilns.</b> {inv.precision}</li>
        <li><b>Inventory:</b> <a href={inv.url} target="_blank" rel="noreferrer">{inv.source}</a>, licence {inv.license} (non-commercial). Night lights: NASA Black Marble VNP46A2. Radar: ESA Copernicus Sentinel-1. FIRMS: NASA, via the same archive as the rest of Kiln Watch.</li>
      </ul>
    </>
  );
}

function KilnMap({ k }: { k: KilnEvidence }) {
  const [w, s, e, n] = k.bbox;
  const W = 560, c = Math.cos(((s + n) / 2) * Math.PI / 180), H = Math.round(W * (n - s) / ((e - w) * c));
  const x = (lon: number) => ((lon - w) / (e - w)) * W, y = (lat: number) => ((n - lat) / (n - s)) * H;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="cb-map" role="img"
      aria-label={`Map of ${k.kilns.length} kiln structures around Dhaka, coloured by whether NASA FIRMS also saw a VIIRS hotspot, and ${k.static_sources.length} FIRMS persistent heat sources.`}>
      <rect width={W} height={H} fill="#0A0E15" />
      {k.kilns.filter((r) => !r[4]).map((r, i) => <circle key={`u${i}`} cx={x(r[0])} cy={y(r[1])} r={1.8} fill="none" stroke="#898781" strokeWidth={0.8} />)}
      {k.kilns.filter((r) => r[4] && r[5] === 0).map((r, i) => <circle key={`n${i}`} cx={x(r[0])} cy={y(r[1])} r={2.2} fill="#3987e5" />)}
      {k.kilns.filter((r) => r[4] && r[5] > 0).map((r, i) => <circle key={`s${i}`} cx={x(r[0])} cy={y(r[1])} r={2.6} fill="#d95926" stroke="#030508" strokeWidth={0.6} />)}
      {k.static_sources.map((r, i) => {
        const cx = x(r[0]), cy = y(r[1]);
        return <path key={`h${i}`} d={`M${cx} ${cy - 5}L${cx + 5} ${cy}L${cx} ${cy + 5}L${cx - 5} ${cy}Z`} fill="none" stroke="#C9A2F2" strokeWidth={1.4}><title>{`FIRMS persistent heat source, ${fmt(r[2])} detections, ${fmt(r[3])} m from the nearest mapped kiln`}</title></path>;
      })}
    </svg>
  );
}
