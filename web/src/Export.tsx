import { useEffect, useMemo, useState } from "react";
import { ExportOptions, api } from "./api";

type Kind = "calendar" | "detections";
const day = (ms: number) => new Date(ms).toISOString().slice(0, 10);

/** Download an area (a preset or one drawn on the map): pick the table, the format, the dates and the columns. */
export default function ExportPanel({ id, name, years, dataThrough, online, onClose }: {
  id: string; name: string; years: [number, number]; dataThrough: string; online: boolean; onClose?: () => void;
}) {
  const [opt, setOpt] = useState<ExportOptions | null>(null);
  const [err, setErr] = useState("");
  const [kind, setKind] = useState<Kind>("calendar");
  const [fmt, setFmt] = useState("csv");
  const [gran, setGran] = useState("month");
  const [off, setOff] = useState<Record<Kind, string[]>>({ calendar: [], detections: [] });   // groups switched off
  const [y0, setY0] = useState(years[0]);
  const [y1, setY1] = useState(years[1]);
  const [d1, setD1] = useState(dataThrough);
  const [d0, setD0] = useState(day(Date.parse(dataThrough) - 30 * 86400000));
  const [comments, setComments] = useState(true);
  const [usedOnly, setUsedOnly] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => { api.exportOptions().then(setOpt).catch((e) => setErr(e.message)); }, []);

  const groups = opt ? (kind === "calendar" ? opt.calendar.groups : opt.detections.groups) : [];
  const keep = groups.filter((g) => !off[kind].includes(g.key));
  const ncols = keep.reduce((n, g) => n + g.columns.length, 0) + (kind === "calendar" ? 1 : 0);
  const days = (Date.parse(d1) - Date.parse(d0)) / 86400000;
  const maxDays = opt?.detections.max_days ?? 366;
  const problem = !online ? "The Kiln Watch API is offline." : !keep.length ? "Choose at least one column group."
    : kind === "calendar" && y0 > y1 ? "The first year is after the last year."
    : kind === "detections" && !(days >= 0 && days <= maxDays) ? `Choose 1 to ${maxDays} days.` : "";

  const url = useMemo(() => {
    const q: Record<string, string> = { kind, format: fmt };
    if (keep.length < groups.length) q.columns = keep.map((g) => g.key).join(",");
    if (kind === "calendar") {
      q.granularity = gran;
      if (y0 !== years[0]) q.start = String(y0);
      if (y1 !== years[1]) q.end = String(y1);
    } else {
      q.start = d0; q.end = d1;
      if (usedOnly) q.used_only = "true";
    }
    if (fmt !== "json" && !comments) q.comments = "false";
    return api.exportUrl(id, q);
  }, [id, kind, fmt, gran, y0, y1, d0, d1, usedOnly, comments, keep.length, groups.length, years]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggle = (k: string) => setOff((o) => ({ ...o, [kind]: o[kind].includes(k) ? o[kind].filter((x) => x !== k) : [...o[kind], k] }));
  const copy = () => navigator.clipboard?.writeText(url).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500); }).catch(() => undefined);
  const yrs = Array.from({ length: years[1] - years[0] + 1 }, (_, i) => years[0] + i);

  return (
    <section className="export" aria-label={`Download ${name}`}>
      <div className="row spread">
        <h3>Download this area</h3>
        {onClose && <button className="icon small" onClick={onClose} aria-label="Close download options">✕</button>}
      </div>
      {err && <p className="error small">Download options unavailable: {err}</p>}
      {opt && <>
        <div className="ctl">
          <span className="ctl-l">What</span>
          <div className="seg" role="radiogroup" aria-label="What to download">
            {([["calendar", "Calendar"], ["detections", "Detections"]] as const).map(([k, l]) => (
              <button key={k} role="radio" aria-checked={kind === k} className={kind === k ? "on" : ""} onClick={() => setKind(k)}>{l}</button>
            ))}
          </div>
          <span className="muted small">{kind === "calendar" ? "One row per month or week: harmonized hotspots, history and quality flags." : "One row per satellite detection, up to a year."}</span>
        </div>

        <div className="ctl-grid">
          <label className="ctl"><span className="ctl-l">Format</span>
            <select value={fmt} onChange={(e) => setFmt(e.target.value)}>
              {opt.formats.map((f) => <option key={f.key} value={f.key}>{f.key.toUpperCase()}</option>)}
            </select>
          </label>
          {kind === "calendar" ? <>
            <label className="ctl"><span className="ctl-l">Step</span>
              <select value={gran} onChange={(e) => setGran(e.target.value)}>
                <option value="month">Monthly</option><option value="week">Weekly</option>
              </select>
            </label>
            <label className="ctl"><span className="ctl-l">From year</span>
              <select value={y0} onChange={(e) => setY0(+e.target.value)}>{yrs.map((y) => <option key={y}>{y}</option>)}</select>
            </label>
            <label className="ctl"><span className="ctl-l">To year</span>
              <select value={y1} onChange={(e) => setY1(+e.target.value)}>{yrs.map((y) => <option key={y}>{y}</option>)}</select>
            </label>
          </> : <>
            <label className="ctl"><span className="ctl-l">From</span>
              <input type="date" value={d0} min="2000-11-01" max={d1} onChange={(e) => setD0(e.target.value)} />
            </label>
            <label className="ctl"><span className="ctl-l">To</span>
              <input type="date" value={d1} min={d0} max={dataThrough} onChange={(e) => setD1(e.target.value)} />
            </label>
          </>}
        </div>
        <p className="muted small">{opt.formats.find((f) => f.key === fmt)?.label}</p>

        <fieldset className="cols">
          <legend>Columns <span className="muted small">({ncols} selected{kind === "calendar" ? "; period is always included" : ""})</span></legend>
          <div className="row">
            <button className="linkish" onClick={() => setOff((o) => ({ ...o, [kind]: [] }))}>All</button>
            <button className="linkish" onClick={() => setOff((o) => ({ ...o, [kind]: groups.map((g) => g.key) }))}>None</button>
          </div>
          {groups.map((g) => (
            <label key={g.key} className="colg">
              <input type="checkbox" checked={!off[kind].includes(g.key)} onChange={() => toggle(g.key)} />
              <span>{g.label}<span className="muted small colnames">{g.columns.join(", ")}</span></span>
            </label>
          ))}
        </fieldset>
        {kind === "calendar" && !off.calendar.includes("raw") && <p className="warn small">Raw counts rise whenever a satellite is added. Use the Aqua-scale columns for trends.</p>}

        <div className="row opts">
          {fmt !== "json" && <label className="chk"><input type="checkbox" checked={comments} onChange={(e) => setComments(e.target.checked)} /> Provenance as # comment lines</label>}
          {kind === "detections" && <label className="chk" title={opt.detections.used_only}><input type="checkbox" checked={usedOnly} onChange={(e) => setUsedOnly(e.target.checked)} /> Only rows the calendar used</label>}
        </div>

        <div className="row">
          <a className="btn" href={problem ? undefined : url} download aria-disabled={!!problem} style={problem ? { opacity: 0.45, pointerEvents: "none" } : undefined}>Download {fmt.toUpperCase()}</a>
          <button className="btn ghost" onClick={copy} disabled={!!problem}>{copied ? "Copied" : "Copy API link"}</button>
        </div>
        {problem && <p className="error small">{problem}</p>}
        <p className="muted small">The same file is available over the API (the link above) and through MCP (<code>export_data</code>).</p>
      </>}
    </section>
  );
}
