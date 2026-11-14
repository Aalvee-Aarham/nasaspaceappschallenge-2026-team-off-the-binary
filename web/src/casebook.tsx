import { useEffect, useId, useState } from "react";
import { CaseVerdict, CasesResponse, ExposureResponse, FireCase, SHORT, api, fmt } from "./api";

// One model of the casebook for every place it appears: the Explorer panel, the Cases & exposure page and the home
// console. Plain words, one shape and one colour per kind of verdict, so it reads the same everywhere.

// Colour carries one job, the kind of verdict: three categorical slots validated all-pairs for colour-blind readers on
// the dark surface (blue, orange, aqua) and a neutral grey. Every verdict also has its own shape and is always named.
export type Group = "agree" | "missed" | "sat" | "other";
export const COLOR: Record<Group, string> = { agree: "#3987e5", missed: "#d95926", sat: "#199e70", other: "#898781" };
export const GROUP_OF: Record<CaseVerdict, Group> = {
  corroborated: "agree", agency_only: "missed", satellite_only: "sat", reported: "other", abstained: "other", insufficient: "other",
};
export const VERDICTS: CaseVerdict[] = ["corroborated", "agency_only", "satellite_only", "reported", "abstained", "insufficient"];
export const LABEL: Record<CaseVerdict, string> = {
  corroborated: "Confirmed", agency_only: "Record missed it", satellite_only: "Satellites only",
  reported: "News only", abstained: "Could not see", insufficient: "No evidence",
};
export const MEANING: Record<CaseVerdict, string> = {
  corroborated: "Satellites saw fire at or next to the place, and an agency record or a burn scar confirms it.",
  agency_only: "An agency or burn-scar record shows a fire. The satellite record shows none in that cell, its 8 neighbours or the next month.",
  satellite_only: "Satellites saw fire. No source that could look mentions it.",
  reported: "News mentions a fire. No agency or burn-scar record.",
  abstained: "No satellite was watching that month.",
  insufficient: "No fire seen and nothing reported by a source that could look.",
};
export const compact = (v: number | null | undefined) => (v == null ? "–" : v >= 1e6 ? `${fmt(v / 1e6, 1)} M` : v >= 1e4 ? `${fmt(v / 1e3, 0)} k` : fmt(v));

/** A verdict marker: colour plus shape, never colour alone. */
export function Mark({ v, x, y, r = 5, sel = false }: { v: CaseVerdict; x: number; y: number; r?: number; sel?: boolean }) {
  const g = GROUP_OF[v], c = COLOR[g], sw = { stroke: "#030508", strokeWidth: 1.5 };
  const ring = sel ? <circle cx={x} cy={y} r={r + 4} fill="none" stroke="#F1F4F8" strokeWidth={2} /> : null;
  if (g === "missed") return <g>{ring}<path d={`M${x} ${y - r * 1.3}L${x + r * 1.3} ${y}L${x} ${y + r * 1.3}L${x - r * 1.3} ${y}Z`} fill={c} {...sw} /></g>;
  if (g === "sat") return <g>{ring}<rect x={x - r} y={y - r} width={r * 2} height={r * 2} rx={1.5} fill={c} {...sw} /></g>;
  if (g === "other") return <g>{ring}<circle cx={x} cy={y} r={r - 0.75} fill="#030508" stroke={c} strokeWidth={2.5} /></g>;
  return <g>{ring}<circle cx={x} cy={y} r={r} fill={c} {...sw} /></g>;
}
export const Icon = ({ v, size = 14 }: { v: CaseVerdict; size?: number }) => (
  <svg width={size} height={size} aria-hidden className="cb-ico"><Mark v={v} x={size / 2} y={size / 2} r={size * 0.3} /></svg>
);

/** Verdict chips: a legend, and a filter when onPick is given. Only verdicts that occur are shown. */
export function VerdictChips({ counts, active, onPick }: { counts: Record<CaseVerdict, number>; active?: CaseVerdict | null; onPick?: (v: CaseVerdict | null) => void }) {
  const shown = VERDICTS.filter((v) => counts[v] > 0);
  if (!onPick) return <ul className="cb-chips">{shown.map((v) => <li key={v}><span><Icon v={v} />{LABEL[v]} <b>{counts[v]}</b></span></li>)}</ul>;
  return (
    <div className="cb-chips" role="group" aria-label="Show only one kind of case">
      {shown.map((v) => (
        <button key={v} className={active === v ? "on" : ""} aria-pressed={active === v} onClick={() => onPick(active === v ? null : v)} title={MEANING[v]}>
          <Icon v={v} />{LABEL[v]} <b>{counts[v]}</b>
        </button>
      ))}
    </div>
  );
}

