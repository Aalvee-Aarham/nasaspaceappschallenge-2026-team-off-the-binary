import { useEffect, useState } from "react";
import { Persona, api, apiOrigin } from "../api";
import { Code, PageHead, PageProps } from "./shared";

const TOOLS: [string, [string, string][]][] = [
  ["Find a place", [
    ["find_place", "Any place name on Earth: centre, a ready box, local languages, overlapping areas."],
    ["list_regions", "Areas that already have a harmonized 2000-present record."],
    ["create_custom_area / get_custom_area_status", "Build the 26-year record for any box and follow its progress."],
  ]],
  ["Now and the next 30 days", [
    ["check_place_fire_risk", "Any town, address or school on Earth: fire seen within 1-25 km this week, the usual fire months, the outlook, and the schools, hospitals, clinics, care homes and fire stations near that fire. No built area needed."],
    ["get_fire_outlook", "Worldwide or in-box 30-day outlook: watch, above normal, season ahead, named regions."],
    ["get_outlook_at", "The outlook for the half-degree cell at a point."],
    ["query_hotspots", "Raw detections per day and satellite for any box and dates, instantly."],
    ["get_situation_brief", "Ready-to-share markdown brief: level, month, next 30 days, events, trend."],
    ["get_early_warning / check_watchlist", "Level per area and the areas at or above a level."],
    ["get_active_wildfire_events", "Open NASA EONET wildfire events, tagged with the area they fall in."],
    ["get_sensor_status", "Last day each of the five satellites delivered, measured from data."],
  ]],
  ["The harmonized record", [
    ["get_area_summary / get_period", "Plain-language answers; one month or week with interval, rank and percentile."],
    ["get_harmonized_calendar", "Month-by-year or week calendar on the Aqua MODIS scale."],
    ["get_annual_series", "Harmonized against raw totals per year: the satellite jumps, removed."],
    ["get_season_profile / compare_areas", "Season start, peak and end; several areas side by side."],
    ["find_anomalies / get_period_evidence", "Most unusual periods; the detections and links behind one."],
    ["audit_sensor_harmonization / get_method", "Calibration, validation, step tests, provenance and the exact rules."],
  ]],
  ["News and events", [
    ["search_news_for_place", "Google News in local languages, GDELT, EONET and GDACS for any place and window."],
    ["get_latest_fire_news", "Worldwide wildfire headlines and events of the last days, 7 languages."],
    ["get_gdacs_wildfires", "GDACS wildfire alerts with burned area, optionally inside a box."],
    ["search_fire_reports / search_timeline_reports", "Reports matched month by month against the record, with a verdict."],
    ["get_fire_cases / get_fire_case", "Fire cases checked against agency records and the news, with a verdict; one case with every witness."],
    ["get_casebook_overview", "Every area at a glance: cases, fires the record missed, people and hospitals near fire, failed sources."],
    ["get_exposure", "Population, hospitals, schools, farmland and major roads in the cells where the record shows fire. Context, not impact."],
    ["get_place_exposure", "One school, hospital or farm: how often and in which months fire is seen in its 11 km cell since 2000."],
    ["get_kiln_evidence", "Brick kilns from a published map, how few NASA FIRMS sees, and night lights in kiln season (Dhaka belt)."],
  ]],
  ["Alerts", [
    ["subscribe_email_alert", "Email for any box: anomaly, 30-day watch, new events. Double opt-in."],
    ["subscribe_place_alert", "Alert for one school, hospital or farm: a detection nearby, or a usually active month ahead."],
    ["create_alert / check_alert / delete_alert", "Token alerts for n8n or polling."],
  ]],
];

/** The state-changing tools a public HTTP connector does not get; a local or stdio server keeps them. */
const WRITE_TOOLS = new Set(["create_custom_area", "subscribe_email_alert", "create_alert", "subscribe_place_alert", "delete_alert"]);

const PROMPTS: [string, string][] = [
  ["fire_manager", "Ember, fire operations officer: operational 30-day brief for a place."],
  ["fire_scientist", "Dr. Vega, remote-sensing scientist: audit of the harmonization."],
  ["fact_checker", "Scout, news fact-checker: a headline against the satellite record."],
  ["community_liaison", "Sentinel, community liaison: a short bulletin in the local language."],
];

