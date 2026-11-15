import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { Block, Events, Meta, api } from "../api";
import { JumpChart, PixelCard, ValidateChart } from "./StoryCharts";
import { BEATS, mountScene, SceneHandle } from "./scene";
import { mountStory, Story } from "./story";
import { Page, PageProps, SECTIONS } from "./shared";
import "./home.css";

// Cinematic landing page: a deck of beats (story.ts) over one 3D scene (scene.ts). Beat i shows keyframe i of
// scene.ts, so the order of B below must match the KF order there.
// Every number here is read from the pipeline's meta.json files; nothing is typed in.
const B = { hero: 0, old: 1, sharp: 2, jump: 3, fix: 4, proof: 5, farm: 6, connect: 7, go: 8 };
const LAST = BEATS - 1;
console.assert(B.go === LAST, "Home.tsx beats and scene.ts keyframes are out of step");

// scroll per beat, in screen heights: short, so the story moves quickly (story.ts glides on to whole beats)
const STEP = 0.8;

const num = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const median = (xs: number[]) => {
  const s = [...xs].sort((a, b) => a - b), n = s.length;
  return n ? (n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2) : null;
};
const fx = (v: number | null | undefined, d = 2) => (num(v) ? v.toFixed(d) : "…");

function summarize(ms: Meta[]) {
  const first = (k: string) => ms.map((m) => m.sensors[k]?.first).filter(Boolean).sort()[0];
  const through = ms.map((m) => m.data_through).sort().pop()!;
  const step = (f: "raw_all_sensors_excess" | "harmonized_excess") => median(ms.map((m) => m.steps.VIIRS_SNPP?.[f]).filter(num));
  const den = ms.map((m) => m.denial.modis_ends_2016).filter((d) => num(d?.ours_seasonal_eb.spearman));
  return {
    statics: ms.reduce((a, m) => a + m.totals.static_detections, 0),
    areas: ms.length,
    sats: new Set(ms.flatMap((m) => Object.keys(m.sensors)).filter((k) => k !== "MODIS")).size,
    since: first("MODIS"), through, snpp: first("VIIRS_SNPP"),
    raw: step("raw_all_sensors_excess"), harm: step("harmonized_excess"),
    nStep: ms.filter((m) => num(m.steps.VIIRS_SNPP?.harmonized_excess)).length,
    rho: median(den.map((d) => d.ours_seasonal_eb.spearman as number)), rhoN: den[0]?.n, rhoTest: den[0]?.test,
  };
}

/** "since 2012", or "2012–2026" once the sensor's last detection is more than 3 days before the record's end (the
 *  ended rule of scripts/readme_figures.mjs). Measured from the data, never a typed end date. */
function span(ms: Meta[], k: string) {
  const firsts = ms.map((m) => m.sensors[k]?.first).filter(Boolean).sort(), lasts = ms.map((m) => m.sensors[k]?.last).filter(Boolean).sort();
  if (!firsts.length) return "";
  const last = lasts[lasts.length - 1], through = ms.map((m) => m.data_through).sort().pop()!;
  return Date.parse(through) - Date.parse(last) > 3 * 864e5 ? ` · ${firsts[0].slice(0, 4)}–${last.slice(0, 4)}, ended` : ` · since ${firsts[0].slice(0, 4)}`;
}

// home menu: the in-app top bar's five items (shared.tsx SECTIONS; the Explorer also has its own button)
const NAV = SECTIONS.map(([l, [[k]]]) => [k, l] as const);

// the MCP server's size: 40 @mcp.tool functions in server/kw/mcp_server.py, 5 of them PUBLIC_WRITE_TOOLS that the public
// HTTP connector drops (35 left). No endpoint reports it, so it is a constant: recount when tools are added.
const MCP_TOOLS = 40, MCP_HTTP_TOOLS = 35;

