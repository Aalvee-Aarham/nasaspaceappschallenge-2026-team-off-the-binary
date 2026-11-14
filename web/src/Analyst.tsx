import { Fragment, ReactNode, useEffect, useRef, useState } from "react";
import { AgentReply, api } from "./api";
import Chart, { ChartSpec } from "./Chart";
import Loader, { STEPS } from "./Loader";

type Msg = { role: "user" | "model"; text: string; trace?: AgentReply["trace"]; charts?: ChartSpec[]; error?: boolean; fresh?: boolean; model?: string | null; fallback?: string };

const AREA_SUGGEST = [
  "Is this month unusual here? Show the last 12 weeks.",
  "Did the arrival of VIIRS create a jump in this record? Show raw versus harmonized years.",
  "Which months stand out most, and are there reports for them?",
  "How is this fire year tracking against earlier years?",
];
const WORLD_SUGGEST = [
  "Where on Earth is fire activity running above normal right now, going into the next 30 days?",
  "Brief me on fire activity around Pará, Brazil: last 14 days and the next 30.",
  "Compare Punjab and Rondônia: when does each burn, and how have they changed?",
  "What wildfire news is breaking worldwide this week?",
];

const TOOL_LABEL: Record<string, string> = {
  list_regions: "areas", region_summary: "summary", get_period: "period", find_anomalies: "anomalies", evidence: "evidence",
  reports: "reports", timeline_reports: "news timeline", early_warning: "early warning", check_watchlist: "watchlist",
  find_place: "place lookup", get_outlook: "30-day outlook", query_hotspots: "hotspots", annual_series: "annual series",
  season_profile: "season", compare_areas: "compare", situation_brief: "brief", latest_fire_news: "latest news",
  show_chart: "chart", ui_select_region: "open area", ui_select_period: "open period", ui_set_view: "change view",
};

// ---------- tiny Markdown: headings, lists, bold, italic, code, links; key numbers highlighted ----------

const NUM = /(\b\d[\d,.]*(?:st|nd|rd|th) percentile\b|\b\d[\d,.]*(?:st|nd|rd|th) of \d+\b|×\s?\d+(?:\.\d+)?|\b\d+(?:\.\d+)?×|\b\d+(?:\.\d+)?%)/g;

function highlight(text: string, key: string): ReactNode[] {
  return text.split(NUM).map((t, i) => (i % 2 ? <mark key={`${key}n${i}`} className="hn">{t}</mark> : t));
}

function inline(text: string, key = ""): ReactNode[] {
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\(https?:[^)\s]+\)|(?<![\w*])\*[^*\s][^*]*\*(?!\w)|(?<!\w)_[^_\s][^_]*_(?!\w))/g;
  return text.split(re).map((t, i) => {
    const k = `${key}-${i}`;
    if (i % 2 === 0) return <Fragment key={k}>{highlight(t, k)}</Fragment>;
    if (t.startsWith("**")) return <strong key={k}>{t.slice(2, -2)}</strong>;
    if (t.startsWith("`")) return <code key={k}>{t.slice(1, -1)}</code>;
    if (t.startsWith("[")) {
      const m = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(t)!;
      return <a key={k} href={m[2]} target="_blank" rel="noreferrer">{m[1]}</a>;
    }
    return <em key={k}>{t.slice(1, -1)}</em>;
  });
}

export function Markdown({ text }: { text: string }) {
  const out: ReactNode[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;
  let para: string[] = [];
  const flush = () => {
    if (para.length) out.push(<p key={`p${out.length}`}>{inline(para.join(" "), `p${out.length}`)}</p>);
    para = [];
    if (list) {
      const items = list.items.map((it, j) => <li key={j} style={{ animationDelay: `${j * 60}ms` }}>{inline(it, `l${out.length}-${j}`)}</li>);
      out.push(list.ordered ? <ol key={`o${out.length}`}>{items}</ol> : <ul key={`u${out.length}`}>{items}</ul>);
      list = null;
    }
  };
  for (const raw of text.split("\n")) {
    const line = raw.trimEnd();
    const h = /^#{1,4}\s+(.*)$/.exec(line);
    const ul = /^\s*[-*•]\s+(.*)$/.exec(line);
    const ol = /^\s*\d+[.)]\s+(.*)$/.exec(line);
    if (!line.trim()) { flush(); continue; }
    if (h) { flush(); out.push(<h4 key={`h${out.length}`}>{inline(h[1], `h${out.length}`)}</h4>); continue; }
    if (ul || ol) {
      if (para.length) { const p = para; para = []; out.push(<p key={`p${out.length}`}>{inline(p.join(" "), `p${out.length}`)}</p>); }
      const ordered = !!ol;
      if (list && list.ordered !== ordered) flush();
      list = list ?? { ordered, items: [] };
      list.items.push((ul ?? ol)![1]);
      continue;
    }
    if (list) flush();
    para.push(line.trim());
  }
  flush();
  return <div className="md">{out}</div>;
}

