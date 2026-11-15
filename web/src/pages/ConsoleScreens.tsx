import { useEffect, useState } from "react";
import { LEVEL_LABEL, Warning, ordinal } from "../api";

// The home console's phone: an n8n alert replay over the early-warning capture. Everything shown comes from the API:
// the early-warning payload for one built area and a real past elevated month. It replays each time `play` turns on.

export type ConsoleData = { w: Warning; prior: [number, number][]; sentence: string | null };

/** Milliseconds since `play` turned on; 0 while off. */
function useClock(play: boolean) {
  const [t, setT] = useState(0);
  useEffect(() => {
    if (!play) { setT(0); return; }
    const t0 = performance.now();
    let id = 0;
    const tick = () => { const e = performance.now() - t0; setT(e); if (e < 9000) id = requestAnimationFrame(tick); };
    id = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(id);
  }, [play]);
  return t;
}
const ramp = (t: number, from: number, dur: number) => { const x = Math.min(1, Math.max(0, (t - from) / dur)); return 1 - (1 - x) ** 3; };
const monthName = (period: string) => new Date(period + "-01T00:00:00Z").toLocaleDateString("en", { month: "long", timeZone: "UTC" });

/** A real past month of the area that would have been "elevated" (month percentile ≥ 90, the warning rule), from monthly.json. */
export type PastAlert = { name: string; period: string; ratio: number; rank: number; n: number };

/** A phone that buzzes with the n8n alert: a replay of a real past elevated month, then today's live check. */
export function Phone({ d, past, play }: { d: ConsoleData | null; past: PastAlert | null; play: boolean }) {
  const t = useClock(play), now = new Date();
  const m = d?.w.month, ratio = m ? m.value / m.median_same_days : null;
  const card = (at: number) => ({ opacity: ramp(t, at, 350), transform: `translateY(${(1 - ramp(t, at, 600)) * -120}%) scale(${0.92 + 0.08 * ramp(t, at, 600)})` });
  return (
    <div className={`phone ${t > 1900 && t < 2500 ? "buzz" : ""}`}>
      <div className="ph-scr">
        <p className="ph-time">{now.toLocaleTimeString("en", { hour: "2-digit", minute: "2-digit", hour12: false })}</p>
        <p className="ph-date">{now.toLocaleDateString("en", { weekday: "long", day: "numeric", month: "long" })}</p>
        {past && (
          <div className="ph-n hot" style={card(1900)}>
            <p className="ph-app"><i />Kiln Watch · n8n<span>alert</span></p>
            <b>Elevated</b>
            <em>{past.name}</em>
            <p>{monthName(past.period)} {past.period.slice(0, 4)}: {past.ratio.toFixed(1)}× the usual {monthName(past.period)}. {past.rank === 1 ? "Highest" : `${ordinal(past.rank)} highest`} of {past.n} years.</p>
            <small>Replay of a real past month</small>
          </div>
        )}
        {d && m && ratio !== null && (
          <div className="ph-n" style={card(3300)}>
            <p className="ph-app"><i />Kiln Watch · today<span>now</span></p>
            <b>{LEVEL_LABEL[d.w.level]}</b>
            <em>{d.w.name}</em>
            <p>{monthName(m.period)} so far: {ratio.toFixed(2)}× the usual. {ratio > 1 && m.value >= 5 ? "Alert sent." : "No alert needed."}</p>
          </div>
        )}
      </div>
    </div>
  );
}