/** Cases of one area from the API; null while loading. */
export function useCases(id: string | null, online: boolean) {
  const [data, setData] = useState<CasesResponse | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    setData(null); setErr("");
    if (!id || !online) return;
    let live = true;
    api.cases(id).then((d) => live && setData(d)).catch((e) => live && setErr(e.message));
    return () => { live = false; };
  }, [id, online]);
  return { data, err };
}

/** Exposure of one area, for one month or (period null) every month with fire. */
export function useExposure(id: string | null, period: string | null, online: boolean) {
  const [data, setData] = useState<ExposureResponse | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    setData(null); setErr("");
    if (!id || !online) return;
    let live = true;
    api.exposure(id, period ?? undefined).then((d) => live && setData(d)).catch((e) => live && setErr(e.message));
    return () => { live = false; };
  }, [id, period, online]);
  return { data, err };
}

/** What each witness said about one case, in plain words. */
export function CaseCard({ c, onClose }: { c: FireCase; onClose?: () => void }) {
  const { satellite: s, cross_family: x, agency, disaster_system: d, press, burned_area: b } = c.witnesses;
  const gap = c.witnesses.unavailable ?? {};
  type St = "fire" | "quiet" | "abstain" | "none" | "blind";
  // "blind" = the witness could not look (its search failed or does not reach back that far): never shown as "nothing found"
  const said = (state: St) => ({ fire: "saw fire", quiet: "saw no fire", abstain: "could not see", none: "nothing found", blind: "could not look" })[state];
  const where = ({ cell: "in this 11 km cell", neighbour: "in a neighbouring cell", cell_next_month: "in this cell the next month", neighbour_next_month: "in a neighbouring cell the next month" } as const)[s.match ?? "cell"];
  const rows: [string, St, React.ReactNode][] = [
    ["Satellites", s.state, s.state === "fire" ? `${fmt(s.match_hotspots ?? s.cell_hotspots, 1)} hotspots ${where}` : s.state === "quiet" ? "no hotspots in this cell, its 8 neighbours or the next month" : "no satellite was watching"],
    ["NASA EONET", agency ? "fire" : gap.agency ? "blind" : "none", agency ? <>event on {agency.date}{agency.url && <> · <a href={agency.url} target="_blank" rel="noreferrer">record ↗</a></>}</> : gap.agency ?? "no event record"],
    ["GDACS", d ? "fire" : gap.disaster_system ? "blind" : "none", d ? <>{d.alert ? `${d.alert} alert` : "alert"}{d.burned_area_ha != null && `, ${fmt(d.burned_area_ha)} ha burned`}{d.url && <> · <a href={d.url} target="_blank" rel="noreferrer">report ↗</a></>}</> : gap.disaster_system ?? "no alert"],
    ["Burned area", b ? "fire" : gap.burned_area ? "blind" : "none", b ? `${fmt(b.km2, 1)} km² burn scar mapped by MODIS in this cell and its 8 neighbours` : gap.burned_area ?? "no burn scar mapped there that month"],
    ["News", press ? "fire" : gap.press ? "blind" : "none", press ? <>{fmt(press.count)} articles{press.sample_urls?.[0] && <> · <a href={press.sample_urls[0]} target="_blank" rel="noreferrer">example ↗</a></>}</> : gap.press ?? "no articles found"],
    ["MODIS vs VIIRS", x.state, x.state === "abstain" ? (x.reason ?? "not checked") : x.agrees === false ? "the two satellite families disagree" : "the two satellite families agree"],
  ];
  return (
    <article className="cb-card" aria-live="polite">
      <header>
        <Icon v={c.verdict} size={18} />
        <div><b>{LABEL[c.verdict]}</b><span>{MEANING[c.verdict]}</span></div>
        {onClose && <button className="icon" onClick={onClose} aria-label="Close case">✕</button>}
      </header>
      <h4>{c.title}</h4>
      <p className="cb-when">{c.date} · {c.lat.toFixed(2)}°, {c.lon.toFixed(2)}°</p>
      <ul className="cb-wit">{rows.map(([n, st, t]) => <li key={n} className={st}><span>{n}</span><em>{said(st)}</em><small>{t}</small></li>)}</ul>
      {s.state !== "abstain" && <p className="cb-foot">This month the whole area had {fmt(s.area_hotspots)} hotspots{s.percentile != null && `, more than ${fmt(s.percentile, 0)}% of years`}. Satellites: {s.sensors.map((k) => SHORT[k] ?? k).join(", ") || "–"}.</p>}
      {c.verdict === "agency_only" && <p className="cb-foot">The fire may be too small to detect, just outside the cell, or in a gap in the record.</p>}
    </article>
  );
}