const STDIO = `{
  "mcpServers": {
    "kiln-watch": {
      "command": "python",
      "args": ["-m", "kw.mcp_server"],
      "cwd": "<path to this repo>/server"
    }
  }
}`;

export function Mcp({ go }: PageProps) {
  const url = `${apiOrigin()}/mcp`;
  const [ps, setPs] = useState<Persona[]>([]);
  const [copied, setCopied] = useState("");
  useEffect(() => { api.personas().then(setPs).catch(() => undefined); }, []);
  const copy = (k: string, t: string) => {
    const request = navigator.clipboard?.writeText(t);
    request?.then(() => { setCopied(k); setTimeout(() => setCopied(""), 1500); }).catch(() => undefined);
  };
  const names = TOOLS.flatMap(([, l]) => l.flatMap(([n]) => n.split(" / ")));
  const nTools = names.length;                                      // all of them, for a local or stdio server
  const nPublic = names.filter((n) => !WRITE_TOOLS.has(n)).length;  // what the public HTTP endpoint serves
  return (
    <>
      <PageHead kicker="Kiln Watch for Claude" title="MCP and characters" lead={`Connect Claude to ${nPublic} deterministic read-only fire tools and four ready-made characters: a fire operations officer, a remote-sensing scientist, a fact-checker and a community liaison. A local server also keeps the ${nTools - nPublic} tools that change state. Claude asks Kiln Watch for every number; it never makes one up.`} />

      <p className="row">
        <button className="btn ghost" onClick={() => go("download")}>Download the data</button>
        <button className="btn ghost" onClick={() => go("create")}>Build your own area</button>
        <button className="btn ghost" onClick={() => go("n8n")}>Automate with n8n</button>
        <button className="btn ghost" onClick={() => go("news")}>News beside the data</button>
      </p>

      <section className="mcp-hero">
        <div className="mcp-stats">
          {[[String(nPublic), "read-only tools over HTTP"], [String(nTools), "tools in a local server"], ["4", "characters"], ["5", "resources"], ["0", "model calls on the server"]].map(([n, l], i) => (
            <div key={l} style={{ animationDelay: `${i * 90}ms` }}><b className="num">{n}</b><span>{l}</span></div>
          ))}
        </div>
        <div className="mcp-url">
          <span className="muted small">Remote MCP endpoint (Streamable HTTP)</span>
          <code>{url}</code>
          <button className="btn" onClick={() => copy("url", url)}>{copied === "url" ? "Copied" : "Copy URL"}</button>
        </div>
      </section>

      <section>
        <h2>1. Connect</h2>
        <div className="connect-grid">
          <div className="ccard">
            <h3>Claude (web and desktop app)</h3>
            <ol className="steps">
              <li>Open <b>Settings → Connectors → Add custom connector</b>.</li>
              <li>Name it <b>Kiln Watch</b> and paste the URL above.</li>
              <li>In a chat, open the <b>+</b> menu, enable Kiln Watch, and pick a character under its prompts.</li>
            </ol>
            <p className="muted small">The URL must be reachable from the internet (a deployed Kiln Watch over HTTPS). For a local copy use the desktop config below.</p>
          </div>
          <div className="ccard">
            <h3>Claude Desktop, local</h3>
            <p className="small">Add to <code>claude_desktop_config.json</code> and restart:</p>
            <Code text={STDIO} />
          </div>
          <div className="ccard">
            <h3>Claude Code</h3>
            <Code text={`claude mcp add --transport http kiln-watch ${url}`} />
            <p className="small">Then drop the characters into <code>.claude/agents/</code> (downloads below) and ask "use fire-manager to brief me on Pará".</p>
          </div>
        </div>
      </section>

      <section>
        <h2>2. Pick a character</h2>
        <p className="muted small">Each character is a role plus strict ground rules: numbers only from tools, detections are not fires, outlooks are not forecasts, missing news proves nothing. Use them as MCP prompts, as Claude Project instructions, or as Claude Code subagents.</p>
        <div className="personas">
          {ps.map((p, i) => (
            <article key={p.id} className={`persona p-${p.id}`} style={{ animationDelay: `${i * 100}ms` }}>
              <header>
                <span className="avatar" aria-hidden>{p.name[0]}</span>
                <div><b>{p.name}</b><span>{p.role}</span></div>
              </header>
              <p className="tag-q">“{p.tagline}”</p>
              <p className="muted small">For: {p.for}.</p>
              <ul className="starters">{p.starters.map((s) => <li key={s}><button className="link" onClick={() => copy(s, s)} title="Copy">{copied === s ? "Copied" : s}</button></li>)}</ul>
              <div className="row">
                <button className="btn ghost" onClick={() => copy(p.id, p.system_prompt)}>{copied === p.id ? "Copied" : "Copy as Project instructions"}</button>
                <a className="btn ghost" href={api.personaUrl(p.id)} download>Claude Code subagent</a>
              </div>
            </article>
          ))}
          {!ps.length && <p className="muted">Start the Kiln Watch API to load the characters.</p>}
        </div>
        <table className="tbl" style={{ marginTop: 14 }}>
          <thead><tr><th>MCP prompt</th><th>What it starts</th></tr></thead>
          <tbody>{PROMPTS.map(([n, d]) => <tr key={n}><td><code>{n}</code></td><td>{d}</td></tr>)}</tbody>
        </table>
      </section>

      <section>
        <h2>3. Ask</h2>
        <ul className="prompts">
          {[
            "Is fire near Paradise, California this week? Which schools and hospitals are closest to it?",
            "Where on Earth is fire activity running above normal right now, and which of those places are entering their usual fire season?",
            "Brief me on fire around Pará, Brazil: the last 14 days by satellite and what the next 30 days usually bring.",
            "Show raw versus harmonized yearly totals for Punjab and explain the jumps in 2012, 2018 and 2024.",
            "A headline says Rondônia had a record fire season in 2024. Check it against the satellites and the news.",
            "Email me at me@example.org when the fire-season outlook around Kalimantan turns to watch.",
          ].map((p) => <li key={p}><q>{p}</q></li>)}
        </ul>
      </section>

      <section>
        <h2>Or call the REST API</h2>
        <p className="muted">The same answers as plain JSON over HTTPS: no key, no sign-up, open CORS. Interactive docs for every endpoint: <a href={`${apiOrigin()}/docs`} target="_blank" rel="noreferrer">{apiOrigin()}/docs</a>.</p>
        <Code text={`# Is fire near a place? Name or "lat, lon"; radius 1-25 km
curl "${apiOrigin()}/api/place-risk?q=Ludhiana,%20India&radius_km=10"
curl "${apiOrigin()}/api/place-risk?lat=39.76&lon=-121.62&radius_km=5"
# Faster first answer without the schools and hospitals (OpenStreetMap is the slow part)
curl "${apiOrigin()}/api/place-risk?q=Sylhet&facilities=false"
# 30-day outlook at a point, raw detections for any box, the study areas
curl "${apiOrigin()}/api/outlook/at?lat=30.9&lon=75.85"
curl "${apiOrigin()}/api/hotspots?west=75&south=30&east=77&north=32&start=2026-11-01&end=2026-11-13"
curl "${apiOrigin()}/api/regions"`} />
        <p className="muted small"><code>/api/place-risk</code> returns <code>level</code> (near, watch, season, low, unknown), a plain-language <code>headline</code> and <code>reasons</code>, <code>recent</code> detections, <code>season</code> (years with fire per calendar month), <code>outlook</code>, <code>facilities</code> (each with its distance to the nearest fire) and <code>errors</code> for any source that could not be read. Detections are not confirmed fires; history is not a forecast.</p>
      </section>

      <section>
        <h2>Tools</h2>
        {TOOLS.map(([g, l]) => (
          <div key={g} className="toolgroup">
            <h3>{g}</h3>
            <table className="tbl"><tbody>{l.map(([n, d]) => <tr key={n}><td><code>{n}</code></td><td>{d}</td></tr>)}</tbody></table>
          </div>
        ))}
        <p className="muted small">Resources: <code>kilnwatch://about</code>, <code>kilnwatch://personas</code>, <code>kilnwatch://regions</code>, <code>kilnwatch://outlook</code>, <code>kilnwatch://region/&lt;id&gt;/brief</code>. Read-only tools are marked so clients can run them without asking. Every result is read from the pipeline's outputs or computed from NASA FIRMS rows; the server never calls a language model.</p>
        <p className="muted small">The public HTTP endpoint serves the {nPublic} read-only tools only: building an
          area, creating or deleting an alert, and alerts and email for one place are state-changing, so they stay in a
          trusted local or stdio server, where {nTools} tools are available.</p>
      </section>
    </>
  );
}