/** Big numbers count up the first time they scroll into view. */
function countUp(root: HTMLElement, scroller: HTMLElement) {
  const ctx = gsap.context(() => {
    root.querySelectorAll<HTMLElement>("[data-count]").forEach((el) => {
      const v = +el.dataset.count!, dec = +(el.dataset.dec ?? 0);
      const f = (x: number) => x.toLocaleString("en", { minimumFractionDigits: dec, maximumFractionDigits: dec });
      const o = { v: 0 };
      el.textContent = f(0);
      gsap.to(o, { v, duration: 2, ease: "power3.out", onUpdate: () => { el.textContent = f(o.v); },
        scrollTrigger: { trigger: el, scroller, start: "top 90%", once: true } });
    });
  }, root);
  ScrollTrigger.refresh();
  return () => ctx.revert();
}

const Count = ({ v, dec = 0 }: { v: number | null | undefined; dec?: number }) =>
  num(v) ? <span data-count={v} data-dec={dec}>{v.toLocaleString("en", { minimumFractionDigits: dec, maximumFractionDigits: dec })}</span> : <span>…</span>;

/** Words that rise out of their own mask when their beat arrives (story.ts animates `.w > span`). Keep the word count
 *  the same between renders: story.ts wires the spans once. */
const W = ({ children }: { children: string }) => (
  <>{children.split(" ").map((w, i) => <Fragment key={i}>{i > 0 && " "}<span className="w"><span>{w}</span></span></Fragment>)}</>
);
const H = ({ lines, tag: T = "h2", cls = "", at = 0 }: { lines: string[]; tag?: "h1" | "h2"; cls?: string; at?: number }) => (
  <T className={`h3d-h ${cls}`} data-in={at}>{lines.map((l) => <span className="ln" key={l}><W>{l}</W></span>)}</T>
);

const Flame = () => (
  <svg viewBox="0 0 32 32" aria-hidden><path d="M16 4c2.2 5.4 7.5 7.6 7.5 14a7.5 7.5 0 0 1-15 0c0-3.3 2.1-5.4 3.2-7.5 1.1 3.2 2.2 4.3 4.3 4.3C15 10.5 15 7.3 16 4z" fill="#EA7329" /><path d="M16 17c1 2.2 3 3 3 5.5a3 3 0 0 1-6 0c0-1.6 1-2.6 1.6-3.5.4 1.2.9 1.6 1.4 1.6-.4-1.2-.4-2.4 0-3.6z" fill="#F6C64F" /></svg>
);
const Arrow = () => <svg viewBox="0 0 24 24" aria-hidden><path d="M6 18 18 6M8 6h10v10" fill="none" stroke="currentColor" strokeWidth="1.6" /></svg>;

// progress bar: groups of chapters, each chapter = label + the beats it spans. Only the active group shows its labels;
// finished and upcoming groups shrink to squares. Click a chapter to jump there.
const GROUPS: [string, number[]][][] = [
  [["Old camera", [B.old]], ["New camera", [B.sharp]], ["The jump", [B.jump]], ["The fix", [B.fix]], ["The proof", [B.proof]]],
  [["Farmers", [B.farm]], ["Connect", [B.connect]]],
];
const CHAPTERS = GROUPS.flatMap((g, gi) => g.map(([l, ks]) => ({ l, ks, gi })));
const GROUP_FROM = GROUPS.map((g) => g[0][1][0]);

// the reviewer path below the story: the page's one numbered list. "farm" opens a finished farmer check (FarmCheck deep link).
const tour = (snppYear: string, areas: number | string): [string, string, Page | "punjab" | "farm"][] => [
  ["The problem", `Raw counts jump in ${snppYear} when a sharper satellite arrives. Nothing changed on the ground.`, "punjab"],
  ["The proof", `${areas} areas, one scorecard.`, "method"],
  ["After MODIS", "Switch satellites off and watch the record hold.", "after"],
  ["Is fire near you?", "Any place on Earth: fire this week, and when fire usually comes.", "near"],
  ["Bangladesh", "A finished farmer check for Aminbazar: kilns next to the field, in Bangla.", "farm"],
  ["Ask Claude", `A ${MCP_TOOLS}-tool MCP server over the same record; ${MCP_HTTP_TOOLS} read-only tools over public HTTP.`, "mcp"],
];
const FARM_LINK = "#pg=bangladesh&q=Aminbazar%2C%20Savar%2C%20Bangladesh";
const PUBLIC_MCP = "https://kiln-watch-seven.vercel.app/mcp";   // the read-only copy: it never sleeps

