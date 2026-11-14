import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useMemo, useRef, useState } from "react";
import { MONTH_SHORT, MONTHS, NearbyPlace, PlaceKind, PlaceLevel, PlaceRisk, apiOrigin, fmt, placeRisk, placeRiskPath } from "./api";
import { PlaceAlert } from "./exposure";
import Loader from "./Loader";

// "Is fire near you?": any place on Earth, in plain words and pictures, for families, students, fire managers and
// safety officers. Every number comes from /api/place-risk. The answer comes in two steps: the fire check first
// (about 10 s), then the schools and hospitals from OpenStreetMap (slower when not cached).

export const LEVEL: Record<PlaceLevel, { word: string; icon: string; color: string; say: string }> = {
  near: { word: "Fire close by", icon: "🔥", color: "#FF5A4F", say: "Satellites saw fire within 5 km this week." },
  watch: { word: "Stay alert", icon: "⚠️", color: "#FF9A3C", say: "Fire was seen in the wider area this week, or this is a time of year when it often burns here." },
  season: { word: "Fire season", icon: "📅", color: "#F6C64F", say: "Fire sometimes happens around here at this time of year." },
  low: { word: "Low right now", icon: "✅", color: "#3DDC97", say: "No fire seen nearby this week, and this is not usually a fire month." },
  unknown: { word: "Could not check", icon: "❔", color: "#97A3B3", say: "The satellite check did not answer. Please try again in a few minutes." },
};
const SCALE: PlaceLevel[] = ["low", "season", "watch", "near"];
export const KIND: Record<PlaceKind, { icon: string; many: string; one: string }> = {
  school: { icon: "🏫", many: "Schools", one: "School" },
  hospital: { icon: "🏥", many: "Hospitals", one: "Hospital" },
  clinic: { icon: "⚕️", many: "Clinics", one: "Clinic" },
  care_home: { icon: "🏠", many: "Care homes", one: "Care home" },
  fire_station: { icon: "🚒", many: "Fire stations", one: "Fire station" },
};
const KINDS = Object.keys(KIND) as PlaceKind[];
const RADII = [5, 10, 25];
const EXAMPLES = ["Ludhiana, India", "Paradise, California", "Sylhet, Bangladesh", "Porto Velho, Brazil", "Canberra, Australia"];
const STEPS = ["Finding the place on the map", "Asking NASA satellites about the last 7 days", "Looking at 23 years of fire history", "Reading the 30-day outlook"];
const OUTLOOK_WORDS: Record<string, string> = {
  watch: "Fire season, and more fire than usual lately", above: "More fire than usual lately",
  season: "Usually a fire season", none: "Usually quiet",
};
const km = (v: number) => (v < 1 ? `${Math.round(v * 1000)} m` : `${fmt(v, v < 10 ? 1 : 0)} km`);
const when = (t: string) => new Date(t.replace(" ", "T") + "Z").toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });

type Target = { q?: string; lat?: number; lon?: number; label?: string };