export function N8n({ go }: PageProps) {
  const base = apiOrigin();
  return (
    <>
      <PageHead kicker="Automation" title="n8n alerts" lead="Kiln Watch can email you itself; n8n is for Slack, Telegram, Teams or anything else. Each alert has a secret token and n8n asks about it every morning." />

      <section>
        <h2>How it works</h2>
        <ol className="flow">
          <li><b>You</b><span>pick a place and triggers on the Early warning page</span></li>
          <li><b>Kiln Watch</b><span>builds that place's record and keeps it fresh</span></li>
          <li><b>n8n</b><span>asks every morning: <code>POST /api/alerts/&lt;token&gt;/poll</code></span></li>
          <li><b>IF</b><span><code>triggered</code>, <code>outlook_triggered</code> or new events</span></li>
          <li><b>You</b><span>get the email, Slack or Telegram message</span></li>
        </ol>
        <div className="row"><button className="btn" onClick={() => go("warning")}>Create an alert</button></div>
      </section>

      <section>
        <h2>Set it up</h2>
        <ol className="steps long">
          <li>On <button className="link" onClick={() => go("warning")}>Early warning</button>, choose an area and triggers and create the alert (the email is optional).</li>
          <li>Press <b>n8n workflow</b>. The file already contains your alert's URL, so there is nothing to type in.</li>
          <li>In n8n choose <b>Workflows, Import from file</b>. Open <b>Send email</b>, pick your SMTP credentials and recipient; or replace it with a Slack, Telegram or Teams node. The text to send is <code>{"{{ $json.message }}"}</code>.</li>
          <li>The URL points at <code>{base}</code>. n8n must be able to reach it: use a deployed Kiln Watch, or <code>host.docker.internal</code> when n8n runs in Docker on the same machine.</li>
          <li>Press <b>Execute workflow</b> once to test, then switch it to <b>Active</b>.</li>
        </ol>
        <p className="muted small">Written for n8n 1.x (Schedule Trigger, HTTP Request, IF, Send Email); not run against every n8n version.</p>
      </section>

      <section>
        <h2>The rules</h2>
        <p><b>Anomaly:</b> the month so far is above N × the median of the same days in earlier years (N = 1 means it tops the median) and at least 5 hotspots; at most once per calendar month. <b>Outlook watch:</b> the 30-day outlook in your box has cells entering a usually active season while already above normal; at most weekly. <b>New events:</b> NASA EONET opens a wildfire event inside the box; each event once. Counts are harmonized across satellites, so a new satellite never causes an alert.</p>
        <p className="muted small">It is a comparison with history, not a forecast or an official alert. Have a person decide on any action.</p>
      </section>

      <section>
        <h2>No n8n? Use the API</h2>
        <Code text={[
          "# email alert for any box (west, south, east, north), here Cerrado, Brazil",
          `curl -X POST ${base}/api/alerts -H "Content-Type: application/json" -d '{"bbox": [-48.5, -14.5, -45.5, -12.0], "name": "Cerrado", "ratio": 1.0, "email": "you@example.org", "triggers": ["anomaly", "outlook", "events"]}'`,
          "",
          "# status of your alert (building, or ready with triggered, outlook and events)",
          `curl ${base}/api/alerts/<token>`,
          "",
          "# what n8n calls: each trigger reported once",
          `curl -X POST ${base}/api/alerts/<token>/poll`,
        ].join(String.fromCharCode(10))} />
        <p className="small">Server operators: set <code>SMTP_HOST</code>, <code>SMTP_PORT</code>, <code>SMTP_USER</code>, <code>SMTP_PASSWORD</code> and <code>SMTP_FROM</code> (a free Gmail app password works) and <code>PUBLIC_URL</code>; Kiln Watch then checks every alert every 3 hours and emails confirmed subscribers. The <button className="link" onClick={() => go("mcp")}>MCP server</button> has <code>subscribe_email_alert</code> for Claude.</p>
      </section>
    </>
  );
}
