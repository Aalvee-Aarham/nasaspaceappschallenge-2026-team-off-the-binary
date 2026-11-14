import { ReactNode, RefObject, useEffect, useState } from "react";
import Lenis from "lenis";
import { Level, LEVEL_LABEL, PlaceCandidate, Region, RegionItem, api } from "../api";

export type Page = "home" | "explore" | "warning" | "after" | "cases" | "bangladesh" | "news" | "download" | "create" | "method" | "mcp" | "n8n";
/** Every routable page (hash links); `PAGES` is the shorter top-bar list. */
export const ALL_PAGES: readonly Page[] = ["home", "explore", "warning", "after", "cases", "method", "bangladesh", "mcp", "n8n", "news", "download", "create"];
export const PAGES: readonly (readonly [Page, string])[] = [
  ["explore", "Explorer"], ["warning", "Early warning"], ["after", "After MODIS"], ["cases", "Cases & exposure"],
  ["method", "Proof"], ["bangladesh", "Bangladesh"], ["mcp", "Connect"],
];

export type PageProps = {
  regions: RegionItem[]; online: boolean; go: (p: Page) => void; openRegion: (id: string) => void; refresh: () => void;
  area?: string | null;   // the area open in the Explorer, if any
};

/** Alerts have no accounts yet: the secret token is the key, remembered in this browser only. */
const KEY = "kw.alerts";
export type Saved = { token: string; name: string };
export function savedAlerts(): Saved[] {
  try { return JSON.parse(localStorage.getItem(KEY) ?? "[]"); } catch { return []; }
}
export function saveAlerts(list: Saved[]) {
  try { localStorage.setItem(KEY, JSON.stringify(list)); } catch { /* private mode: alert still works through n8n */ }
}

export function PageHead({ kicker, title, lead, children }: { kicker: string; title: string; lead: string; children?: ReactNode }) {
  return (
    <header className="page-head">
      <div><p className="kicker">{kicker}</p><h1>{title}</h1></div>
      <div><p className="lead">{lead}</p>{children}</div>
    </header>
  );
}

/** Eased wheel scrolling for a scrollable page; nested scroll areas keep their own wheel. */
export function useSmoothScroll(ref: RefObject<HTMLElement | null>, key: unknown) {
  useEffect(() => {
    const el = ref.current;
    if (!el || !el.firstElementChild || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const lenis = new Lenis({ wrapper: el, content: el.firstElementChild as HTMLElement, autoRaf: true, lerp: 0.1,
      prevent: (n) => n.classList.contains("scroll") || n.tagName === "PRE" || n.tagName === "SELECT" });
    return () => lenis.destroy();
  }, [ref, key]);
}

export const LevelChip = ({ level }: { level: Level }) => <span className={`lvl ${level}`}>{LEVEL_LABEL[level]}</span>;

/** Loads a region's JSON bundle; keeps the previous choice stable while another loads. */
export function useRegion(id: string | null) {
  const [region, setRegion] = useState<Region | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    setRegion(null); setErr(null);
    if (!id) return;
    let live = true;
    api.region(id).then((r) => live && setRegion(r)).catch((e) => live && setErr(e.message));
    return () => { live = false; };
  }, [id]);
  return { region, err };
}

export function AreaSelect({ regions, value, onChange }: { regions: RegionItem[]; value: string; onChange: (id: string) => void }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} aria-label="Area">
      {regions.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
    </select>
  );
}

/** Copy-able code block. */
export function Code({ text }: { text: string }) {
  const [done, setDone] = useState(false);
  const copy = () => {
    const copy = navigator.clipboard?.writeText(text);
    copy?.then(() => { setDone(true); setTimeout(() => setDone(false), 1500); }).catch(() => undefined);
  };
  return (
    <div className="codeblock">
      <pre><code>{text}</code></pre>
      <button className="btn ghost" onClick={copy}>{done ? "Copied" : "Copy"}</button>
    </div>
  );
}

export const Offline = ({ what }: { what: string }) => (
  <p className="warn small">{what} needs the Kiln Watch API. Start it with <code>uvicorn kw.api:app --port 8000</code> in <code>server/</code>.</p>
);