export default function PlaceRiskCheck({ online, onArea }: { online: boolean; onArea?: (id: string) => void }) {
  const [q, setQ] = useState("");
  const [radius, setRadius] = useState(10);
  const [target, setTarget] = useState<Target | null>(null);
  const [data, setData] = useState<PlaceRisk | null>(null);
  const [fac, setFac] = useState<PlaceRisk["facilities"]>(null);
  const [facErr, setFacErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [facBusy, setFacBusy] = useState(false);
  const [err, setErr] = useState("");
  const latest = useRef(0);   // bumps on every check so a stale answer never overwrites a newer one
  const out = useRef<HTMLDivElement>(null);

  const run = (t: Target, r = radius) => {
    const id = ++latest.current;
    setTarget(t); setBusy(true); setErr(""); setData(null); setFac(null); setFacErr(""); setFacBusy(false);
    requestAnimationFrame(() => out.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
    placeRisk({ ...t, radius_km: r, facilities: false }).then((d) => {
      if (latest.current !== id) return;
      setData(d); setBusy(false); setFacBusy(true);
      const at = { lat: d.place.lat, lon: d.place.lon, label: d.place.name };
      return placeRisk({ ...at, radius_km: r }).then((d2) => {
        if (latest.current !== id) return;
        if (d2.facilities) setFac(d2.facilities); else setFacErr(d2.errors.facilities ?? "The list could not be read.");
      }).catch((e) => latest.current === id && setFacErr(e.message)).finally(() => latest.current === id && setFacBusy(false));
    }).catch((e) => { if (latest.current === id) { setErr(e.message); setBusy(false); } });
  };
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const t = q.trim();
    if (!t) { setErr("Please type the name of a town, village, school or address first."); return; }
    run({ q: t });
  };
  const here = () => {
    if (!navigator.geolocation) { setErr("This browser cannot share your location. Please type your town instead."); return; }
    setErr("");
    navigator.geolocation.getCurrentPosition(
      (p) => { setQ(""); run({ lat: +p.coords.latitude.toFixed(4), lon: +p.coords.longitude.toFixed(4), label: "your location" }); },
      () => setErr("Your location was not shared. Please type your town or village instead."),
      { timeout: 15000, maximumAge: 600000 });
  };
  const pickRadius = (r: number) => { setRadius(r); if (target && !busy) run(data ? { lat: data.place.lat, lon: data.place.lon, label: data.place.name } : target, r); };

  if (!online) return <p className="warn">The fire check needs the Kiln Watch API, which is not answering right now. Please try again in a minute.</p>;

  return (
    <div className="pr">
      <form className="pr-search" onSubmit={submit} role="search">
        <label htmlFor="pr-q" className="pr-ask">Type a town, village, school or address</label>
        <div className="pr-row">
          <input id="pr-q" value={q} onChange={(e) => setQ(e.target.value)} placeholder="For example: Ludhiana, India" autoComplete="off" enterKeyHint="search" />
          <button className="pr-go" type="submit" disabled={busy}>{busy ? "Checking…" : "Check"}</button>
        </div>
        <div className="pr-row pr-opts">
          <button type="button" className="pr-here" onClick={here} disabled={busy}><span aria-hidden>📍</span> Use my location</button>
          <div className="pr-radius" role="group" aria-label="How far around the place to look">
            <span>Look within</span>
            {RADII.map((r) => <button type="button" key={r} className={radius === r ? "on" : ""} aria-pressed={radius === r} onClick={() => pickRadius(r)}>{r} km</button>)}
          </div>
        </div>
        <p className="pr-try">Try: {EXAMPLES.map((x) => <button type="button" key={x} onClick={() => { setQ(x); run({ q: x }); }}>{x}</button>)}</p>
      </form>

      <div ref={out} className="pr-out" aria-live="polite">
        {err && <p className="pr-err" role="alert">{err}</p>}
        {busy && <Loader steps={STEPS} expected={12} title="Checking for fire" />}
        {data && <Result d={data} fac={fac} facBusy={facBusy} facErr={facErr} retryFac={() => run({ lat: data.place.lat, lon: data.place.lon, label: data.place.name })}
          onPick={(c) => { setQ(c.display_name); run({ lat: c.lat, lon: c.lon, label: c.name }); }} onArea={onArea} />}
      </div>
    </div>
  );
}

function Result({ d, fac, facBusy, facErr, retryFac, onPick, onArea }: {
  d: PlaceRisk; fac: PlaceRisk["facilities"]; facBusy: boolean; facErr: string; retryFac: () => void;
  onPick: (c: PlaceRisk["candidates"][number]) => void; onArea?: (id: string) => void;
}) {
  const L = LEVEL[d.level];
  const r = d.recent;
  const month = new Date().getMonth();
  const m0 = d.season?.by_month[month];
  const ol = d.outlook?.class ?? "none";
  const name = d.place.name.split(",")[0];
  return (
    <article className="pr-res">
      <section className={`pr-verdict ${d.level}`} style={{ ["--lv" as string]: L.color }}>
        <div className="pr-icon" aria-hidden>{L.icon}</div>
        <div>
          <p className="pr-word">{L.word}</p>
          <h2 className="pr-head">{d.headline}</h2>
          <p className="pr-where">{d.place.display_name ?? d.place.name} · looking within {d.radius_km} km</p>
        </div>
      </section>
      <ol className="pr-scale" aria-label="Fire level, from low to high">
        {SCALE.map((s) => <li key={s} className={s === d.level ? "on" : ""} style={{ ["--lv" as string]: LEVEL[s].color }} aria-current={s === d.level ? "true" : undefined}>
          <span aria-hidden>{LEVEL[s].icon}</span>{LEVEL[s].word}</li>)}
      </ol>
      {d.candidates.length > 0 && (
        <p className="pr-alt">Not the right place? {d.candidates.map((c) => ({ c, t: c.display_name.split(",").slice(0, 3).join(",") })).filter((x, i, all) => all.findIndex((y) => y.t === x.t) === i).slice(0, 4)
          .map(({ c, t }) => <button key={`${c.lat},${c.lon}`} className="link" onClick={() => onPick(c)}>{t}</button>)}</p>
      )}

      <div className="pr-tiles">
        <div className="pr-tile">
          <span>This week</span>
          {r == null ? <b className="muted">Not checked</b> : r.count === 0 ? <b className="ok">No fire seen</b> : <b className="hot">{fmt(r.count)} {r.count === 1 ? "fire spot" : "fire spots"}</b>}
          <small>{r == null ? "The satellite check did not answer." : r.count === 0 ? `within ${d.radius_km} km, last ${r.days} days` : `closest ${km(r.nearest_km!)} away`}</small>
        </div>
        <div className="pr-tile">
          <span>{m0 ? MONTHS[month] : "This month"} in past years</span>
          {m0 ? <b>{m0.years_with_fire} of {m0.record_years} years</b> : <b className="muted">Not available</b>}
          <small>{m0 ? `had fire within about ${d.season!.within_km} km` : "History could not be read."}</small>
        </div>
        <div className="pr-tile">
          <span>Next 30 days</span>
          <b>{d.errors.outlook ? "Not available" : OUTLOOK_WORDS[ol]}</b>
          <small>what this time of year usually brings</small>
        </div>
      </div>

      <PlaceMap d={d} fac={fac} />
      <p className="pr-key">
        <span><span aria-hidden>📍</span> {name === "your location" ? "You" : name}</span>
        <span><i className="dot fire" /> Fire seen by satellite, last 7 days</span>
        <span><i className="ring" /> {d.radius_km} km around the place</span>
        <span><i className="dot fnear" /> Building within 5 km of a fire</span>
        <span><i className="dot fok" /> Building, no fire close</span>
      </p>

      <section className="pr-sec" aria-labelledby="pr-b-h">
        <h3 id="pr-b-h">Schools, hospitals and care homes nearby</h3>
        {facBusy ? <Loader compact steps={["Asking OpenStreetMap for schools and hospitals", "Measuring how far each one is from the fire"]} expected={30} />
          : facErr ? <p className="pr-err">The list of schools and hospitals could not be loaded ({facErr.replace(/^OpenStreetMap \(Overpass\) did not answer: /, "the map service is busy")}). <button className="link" onClick={retryFac}>Try again</button></p>
          : fac ? <Buildings f={fac} r={d.radius_km} anyFire={(r?.count ?? 0) > 0} /> : null}
      </section>

      {d.season && <Months s={d.season} now={month} />}

      <section className="pr-sec pr-do" aria-labelledby="pr-do-h">
        <h3 id="pr-do-h">What you can do</h3>
        <ul>
          <li><span aria-hidden>📞</span> If you see flames or thick smoke, call your local emergency number. This website is not an official warning.</li>
          <li><span aria-hidden>👀</span> A dot on the map is heat seen from space, a few hours old. Look outside or ask local authorities before acting on it.</li>
          <li><span aria-hidden>🔔</span> Get a message when satellites see fire near this place, or before its usual fire month.</li>
        </ul>
        <PlaceAlert lat={d.place.lat} lon={d.place.lon} label={d.place.name} />
      </section>

      {d.built_area && onArea && (
        <p className="pr-alt">This place is inside a study area with the full 2000–today record: <button className="link" onClick={() => onArea(d.built_area!.id)}>{d.built_area.name} ›</button></p>
      )}

      <details className="cx-more">
        <summary>For fire managers and students: how this is worked out</summary>
        <ul className="plain small">
          {d.reasons.map((x) => <li key={x}>{x}</li>)}
          <li><b>Rule:</b> {d.rule}</li>
          <li><b>This week:</b> NASA FIRMS active fire detections from every satellite (MODIS Terra and Aqua, VIIRS Suomi-NPP, NOAA-20, NOAA-21), confidence-filtered, read live from the public FIRMS mirror{r?.data_through ? `; satellite data through ${r.data_through}` : ""}.</li>
          {d.season && <li><b>Fire months:</b> {d.season.sensor}, {d.season.first_year}–{d.season.last_year}, in the 0.1° cells within about {d.season.within_km} km. One instrument family for every year, so years compare fairly.</li>}
          <li><b>Next 30 days:</b> the worldwide 0.5° climatological outlook on the Aqua MODIS scale (Method page). Not a weather or fire forecast.</li>
          {fac && <li><b>Buildings:</b> {fac.source}{fac.truncated ? ". This is a busy area: the list hit its limit of 3,000, so some may be missing. Try 5 km." : "."}</li>}
          {Object.entries(d.errors).filter(([k]) => k !== "facilities").map(([k, v]) => <li key={k} className="error">Could not read {k}: {v}</li>)}
          <li>{d.caveat}</li>
          <li><b>Use it in your own app:</b> <a href={apiOrigin() + placeRiskPath({ lat: d.place.lat, lon: d.place.lon, radius_km: d.radius_km })} target="_blank" rel="noreferrer"><code>GET /api/place-risk?lat={d.place.lat}&amp;lon={d.place.lon}&amp;radius_km={d.radius_km}</code></a>, or the MCP tool <code>check_place_fire_risk</code> (Connect page).</li>
        </ul>
      </details>
    </article>
  );
}

function Buildings({ f, r, anyFire }: { f: NonNullable<PlaceRisk["facilities"]>; r: number; anyFire: boolean }) {
  const [kind, setKind] = useState<PlaceKind | "all">("all");
  const [all, setAll] = useState(false);
  const rows = f.list.filter((x) => kind === "all" || x.kind === kind);
  const shown = all ? rows : rows.slice(0, 12);
  const total = KINDS.reduce((s, k) => s + f.counts[k], 0);
  const nearTotal = KINDS.reduce((s, k) => s + f.counts_near_fire[k], 0);
  if (!total) return <p>No schools, hospitals, clinics, care homes or fire stations are on the map within {r} km. OpenStreetMap may simply not have them yet.</p>;
  const nearList = KINDS.filter((k) => f.counts_near_fire[k]).map((k) => `${fmt(f.counts_near_fire[k])} ${(f.counts_near_fire[k] === 1 ? KIND[k].one : KIND[k].many).toLowerCase()}`);
  return (
    <>
      <p className={`pr-sum ${nearTotal ? "hot" : ""}`}>
        {nearTotal ? <><span aria-hidden>🔥 </span><b>{nearList.join(", ")}</b> {nearTotal === 1 ? "is" : "are"} within 5 km of a fire seen this week.</>
          : anyFire ? <>Fire was seen this week, but none of these {fmt(total)} places is within 5 km of it.</>
          : <>No fire was seen this week near any of these {fmt(total)} places.</>}
      </p>
      <div className="pr-kinds" role="group" aria-label="Show only">
        <button className={kind === "all" ? "on" : ""} aria-pressed={kind === "all"} onClick={() => setKind("all")}>All · {fmt(total)}</button>
        {KINDS.filter((k) => f.counts[k]).map((k) => (
          <button key={k} className={kind === k ? "on" : ""} aria-pressed={kind === k} onClick={() => setKind(k)}>
            <span aria-hidden>{KIND[k].icon}</span> {KIND[k].many} · {fmt(f.counts[k])}{f.counts_near_fire[k] ? <em> · {fmt(f.counts_near_fire[k])} near fire</em> : null}
          </button>
        ))}
      </div>
      <ul className="pr-list">
        {shown.map((x) => <Building key={`${x.lat},${x.lon},${x.name}`} x={x} />)}
      </ul>
      {rows.length > 12 && <button className="btn ghost" onClick={() => setAll(!all)} aria-expanded={all}>{all ? "Show fewer" : `Show ${fmt(rows.length - 12)} more`}</button>}
      {f.list.length < total && <p className="muted small">The {fmt(f.list.length)} places closest to fire are listed; all {fmt(total)} are counted above.</p>}
    </>
  );
}

function Building({ x }: { x: NearbyPlace }) {
  const L = LEVEL[x.level];
  const close = x.fire_km != null && x.fire_km <= 5;
  return (
    <li style={{ ["--lv" as string]: L.color }} className={close ? "near" : ""}>
      <span className="pr-bi" aria-hidden>{KIND[x.kind].icon}</span>
      <span className="pr-bn"><b>{x.name ?? `${KIND[x.kind].one} (no name on the map)`}</b><small>{KIND[x.kind].one} · {km(x.km)} from the place</small></span>
      <span className={`pr-pill ${close ? "hot" : x.fire_km != null ? "warm" : "ok"}`}>
        {x.fire_km == null ? "No fire this week" : `Fire ${km(x.fire_km)} away`}
      </span>
    </li>
  );
}

function Months({ s, now }: { s: NonNullable<PlaceRisk["season"]>; now: number }) {
  const max = Math.max(1, ...s.by_month.map((m) => m.years_with_fire));
  const busy = [...s.by_month].sort((a, b) => b.years_with_fire - a.years_with_fire).filter((m) => m.years_with_fire > 0).slice(0, 3);
  return (
    <section className="pr-sec" aria-labelledby="pr-m-h">
      <h3 id="pr-m-h">When does fire usually happen here?</h3>
      <p>{busy.length ? <>Most often in <b>{busy.map((m) => MONTHS[m.month - 1]).join(", ")}</b>. Each bar shows in how many of the last {s.last_year - s.first_year + 1} years fire was seen within about {s.within_km} km in that month.</>
        : <>Fire was not seen within about {s.within_km} km in any month of the last {s.last_year - s.first_year + 1} years.</>}</p>
      <ol className="pr-months">
        {s.by_month.map((m, i) => (
          <li key={m.month} className={i === now ? "now" : ""} title={`${MONTHS[i]}: fire in ${m.years_with_fire} of ${m.record_years} years`}>
            <b>{m.years_with_fire || ""}</b>
            <i style={{ height: `${(m.years_with_fire / max) * 100}%`, opacity: m.years_with_fire ? 0.35 + 0.65 * m.share : 0 }} />
            <span>{MONTH_SHORT[i]}{i === now && <em>now</em>}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

const STYLE = "https://tiles.openfreemap.org/styles/positron";

function circle(lat: number, lon: number, r: number) {
  const k = Math.cos((lat * Math.PI) / 180);
  return Array.from({ length: 65 }, (_, i) => {
    const a = (i / 64) * 2 * Math.PI;
    return [lon + (r / 111.32) * Math.sin(a) / k, lat + (r / 111.32) * Math.cos(a)];
  });
}

/** A light street map: the place, the search circle, this week's fire detections and the buildings around it. */
function PlaceMap({ d, fac }: { d: PlaceRisk; fac: PlaceRisk["facilities"] }) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const [ready, setReady] = useState(false);
  const { lat, lon } = d.place;
  const fires = useMemo(() => ({
    type: "FeatureCollection" as const,
    features: (d.recent?.detections ?? []).map((x) => ({ type: "Feature" as const, geometry: { type: "Point" as const, coordinates: [x.lon, x.lat] },
      properties: { t: `${when(x.time_utc)}, ${x.time_utc.slice(11)} UTC · ${x.satellite} · ${km(x.km)} from the place` } })),
  }), [d]);

  useEffect(() => {
    const m = new maplibregl.Map({ container: el.current!, style: STYLE, center: [lon, lat], zoom: 10, scrollZoom: false, attributionControl: { compact: true } });
    map.current = m;
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    m.on("load", () => setReady(true));
    return () => { m.remove(); map.current = null; setReady(false); };
  }, []);   // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    const ring = circle(lat, lon, d.radius_km);
    const facs = {
      type: "FeatureCollection" as const,
      features: (fac?.list ?? []).map((x) => ({ type: "Feature" as const, geometry: { type: "Point" as const, coordinates: [x.lon, x.lat] },
        properties: { near: x.fire_km != null && x.fire_km <= 5 ? 1 : 0, name: x.name ?? `${KIND[x.kind].one} (no name on the map)`,
          t: `${KIND[x.kind].icon} ${KIND[x.kind].one} · ${x.fire_km == null ? "no fire seen this week" : `fire seen ${km(x.fire_km)} away`}` } })),
    };
    const data = { ring: { type: "Feature" as const, geometry: { type: "Polygon" as const, coordinates: [ring] }, properties: {} }, fires, facs };
    for (const [id, g] of Object.entries(data)) {
      const src = m.getSource(id) as maplibregl.GeoJSONSource | undefined;
      if (src) src.setData(g as GeoJSON.GeoJSON); else m.addSource(id, { type: "geojson", data: g as GeoJSON.GeoJSON });
    }
    if (!m.getLayer("ring")) {
      // Buildings under the fire dots: the fire is what must never be hidden. Popups are built as text (OSM names are user data).
      const pop = (title: string, line: string, at: maplibregl.LngLatLike) => {
        const el = document.createElement("div");
        const b = document.createElement("b");
        b.textContent = title;
        el.append(b, document.createElement("br"), line);
        new maplibregl.Popup({ offset: 8 }).setLngLat(at).setDOMContent(el).addTo(m);
      };
      m.addLayer({ id: "ring", type: "fill", source: "ring", paint: { "fill-color": "#00A1FF", "fill-opacity": 0.06 } });
      m.addLayer({ id: "ring-l", type: "line", source: "ring", paint: { "line-color": "#00A1FF", "line-width": 2, "line-dasharray": [2, 2] } });
      m.addLayer({ id: "facs", type: "circle", source: "facs", paint: { "circle-radius": ["interpolate", ["linear"], ["zoom"], 9, 3.5, 14, 8], "circle-color": "#FFFFFF",
        "circle-stroke-color": ["case", ["==", ["get", "near"], 1], "#FF3B2F", "#7D8896"], "circle-stroke-width": 2.5 } });
      m.addLayer({ id: "fire-glow", type: "circle", source: "fires", paint: { "circle-radius": 16, "circle-color": "#FF3B2F", "circle-opacity": 0.2, "circle-blur": 0.6 } });
      m.addLayer({ id: "fire", type: "circle", source: "fires", paint: { "circle-radius": 7, "circle-color": "#FF3B2F", "circle-stroke-color": "#FFE1A8", "circle-stroke-width": 2 } });
      m.on("click", "fire", (e) => { const f = e.features?.[0]; if (f) pop("Fire seen by satellite", f.properties.t, e.lngLat); });
      m.on("click", "facs", (e) => { const f = e.features?.[0]; if (f && !m.queryRenderedFeatures(e.point, { layers: ["fire"] }).length) pop(f.properties.name, f.properties.t, e.lngLat); });
      for (const l of ["fire", "facs"]) {
        m.on("mouseenter", l, () => { m.getCanvas().style.cursor = "pointer"; });
        m.on("mouseleave", l, () => { m.getCanvas().style.cursor = ""; });
      }
    }
    const b = new maplibregl.LngLatBounds();
    ring.forEach((p) => b.extend(p as [number, number]));
    m.fitBounds(b, { padding: 24, duration: 600 });
  }, [ready, lat, lon, d.radius_km, fires, fac]);

  useEffect(() => {   // the place itself
    const m = map.current;
    if (!m || !ready) return;
    const pin = document.createElement("div");
    pin.className = "pr-pin";
    pin.textContent = "📍";
    const mk = new maplibregl.Marker({ element: pin, anchor: "bottom" }).setLngLat([lon, lat]).addTo(m);
    return () => { mk.remove(); };
  }, [ready, lat, lon]);

  return <div ref={el} className="pr-map" role="region" aria-label={`Map of ${d.place.name}: ${d.recent?.count ?? 0} fire spots this week and the buildings around it`} />;
}
