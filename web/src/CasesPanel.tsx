import { CaseVerdict, CasesResponse, FireCase, fmt, periodLabel } from "./api";
import { CaseCard, Icon, LABEL, VerdictChips, compact, useExposure } from "./casebook";

/** Collapsible panel over the Explorer map: the open area's fire cases and who lives where the record shows fire. */
export default function CasesPanel({ name, regionId, online, data, err, filter, onFilter, sel, onSel, onClose, onPage }: {
  name: string | null; regionId: string | null; online: boolean; data: CasesResponse | null; err: string;
  filter: CaseVerdict | null; onFilter: (v: CaseVerdict | null) => void; sel: FireCase | null; onSel: (c: FireCase | null) => void;
  onClose: () => void; onPage: () => void;
}) {
  const ex = useExposure(regionId, sel?.period ?? null, online).data;
  const rows = (data?.cases ?? []).filter((c) => !filter || c.verdict === filter);
  return (
    <aside className="cases-panel" id="cases-panel" aria-label="Cases and exposure">
      <header>
        <div><h2>Cases &amp; exposure</h2>{name && <p>{name}</p>}</div>
        <button className="icon" onClick={onClose} aria-label="Close cases panel">✕</button>
      </header>

      {!regionId ? <p className="muted">Open an area on the map to see its fire cases.</p>
        : !online ? <p className="muted">This needs the Kiln Watch API.</p>
        : err ? <p className="muted">No cases for this area yet.</p>
        : !data ? <div className="skeleton tall" />
        : <>
          <div className="cp-nums">
            <div><b>{fmt(data.cases.length)}</b><span>cases</span></div>
            <div><b>{fmt(data.counts.agency_only)}</b><span>record missed</span></div>
            <div><b>{ex ? compact(ex.population) : "…"}</b><span>{sel ? `people, ${periodLabel(sel.period)}` : "people in fire cells"}</span></div>
          </div>

          {ex && (ex.hospitals != null || ex.schools != null) && (
            <p className="cp-near">{sel ? `In ${periodLabel(sel.period)}, fire was seen in cells with` : "Fire has been seen in cells with"} <b>{ex.hospitals == null ? "–" : fmt(ex.hospitals)} hospitals</b>{ex.schools != null && <> and <b>{fmt(ex.schools)} schools</b></>}.</p>
          )}
          <VerdictChips counts={data.counts} active={filter} onPick={(v) => { onFilter(v); onSel(null); }} />

          {sel ? <>
            <button className="link small cp-back" onClick={() => onSel(null)}>‹ All cases</button>
            <CaseCard c={sel} />
            {ex && <p className="cp-expo">In {periodLabel(sel.period)} fire touched <b>{fmt(ex.fire_cells)}</b> cells where about <b>{compact(ex.population)}</b> people live.</p>}
          </> : (
            <ul className="cp-list">
              {rows.map((c) => (
                <li key={c.id}><button onClick={() => onSel(c)}>
                  <Icon v={c.verdict} /><span className="t">{c.title}</span><span className="d">{c.date.slice(0, 7)} · {LABEL[c.verdict]}</span>
                </button></li>
              ))}
            </ul>
          )}

          <p className="cp-note">Exposure is context, not impact: people living in 11 km cells where fire was detected.</p>
          <button className="btn ghost cp-page" onClick={onPage}>Open the full page ›</button>
        </>}
    </aside>
  );
}