/** Any place on Earth: search a name, type coordinates, or draw on the map. Boxes are 0.5 to 4 degrees, 16 square degrees at most. */
export function AreaPicker({ online, cta, busy, onPick, onDraw }: {
  online: boolean; cta: string; busy?: boolean; onPick: (box: number[], name?: string) => void; onDraw?: () => void;
}) {
  const [q, setQ] = useState("");
  const [box, setBox] = useState(["", "", "", ""]);
  const [name, setName] = useState("");
  const [msg, setMsg] = useState("");
  const [searching, setSearching] = useState(false);
  const [candidates, setCandidates] = useState<PlaceCandidate[]>([]);
  const [selIdx, setSelIdx] = useState<number | null>(null);
  const n = box.map(Number);
  const valid = box.every((v) => v.trim() !== "" && Number.isFinite(+v)) && n[1] < n[3] && n.every((v, i) => Math.abs(v) <= (i % 2 ? 90 : 180));
  const width = n[0] <= n[2] ? n[2] - n[0] : n[2] + 360 - n[0];
  const area = valid ? width * (n[3] - n[1]) : 0;

  const pickCandidate = (c: PlaceCandidate, idx: number) => {
    setSelIdx(idx);
    setBox(c.bbox.map((v) => v.toFixed(2)));
    setName(c.name);
    setMsg("");
  };

  const find = async (e: React.FormEvent) => {
    e.preventDefault();
    setMsg("");
    setCandidates([]);
    setSelIdx(null);
    const query = q.trim();
    if (!query) {
      setMsg("Please enter a place or address first (e.g. Mirpur, Dhaka).");
      return;
    }
    setSearching(true);
    try {
      const res = await api.findPlace(query);
      if (!res.found || !res.bbox) {
        setMsg(`No place called “${query}”. Try adding city or country, e.g. “${query}, Dhaka”.`);
        return;
      }
      const cands = res.candidates && res.candidates.length ? res.candidates : [
        { name: res.name ?? query, display_name: res.display_name ?? res.name ?? query, country: res.country, country_code: res.country_code, lat: res.lat ?? 0, lon: res.lon ?? 0, bbox: res.bbox, places: res.places }
      ];
      setCandidates(cands);
      pickCandidate(cands[0], 0);
    } catch {
      // Fallback: direct Nominatim call if backend is offline
      try {
        const r = await fetch(`https://nominatim.openstreetmap.org/search?format=jsonv2&limit=6&addressdetails=1&q=${encodeURIComponent(query)}`,
                              { signal: AbortSignal.timeout(8000) });
        const list = await r.json();
        if (!list || !list.length) { setMsg(`No place called “${query}”.`); return; }
        const cl = (v: number) => Math.min(4, Math.max(0.5, v));
        const cands: PlaceCandidate[] = list.map((p: any) => {
          const [s, nn, w, ea] = p.boundingbox.map(Number);
          const [hw, hh, lat, lon] = [cl(ea - w) / 2, cl(nn - s) / 2, (s + nn) / 2, (w + ea) / 2];
          const disp = String(p.display_name);
          const nm = disp.split(",").slice(0, 2).join(",").trim();
          return {
            name: nm,
            display_name: disp,
            country: p.address?.country,
            country_code: p.address?.country_code,
            lat, lon,
            bbox: [Math.max(-180, lon - hw), Math.max(-90, lat - hh), Math.min(180, lon + hw), Math.min(90, lat + hh)],
          };
        });
        setCandidates(cands);
        pickCandidate(cands[0], 0);
      } catch {
        setMsg("Place search is unavailable. You can enter the coordinates directly below.");
      }
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="picker">
      <form className="row" onSubmit={find} role="search">
        <input className="grow" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search place or address, e.g. Mirpur, Dhaka or Cerrado, Brazil" aria-label="Search a place" />
        <button className="btn ghost" disabled={searching}>{searching ? "Finding…" : "Find"}</button>
        {onDraw && <button type="button" className="btn ghost" onClick={onDraw} disabled={!online}>Draw on the map</button>}
      </form>
      {msg && <p className="error small">{msg}</p>}

      {candidates.length > 1 && (
        <div style={{ marginTop: 10, marginBottom: 10 }}>
          <div className="small muted" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
            <span>Found <b>{candidates.length} matching places</b>. Click to choose yours:</span>
            <span className="small muted">or search more specifically (e.g. “{q.trim()}, Dhaka”)</span>
          </div>
          <div style={{ display: "grid", gap: 6, maxHeight: "200px", overflowY: "auto", paddingRight: 4 }}>
            {candidates.map((c, i) => {
              const active = selIdx === i;
              return (
                <button
                  key={i}
                  type="button"
                  onClick={() => pickCandidate(c, i)}
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "flex-start",
                    textAlign: "left",
                    padding: "7px 10px",
                    background: active ? "var(--raised-2)" : "var(--raised)",
                    border: `1px solid ${active ? "var(--focus)" : "var(--line)"}`,
                    borderRadius: "var(--radius-m)",
                    cursor: "pointer",
                    color: "var(--text)",
                    transition: "border-color .15s, background .15s",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", width: "100%", alignItems: "center" }}>
                    <span style={{ fontWeight: active ? 700 : 600, color: active ? "var(--focus)" : "var(--text)" }}>
                      {active ? "✓ " : ""}{c.name}
                    </span>
                    {c.country && <span className="tag" style={{ margin: 0, fontSize: "11px" }}>{c.country}</span>}
                  </div>
                  <span className="muted small" style={{ fontSize: "12px", marginTop: 2, lineHeight: 1.3 }}>
                    {c.display_name}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {candidates.length === 1 && (
        <p className="muted small" style={{ margin: "6px 0 8px" }}>
          <b>Matched:</b> {candidates[0].display_name}
        </p>
      )}

      <form onSubmit={(e) => { e.preventDefault(); if (valid && area <= 16) onPick(n, name.trim() || undefined); }}>
        <div className="coord-grid">
          {(["West", "South", "East", "North"] as const).map((l, i) => (
            <label key={l}>{l}<input inputMode="decimal" value={box[i]} placeholder={["88.0", "23.0", "89.5", "24.5"][i]} onChange={(e) => setBox(box.map((v, j) => (j === i ? e.target.value : v)))} /></label>
          ))}
        </div>
        <label className="field">Name (optional)<input value={name} onChange={(e) => setName(e.target.value)} maxLength={80} placeholder="Brick kilns north of Dhaka" /></label>
        {valid && <p className={area > 16 ? "error small" : "muted small"}>{area > 16 ? `This box is ${area.toFixed(1)} square degrees; use one up to 16.` : `About ${Math.round(area * 12100).toLocaleString()} km².`}</p>}
        <button className="btn" disabled={!online || !valid || area > 16 || busy}>{busy ? "Working…" : cta}</button>
      </form>
    </div>
  );
}