/** The AI assistant's face: a small chatbot with a sparkle, so nobody mistakes its answers for the record itself. */
export function AiAvatar({ size = 28, label }: { size?: number; label?: string }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} className="ai-av" role={label ? "img" : undefined} aria-label={label} aria-hidden={label ? undefined : true}>
      <circle cx="12" cy="12" r="11.5" className="ai-av-bg" />
      <path d="M12 7V4.6" className="ai-av-line" />
      <circle cx="12" cy="4.2" r="1.2" className="ai-av-face" />
      <rect x="5.5" y="7.5" width="13" height="10" rx="3.5" className="ai-av-face" />
      <circle cx="9.6" cy="12" r="1.3" className="ai-av-eye" />
      <circle cx="14.4" cy="12" r="1.3" className="ai-av-eye" />
      <path d="M10.2 15h3.6" className="ai-av-mouth" />
      <path d="M19.5 2.5l.6 1.5 1.5.6-1.5.6-.6 1.5-.6-1.5-1.5-.6 1.5-.6z" className="ai-av-spark" />
    </svg>
  );
}

/** Reveals a fresh answer quickly, as if typed (about 1.5 s whatever its length). */
function useReveal(text: string, on: boolean) {
  const [n, setN] = useState(on ? 0 : text.length);
  useEffect(() => {
    if (!on || matchMedia("(prefers-reduced-motion: reduce)").matches) { setN(text.length); return; }
    let raf = 0;
    const t0 = performance.now(), dur = Math.min(1600, 300 + text.length * 6);
    const tick = (now: number) => {
      const p = Math.min(1, (now - t0) / dur);
      setN(Math.round(text.length * (1 - (1 - p) ** 2)));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [text, on]);
  return n;
}

function Answer({ m }: { m: Msg }) {
  const n = useReveal(m.text, !!m.fresh);
  const done = n >= m.text.length;
  return (
    <>
      <div className="bubble">
        <Markdown text={m.text.slice(0, n)} />
        {!done && <span className="caret" aria-hidden />}
      </div>
      {done && m.charts?.map((c, i) => <Chart key={c.id} spec={c} delay={i * 250} />)}
      {done && m.fallback && <p className="muted small">Gemini was unavailable ({m.fallback}); these are the record's own sentences.</p>}
    </>
  );
}

export default function Analyst(p: {
  enabled: boolean; online: boolean; context: { region_id?: string | null; region_name?: string } & Record<string, unknown>; seed: string | null; onSeedUsed: () => void;
  onActions: (a: AgentReply["actions"]) => void; onClose: () => void; model?: string | null;
}) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [wide, setWide] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  const suggest = p.context.region_id ? AREA_SUGGEST : WORLD_SUGGEST;

  const send = async (q: string) => {
    if (!q.trim() || busy) return;
    const history = msgs.filter((m) => !m.error).map(({ role, text }) => ({ role, text }));
    setMsgs((m) => [...m.map((x) => ({ ...x, fresh: false })), { role: "user", text: q }]);
    setText("");
    setBusy(true);
    try {
      const r = await api.ask(q, history, p.context);
      setMsgs((m) => [...m, { role: "model", text: r.answer, trace: r.trace, charts: r.charts as ChartSpec[] | undefined, fresh: true, model: r.model, fallback: r.fallback }]);
      if (r.actions.length) p.onActions(r.actions);
    } catch (e) {
      setMsgs((m) => [...m, { role: "model", text: (e as Error).message, error: true }]);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (p.seed && !busy) { send(p.seed); p.onSeedUsed(); } // wait for the running answer, never drop the question
  }, [p.seed, busy]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, busy]); // braces: scrollIntoView returns a Promise in new Chrome, which React would call as cleanup

  return (
    <aside className={`analyst ${wide ? "wide" : ""}`} aria-label="AI analyst">
      <header>
        <div className="ahead">
          <AiAvatar size={32} />
          <div>
            <h2>Analyst <span className="ai-tag" title="AI assistant (Google Gemini)">AI</span></h2>
            <span className="muted small">{p.enabled ? `${p.model ?? "Gemini"} · answers only from Kiln Watch tools` : "off"}</span>
          </div>
        </div>
        <div className="row">
          {msgs.length > 0 && <button className="icon small" onClick={() => setMsgs([])} title="New conversation" aria-label="New conversation">⟲</button>}
          <button className="icon small" onClick={() => setWide(!wide)} title={wide ? "Narrow" : "Wider"} aria-label={wide ? "Narrow panel" : "Widen panel"}>{wide ? "›" : "‹"}</button>
          <button className="icon" onClick={p.onClose} aria-label="Close analyst">✕</button>
        </div>
      </header>
      <div className="msgs">
        {!p.online ? <p className="muted">The analyst needs the Kiln Watch API running.</p> : !p.enabled ? (
          <div className="muted">
            <p>The analyst runs on Google Gemini's free tier. To turn it on, create a key at <a href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer">aistudio.google.com/apikey</a>, set <code>GEMINI_API_KEY</code> and restart the API.</p>
            <p>Everything else in Kiln Watch works without it.</p>
          </div>
        ) : msgs.length === 0 && (
          <div className="intro">
            <h3>{p.context.region_name ? `Ask about ${p.context.region_name}` : "Ask about fire anywhere on Earth"}</h3>
            <p className="muted small">I am an AI assistant. Every number comes from Kiln Watch's own tools and every tool call is listed. Charts are drawn from the pipeline, never by the model.</p>
            {suggest.map((s, i) => <button key={s} className="suggest" style={{ animationDelay: `${i * 80}ms` }} onClick={() => send(s)}>{s}</button>)}
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={`msg ${m.role} ${m.error ? "error" : ""}`}>
            {m.role === "model" && <AiAvatar label="AI analyst" />}
            <div className="msg-body">
            {m.role === "model" && m.trace && m.trace.length > 0 && (
              <ol className="chips" aria-label="Tools used">
                {m.trace.map((t, k) => (
                  <li key={k} className={t.ok ? "" : "bad"} style={{ animationDelay: `${k * 70}ms` }} title={`${t.tool}(${Object.values(t.args).join(", ")})`}>
                    {TOOL_LABEL[t.tool] ?? t.tool}
                  </li>
                ))}
              </ol>
            )}
            {m.role === "model" && !m.error ? <Answer m={m} /> : <div className="bubble">{m.text}</div>}
            {m.trace && m.trace.length > 0 && (
              <details className="trace">
                <summary>{m.trace.length} tool call{m.trace.length > 1 ? "s" : ""}{m.model ? ` · ${m.model}` : ""}</summary>
                <ol>{m.trace.map((t, k) => <li key={k} className={t.ok ? "" : "error"}><code>{t.tool}</code> {Object.values(t.args).map(String).join(", ")}</li>)}</ol>
              </details>
            )}
            </div>
          </div>
        ))}
        {busy && <div className="msg model"><AiAvatar label="AI analyst is thinking" /><div className="msg-body"><Loader steps={STEPS.analyst} expected={12} compact /></div></div>}
        <div ref={end} />
      </div>
      <form onSubmit={(e) => { e.preventDefault(); send(text); }}>
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder={p.enabled ? (p.context.region_name ? `Ask about ${p.context.region_name}…` : "Ask about any place…") : "Analyst is off"} disabled={!p.enabled || !p.online || busy} aria-label="Question" maxLength={2000} />
        <button className="btn" disabled={!p.enabled || !p.online || busy || !text.trim()}>Ask</button>
      </form>
    </aside>
  );
}