// the five satellites, in scene.ts ORBITS order
const SATS = [["Terra", "MODIS", "MODIS_T"], ["Aqua", "MODIS", "MODIS_A"], ["Suomi NPP", "VIIRS", "VIIRS_SNPP"], ["NOAA-20", "VIIRS", "VIIRS_NOAA20"], ["NOAA-21", "VIIRS", "VIIRS_NOAA21"]];

const SHOTS = `${import.meta.env.BASE_URL}shots/`;

export default function Home({ regions, go, openRegion }: PageProps) {
  const scroller = useRef<HTMLDivElement>(null), content = useRef<HTMLDivElement>(null), canvas = useRef<HTMLCanvasElement>(null), bar = useRef<HTMLDivElement>(null);
  const tourSec = useRef<HTMLElement>(null);
  const scene = useRef<SceneHandle | null>(null), story = useRef<Story | null>(null);
  const [metas, setMetas] = useState<Meta[]>([]);
  const [events, setEvents] = useState<Events | null>(null);
  const [menu, setMenu] = useState(false); // the page menu on narrow screens
  const [area, setArea] = useState<{ meta: Meta; monthly: Block } | null>(null); // the area the story charts show
  const presets = useMemo(() => regions.filter((r) => r.preset), [regions]);
  const farm = () => { history.replaceState(null, "", FARM_LINK); go("bangladesh"); };
  const skip = () => { if (tourSec.current) story.current?.skip(tourSec.current); };

  useEffect(() => {
    const root = scroller.current!;
    const onBeat = (to: number) => { root.classList.toggle("fin", to === LAST); };
    const onPlayhead = (p: number) => {
      const b = bar.current;
      if (!b) return;
      b.classList.toggle("on", p > 0.5 && p < LAST - 0.5);
      let active = 0;
      GROUP_FROM.forEach((k, gi) => { if (p > k - 0.5) active = gi; }); // a group takes over as its first beat arrives
      CHAPTERS.forEach(({ ks, gi }, i) => {
        const el = b.children[i] as HTMLElement, f = Math.min(1, Math.max(0, (p - (ks[0] - 1)) / ks.length));
        el.style.setProperty("--f", `${f * 100}%`);
        el.classList.toggle("wide", gi === active);
      });
    };
    const st = mountStory(root, content.current!, { beats: BEATS, onBeat, onPlayhead });
    const h = mountScene(canvas.current!, root, st.ph, () => { root.classList.add("ready"); st.start(); });
    story.current = st;
    scene.current = h;
    return () => { h.dispose(); st.dispose(); root.className = "h3d"; scene.current = story.current = null; };
  }, []);

  useEffect(() => {
    let live = true;
    api.events().then((e) => { if (!live) return; setEvents(e); scene.current?.setEvents(e.events.filter((x) => Number.isFinite(x.lon) && Number.isFinite(x.lat))); })
      .catch(() => undefined);   // the globe pins and the count are extras: the count stays "…"
    return () => { live = false; };
  }, []);

  useEffect(() => {
    scene.current?.setPins(presets.map((r) => ({ lon: (r.bbox[0] + r.bbox[2]) / 2, lat: (r.bbox[1] + r.bbox[3]) / 2 })));
    if (!presets.length) return;
    let live = true;
    Promise.all(presets.map((r) => api.meta(r.id).catch(() => null))).then((ms) => live && setMetas(ms.filter((m): m is Meta => !!m)));
    return () => { live = false; };
  }, [presets]);

  // under the story the page scrolls: the fixed story chrome goes, the menu hides on the way down
  useEffect(() => {
    const el = scroller.current!;
    let last = 0;
    const track = el.querySelector<HTMLElement>(".h3d-story")!;
    const on = () => {
      const y = el.scrollTop;
      el.classList.toggle("end", y > track.offsetTop + track.offsetHeight - innerHeight * 0.65);
      if (y > 2) el.classList.toggle("nav-up", y > last && y > innerHeight * 0.6);
      if (Math.abs(y - last) > 4) setMenu(false); // the open page menu folds away once the story moves
      last = y;
    };
    el.addEventListener("scroll", on, { passive: true });
    return () => el.removeEventListener("scroll", on);
  }, []);

  // story area, picked by rule: the built area with the most detections
  useEffect(() => {
    if (!metas.length) return;
    const top = [...metas].sort((a, b) => b.totals.detections - a.totals.detections)[0];
    let live = true;
    api.monthly(top.id).then((monthly) => live && setArea({ meta: top, monthly })).catch(() => undefined);
    return () => { live = false; };
  }, [metas]);

  const s = useMemo(() => (metas.length ? summarize(metas) : null), [metas]);
  const sm = area?.meta, den = sm?.denial.modis_ends_2016;
  // first years from meta.sensors; "…" until the metas arrive (one word, so W's word count stays the same)
  const y0 = s?.since?.slice(0, 4) ?? "…", y1 = s?.snpp?.slice(0, 4) ?? "…";
  useEffect(() => (s ? countUp(content.current!, scroller.current!) : undefined), [s]);

  return (
    <div className="h3d" ref={scroller}>{/* story.ts and the effects below toggle state classes on this node, so its className stays constant */}
      <a className="skip-link" href="#h3d-tour" onClick={(e) => { e.preventDefault(); skip(); }}>Skip to content</a>
      <canvas className="h3d-canvas" ref={canvas} aria-hidden />
      <div className="h3d-veil" aria-hidden />
      <div className="h3d-fade" aria-hidden />
      <div className="h3d-load" aria-hidden><span>Kiln Watch</span><i /></div>

      <header className="h3d-nav">
        <a className="brand" href="#" aria-label="Kiln Watch, back to the start" onClick={(e) => { e.preventDefault(); scroller.current?.scrollTo({ top: 0 }); story.current?.go(0); }}><Flame /><span>Kiln Watch</span></a>
        <nav aria-label="Pages" id="h3d-pages" className={menu ? "open" : ""}>
          {NAV.map(([k, l]) => <button key={k} onClick={() => go(k)}>{l}</button>)}
        </nav>
        <button className="h3d-box" onClick={() => go("explore")}>Open Explorer <Arrow /></button>
        <button className="h3d-menu" aria-expanded={menu} aria-controls="h3d-pages" aria-label={menu ? "Close the page menu" : "Open the page menu"} onClick={() => setMenu(!menu)}>
          <svg viewBox="0 0 24 24" aria-hidden><path d={menu ? "M6 6l12 12M18 6 6 18" : "M4 7h16M4 12h16M4 17h16"} fill="none" stroke="currentColor" strokeWidth="1.8" /></svg>
        </button>
      </header>

      <div className="h3d-bar" ref={bar}>
        {CHAPTERS.map(({ l, ks, gi }) => (
          <button key={l} className={gi ? "" : "wide"} aria-label={`Go to: ${l}`} onClick={() => story.current?.go(ks[0])}><span>{l}</span><i><span>{l}</span></i></button>
        ))}
      </div>
      <div className="h3d-tags" aria-hidden>
        {SATS.map(([n, inst, k]) => (
          <div key={n} data-sat className={inst === "MODIS" ? "modis" : ""}><i /><b>{n}</b><span>{inst}{span(metas, k)}</span></div>
        ))}
      </div>
      {/* the ring fills while a scene is still landing (story.ts); then the cue invites the next move */}
      <button className="h3d-cue" aria-label="Next scene" onClick={() => story.current?.next()}>
        <svg viewBox="0 0 36 36" aria-hidden><circle cx="18" cy="18" r="16" pathLength={1} /><path d="M12 16l6 6 6-6" /></svg>
        <span>Scroll</span>
      </button>
      <button className="h3d-cta" onClick={() => go("explore")}><span>Open the explorer</span><i><Arrow /></i></button>

      <div className="h3d-content" ref={content}>
        <section className="h3d-story" style={{ height: `${(LAST * STEP + 1) * 100}vh` }}>
          <div className="h3d-stage">
          {/* 0 · hero: the satellite drifts and scans; live NASA wildfire events glow on the globe */}
          <div className="h3d-beat hero" data-b={B.hero}>
            <div className="h3d-col">
              <p className="kicker" data-in>NASA Space Apps 2026 · Harmonization of MODIS and VIIRS Hot Spots</p>
              <H tag="h1" cls="xl" lines={["Every fire.", "One record."]} at={0.1} />
              <p className="h3d-lead big" data-in="0.6">NASA satellites have watched Earth's fires from space <em>since {y0}</em>. We turn their mismatched counts into <em>one record you can trust</em>.</p>
              <p className="h3d-proof" data-in="0.8">When a sharper satellite joined in {y1}, raw counts jumped <b>×{fx(s?.raw, 1)}</b>. Our record moves <b>×{fx(s?.harm)}</b> (1.00 = no jump; median of {s?.nStep ?? "…"} areas). <button className="linkish" onClick={() => go("method")}>See the proof ›</button></p>
              <p className="h3d-try" data-in="0.9">
                <button onClick={() => go("near")}>Is fire near you?</button>
                <button lang="bn" onClick={farm}>বাংলা: জমির কাছে ইটভাটা</button>
                <button className="ghost" onClick={skip}>Skip the story ↓</button>
              </p>
              <p className="firechip" data-in="1"><i /><b>{events?.count ?? "…"}</b> wildfires reported to NASA in the last 30 days</p>
            </div>
          </div>

          {/* 1 · the older camera: Terra and Aqua assemble on the blueprint */}
          <div className="h3d-beat" data-b={B.old}>
            <div className="h3d-col narrow" data-in>
              <p className="kicker">The older camera · MODIS · on Terra and Aqua · since {y0}</p>
              <p className="h3d-title"><W>Sees the ground in</W> <em><W>1 km squares</W></em></p>
              <p className="h3d-line">A big fire lights a few squares. <em>Small fires can slip through.</em></p>
            </div>
            <PixelCard cams={["modis"]} />
          </div>

          {/* 2 · the sharper camera: Suomi NPP assembles */}
          <div className="h3d-beat" data-b={B.sharp}>
            <div className="h3d-col narrow" data-in>
              <p className="kicker">The sharper camera · VIIRS · on Suomi NPP, NOAA-20, NOAA-21 · since {y1}</p>
              <p className="h3d-title"><W>Sees</W> <em><W>375 m squares</W></em></p>
              <p className="h3d-line">The same fires on the same day: <em>far more dots</em>. So the counts jump even when the fires don't.</p>
            </div>
            <PixelCard cams={["modis", "viirs"]} />
          </div>

          {/* 3, 4 · the jump in the raw counts, then the calibrated record on the same chart */}
          <div className="h3d-beat h3d-plot" data-b={`${B.jump}-${B.fix}`}>
            <div className="beat" data-b={B.jump} data-in>
              <p className="idx">The jump</p>
              <p className="h3d-big"><W>Counts jumped</W> <em className="f"><W>{`×${fx(s?.raw, 1)}`}</W></em></p>
              <p className="h3d-line">in {y1}, more than the fires did. <em>A sharper camera had joined.</em></p>
            </div>
            <div className="beat" data-b={B.fix} data-in>
              <p className="idx">The fix</p>
              <p className="h3d-big"><W>Now:</W> <em><W>{`×${fx(s?.harm)}`}</W></em></p>
              <p className="h3d-line">We measure how much more each camera sees and <em>convert</em> all {s?.sats ?? "…"} to one scale. Like converting currencies.</p>
              <p className="fine">1.00 means no jump. Median of {s?.nStep ?? "…"} areas; the chart shows {sm?.name ?? "…"}.</p>
            </div>
            <div className="chartwrap" data-in="0.1"><JumpChart m={area?.monthly ?? null} meta={sm ?? null} fixBeat={B.fix} /></div>
          </div>

          {/* 5 · the proof: MODIS switched off on paper, rebuilt from VIIRS */}
          <div className="h3d-beat h3d-plot val" data-b={B.proof}>
            <div className="beat" data-in>
              <p className="idx">The proof</p>
              <p className="h3d-big"><W>We</W> <em><W>tested</W></em> <W>it</W></p>
              <p className="h3d-line">We hid the older camera after {den?.train[1].slice(0, 4) ?? "…"} and rebuilt its record from the newer one alone.</p>
            </div>
            <div className="score" data-in="1.4">
              <b>{fx(s?.rho)}</b>
              <span>match with the<br />camera we hid<br />1.00 = perfect</span>
              <p className="fine">Median of {s?.areas ?? "…"} areas, {s?.rhoN ?? "…"} months each (rank correlation). The chart shows {sm?.name ?? "…"}: {fx(den?.ours_seasonal_eb.spearman)}.</p>
            </div>
            <div className="chartwrap" data-in="0.2"><ValidateChart meta={sm ?? null} /></div>
          </div>

          {/* 6 · for farmers, in Bangla */}
          <div className="h3d-beat farmbeat" data-b={B.farm}>
            <div className="farmshots" data-in="0.3">{["farmer-kilns", "farmer-boro"].map((f) => <img key={f} src={`${SHOTS}${f}.png`} alt="" />)}</div>
            <div className="h3d-col right big">
              <H lines={["Kilns next to", "the field"]} cls="xl" />
              <div data-in="0.5">
                <p className="kicker under" lang="bn">বাংলাদেশ · For farmers</p>
                <p className="h3d-lead">Farmers say kiln smoke ruins their crops but cannot show the kilns are there. <em>Now they can</em>, in Bangla, in one tap.</p>
                <p className="who">Kilns within 1 km from a national inventory, fire this week, and fire before the Boro harvest. Email, WhatsApp or print it for the agriculture office.</p>
                <button className="h3d-link" onClick={farm}>Try it: Aminbazar <Arrow /></button>
                <p className="fine">Why “Kiln Watch”: we began with the brick kilns around Dhaka. We measured that fire satellites cannot count kilns, so the farmer check reads a kiln inventory, never the fire detections.</p>
              </div>
            </div>
          </div>

          {/* 7 · connect */}
          <div className="h3d-beat connect" data-b={B.connect}>
            <div className="h3d-col big">
              <H lines={["Plug in", "any agent"]} cls="xl" />
              <div data-in="0.5">
                <p className="kicker under">MCP · REST API · n8n</p>
                <p className="h3d-lead">Claude, Cursor or any AI assistant asks Kiln Watch for <em>real numbers</em> instead of guessing. MCP is the standard way an assistant calls outside tools.</p>
                <p className="who">For developers and data teams. n8n, an automation tool, turns an alert into an email or a Slack message.</p>
                <button className="h3d-link" onClick={() => go("mcp")}>Connect <Arrow /></button>
              </div>
            </div>
            <div className="term" data-in="0.4">
              <p className="bar"><i /><i /><i /><span>terminal · public server, read-only</span></p>
              <pre>{`claude mcp add --transport http \\\n  kiln-watch ${PUBLIC_MCP}`}</pre>
              <p className="tools"><span>tools</span>get_harmonized_calendar · check_place_fire_risk · get_early_warning · find_anomalies · search_fire_reports · get_active_wildfire_events …</p>
            </div>
          </div>

          {/* 8 · the way in */}
          <div className="h3d-beat center" data-b={B.go}>
            <H lines={["Get your fire record today"]} cls="xl" at={0.2} />
            <button className="h3d-go" data-in="0.8" onClick={() => go("explore")}>Open the explorer</button>
          </div>
          </div>
        </section>

        <section className="h3d-flat built tour" id="h3d-tour" ref={tourSec} tabIndex={-1}>
          <div className="head" data-reveal>
            <p className="label">See it in three minutes</p>
            <h2 className="h3d-h">Six stops,<br />one story</h2>
          </div>
          <ol className="who-grid" data-reveal>
            {tour(y1, s?.areas ?? "…").map(([t, d, pg], i) => <li key={t}><button onClick={() => (pg === "punjab" ? openRegion("punjab") : pg === "farm" ? farm() : go(pg))}><b>{i + 1}. {t}</b><span>{d}</span><i><Arrow /></i></button></li>)}
          </ol>
        </section>

        <section className="h3d-flat heritage">
          <p className="label">The record so far</p>
          <div className="nums" data-reveal>
            <div><b><Count v={s?.areas} /></b><span>Areas built, {y0} to today</span></div>
            <div><b><Count v={s?.rho} dec={2} /></b><span>Match with the satellite we hid, 1.00 is perfect ({s?.rhoN ?? "…"} months)</span></div>
            <div><b><Count v={s ? s.statics / 1000 : null} />K</b><span>Detections from steady heat sources (gas flares, factories) kept apart from fires</span></div>
          </div>
          <p className="fine">Middle figure: median across areas of the test “what if MODIS had ended in 2016?”, where {s?.rhoTest ? `${s.rhoTest[0]} to ${s.rhoTest[1]}` : "…"} is rebuilt from VIIRS alone and compared with what Aqua MODIS saw. Data through {s?.through ?? "…"}.</p>
        </section>

        <section className="h3d-flat wall">
          <div className="head" data-reveal>
            <h2 className="h3d-h">{s?.areas ?? "…"} areas<br />on one scale</h2>
            <p>Open a built area, or make your own: any box on Earth up to 4° × 4°. The first build reads every detection since {y0} and takes 5 to 10 minutes.</p>
          </div>
          <ul className="cells" data-reveal>
            {presets.map((r) => (
              <li key={r.id}><button onClick={() => openRegion(r.id)}>
                <span className="c">{r.country}</span><b>{r.name}</b><span className="t">{r.story}</span><i><Arrow /></i>
              </button></li>
            ))}
            <li className="you"><button onClick={() => go("create")}><b>You?</b><span className="t">Build a record for any area on Earth.</span><i><Arrow /></i></button></li>
          </ul>
        </section>

        <footer className="h3d-flat h3d-foot">
          <div className="cols">
            <div className="about"><h3>Kiln Watch</h3><p>One consistent fire record,<br />{y0} to today.<br />NASA Space Apps 2026.</p></div>
            {SECTIONS.map(([l, ps]) => <div key={l}><h3>{l}</h3>{ps.map(([k, pl]) => <button key={k} onClick={() => go(k)}>{pl}</button>)}</div>)}
          </div>
          <div className="legal">
            <p>Data: NASA FIRMS (MODIS C6.1, VIIRS 375 m) via the Portolan mirror. Satellite models: NASA 3D Resources. Earth: NASA Blue Marble. Not an official NASA product.</p>
            <p>Detections are not fires and not burned area. The fire outlook is a climatological outlook, not a forecast.</p>
          </div>
        </footer>
      </div>
    </div>
  );
}