/** The area's fire cells shaded by people living there, with the cases on top. `reveal` (0–1) animates the markers in. */
export function CellMap({ bbox, cells, cases, sel, onSel, onCell, reveal = 1, label, hi, fill }: {
  bbox: number[]; cells: [number, number, number, number][]; cases: FireCase[]; sel?: string | null; onSel?: (id: string) => void;
  onCell?: (lat: number, lon: number) => void; reveal?: number; label?: string; hi?: [number, number] | null;   // hi: SW corner of a cell to outline
  fill?: number;   // fill: a fixed height/width box every area is stretched into (cells then are not square); omitted, the area keeps its true shape
}) {
  const clip = `cb-clip${useId().replace(/:/g, "")}`;
  const [w, s, e, n] = bbox;
  const W = 560, k = Math.cos(((s + n) / 2) * Math.PI / 180), H = Math.round(fill ? W * fill : W * (n - s) / ((e - w) * k));
  const x = (lon: number) => ((lon - w) / (e - w)) * W, y = (lat: number) => ((n - lat) / (n - s)) * H;
  const max = Math.max(1, ...cells.map((c) => c[2]));
  const cw = (0.1 / (e - w)) * W + 0.4, ch = (0.1 / (n - s)) * H + 0.4;
  const shown = Math.round(cases.length * reveal);
  const order = cases.slice(0, shown).sort((a, b) => (a.id === sel ? 1 : 0) - (b.id === sel ? 1 : 0));
  return (
    // Size the box to the area's own shape: width shrinks so a tall area fits the height cap without empty side bands.
    <svg viewBox={`0 0 ${W} ${H}`} className="cb-map" style={{ aspectRatio: `${W} / ${H}`, ["--ar" as string]: (W / H).toFixed(4) }} role="img" aria-label={label ?? `Map: ${cells.length} cells that have had fire, lighter where more people live, and ${cases.length} cases.`}>
      <defs><clipPath id={clip}><rect width={W} height={H} /></clipPath></defs>
      <g clipPath={`url(#${clip})`}>{/* cells on the bbox edge are cut at the border, never drawn outside it */}
      <rect width={W} height={H} fill="#0A0E15" />
      {/* Real ground under the cells for orientation: NASA Blue Marble shaded relief for the exact bbox (plate carrée, so it lines up with x/y). */}
      <image href={reliefImage(bbox, W * 2, H * 2)} width={W} height={H} preserveAspectRatio="none" opacity={0.55} />
      <rect width={W} height={H} fill="#05080D" opacity={0.35} />
      {cells.map(([la, lo, p], i) => <rect key={i} x={x(lo)} y={y(la + 0.1)} width={cw} height={ch} fill={peopleShade(p, max)}
        stroke="rgba(241,244,248,0.22)" strokeWidth={0.5}
        className={onCell ? "cb-cell" : undefined} onClick={onCell ? () => onCell(la + 0.05, lo + 0.05) : undefined} />)}
      {hi && <rect x={x(hi[1]) - 2} y={y(hi[0] + 0.1) - 2} width={cw + 4} height={ch + 4} fill="none" stroke="#F1F4F8" strokeWidth={2.5} pointerEvents="none" />}
      {order.map((c) => (
        <g key={c.id} className={onSel ? "cb-pt" : undefined} onClick={onSel ? () => onSel(c.id) : undefined}>
          {onSel && <circle cx={x(c.lon)} cy={y(c.lat)} r={12} fill="transparent" />}
          <Mark v={c.verdict} x={x(c.lon)} y={y(c.lat)} sel={c.id === sel} />
          <title>{`${c.date} · ${c.title} · ${LABEL[c.verdict]}`}</title>
        </g>
      ))}
      </g>
    </svg>
  );
}
/** One neutral ramp for people, kept apart from the verdict colours: more people, brighter veil over the ground (log scale).
 *  Even an empty cell keeps a visible floor, so "fire was seen here" never disappears into the basemap. */
export const peopleShade = (p: number, max: number) => { const t = Math.log10(p + 1) / Math.log10(max + 1); return `rgba(241,244,248,${(0.1 + t * 0.6).toFixed(3)})`; };
/** One GIBS WMS image (EPSG:4326) covering exactly this bbox. */
const reliefImage = ([w, s, e, n]: number[], width: number, height: number) =>
  `https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi?SERVICE=WMS&REQUEST=GetMap&VERSION=1.1.1&LAYERS=BlueMarble_ShadedRelief_Bathymetry&STYLES=&FORMAT=image/jpeg&SRS=EPSG:4326&BBOX=${w},${s},${e},${n}&WIDTH=${Math.round(width)}&HEIGHT=${Math.round(height)}`;
