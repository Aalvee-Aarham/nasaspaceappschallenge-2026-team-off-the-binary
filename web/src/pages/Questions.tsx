import { ReactNode, useEffect, useState } from "react";
import { Checks, api } from "../api";
import { LIMITS } from "./Method";
import { PageHead, PageProps } from "./shared";

const GH = "https://github.com/nasa/spaceapps/discussions/";
type Status = "solved" | "measured" | "open";
const STATUS: Record<Status, string> = { solved: "Built in", measured: "Measured", open: "Open" };
const SRC = {
  snpp: ["FIRMS blog", "https://www.earthdata.nasa.gov/news/blog/transitioning-from-suomi-npp-viirs-omps-what-firms-users-need-know"],
  faq: ["FIRMS FAQ", "https://www.earthdata.nasa.gov/data/tools/firms/faq"],
  modis: ["Earthdata alert", "https://www.earthdata.nasa.gov/data/alerts-outages/transition-from-modis-viirs"],
  cams: ["Copernicus CAMS", "https://atmosphere.copernicus.eu/drifting-away-modis-cams-global-fire-assimilation-system"],
  li: ["Li et al. 2018", "https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2017jd027823"],
  night: ["arXiv 2510.26816", "https://arxiv.org/pdf/2510.26816"],
  pod: ["GMD 2026", "https://gmd.copernicus.org/articles/19/10123/2026/"],
} satisfies Record<string, [string, string]>;

const mean = (v: number[]) => v.reduce((a, b) => a + b, 0) / v.length;
const pct = (v: number | null | undefined) => (v == null ? "–" : `${Math.round(v * 100)}%`);

function Q({ n, src, status, ask, official, children }: { n?: number; src?: [string, string]; status: Status; ask: string; official?: string; children: ReactNode }) {
  const [label, href] = src ?? [`#${n}`, GH + n];
  return (
    <li className="qa">
      <p><span className={`tag qa-${status}`}>{STATUS[status]}</span> <a href={href} target="_blank" rel="noreferrer">{label}</a> <b>{ask}</b></p>
      {official && <p className="muted small">{src ? "The source says" : "Reply on the thread"}: {official}</p>}
      <div>{children}</div>
    </li>
  );
}

export default function Questions({ regions, go }: PageProps) {
  const [c, setC] = useState<Checks | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api.checks().then(setC).catch((e) => setErr(e.message)); }, []);
  const snppEnd = regions.find((r) => r.preset)?.sensors_last?.VIIRS_SNPP;

  return (
    <>
      <PageHead kicker="Open questions" title="What teams asked NASA, and our answers"
        lead="We read every thread about this challenge on NASA's Space Apps GitHub. Each question below links to the thread, shows the reply it got, and says how Kiln Watch handles it: built in, measured here from the data, or still open." />

      <section>
        <h2>Discussion #1879: data sources, units and interpretation</h2>
        <p className="muted small">Five questions addressed to the challenge authors; the replies quoted are from m-compagnucci on the thread.</p>
        <ol className="plain qa-list">
          <Q n={1879} status="solved" ask="Should the record be MODIS-equivalent or VIIRS-equivalent?" official="either is fine if properly justified.">
            <p>Primary unit: hotspots on the <b>Aqua MODIS scale</b>. Converting VIIRS down to MODIS discards information and is well-posed; going up would invent small fires MODIS never saw. A VIIRS-scale view is also in the Explorer, and every month before 2012 is hatched <i>modelled</i> there. Justification and tests: <a href="#pg=method" onClick={() => go("method")}>Proof</a>.</p>
          </Q>
          <Q n={1879} status="solved" ask="Is the standard FIRMS archive acceptable, or are swath products expected?" official="yes, FIRMS is the suggested NASA resource.">
            <p>Every detection comes from FIRMS (MODIS C6.1, VIIRS 375 m C2), standard and near-real-time. Near-real-time rows carry no FIRMS <code>type</code> flag, so a cell is typed as a persistent heat source from its own standard-processing history, and near-real-time months are labelled <i>provisional</i> rather than adjusted.</p>
          </Q>
          <Q n={1879} status="solved" ask="FIRMS stopped new Suomi-NPP data; should solutions show continuity with NOAA-20 and NOAA-21?" official="yes, look for solutions that extend into the future.">
            <p>The question says 2 November 2022; the data says otherwise. Read from the FIRMS records, Suomi-NPP's last day is <b>{snppEnd ?? "…"}</b>{snppEnd ? "" : " (loading)"}. The end is detected, never typed in. NASA's own pages disagree on the hour (the FIRMS blog says 13:00 UTC, the FIRMS FAQ 15:40 UTC). We count observing days, so the record does not depend on which is right. The chain is NOAA-21 → NOAA-20 → Suomi-NPP → Aqua, so the record carries on. The cut-over is tested week by week on <a href="#pg=after" onClick={() => go("after")}>After MODIS</a>.</p>
          </Q>
          <Q n={1879} status="solved" ask="Who are the calendar's users, and which time step: days, ISO weeks or months?" official="early warning, emergency responders, scientists, land managers, firefighters; monthly is solid, weekly interesting if it stays readable.">
            <p>Monthly is the default calendar (month by year). A weekly grid is one switch away. Daily stays underneath: click any cell for its detections and that day's imagery. The early warning compares a period with the same period in earlier years.</p>
          </Q>
          <Q n={1879} status="solved" ask="Is Google Earth Engine acceptable for datasets such as MOD14A1?" official="acceptable, but use NASA-suggested resources.">
            <p>The fire record uses FIRMS only. Earth Engine is used at build time for witnesses (MODIS burned area MCD64A1, Black Marble night lights, Sentinel-1), and the live app needs none of it.</p>
          </Q>
        </ol>
      </section>

      <section>
        <h2>Discussion #1786: how to harmonize, and how big</h2>
        <ol className="plain qa-list">
          <Q n={1786} status="measured" ask="Pixels seen at an angle grow, to about 2 km for MODIS. How do you harmonize those?">
            <p>We calibrate a ratio of totals per calendar month. That absorbs the scan-angle effect only if the share of detections seen near the swath edge stays the same from year to year. We measured it: each sensor's detections are split at its own median pixel size, 2012 to 2020, vegetation fires only.</p>
            {err && <p className="error small">{err}</p>}
            {c && (
              <div className="scroll"><table className="tbl">
                <thead><tr><th>Area</th><th>Aqua edge share, range of years</th><th>Year-to-year spread</th><th>Suomi-NPP ÷ Aqua, inner half</th><th>outer half</th></tr></thead>
                <tbody>{c.areas.map((a) => {
                  const s = a.scan, r = s.ratio;
                  return (
                    <tr key={a.id} className={s.aqua.edge_share_sd_pp == null ? "dim" : ""}>
                      <td>{a.name}</td>
                      <td className="num">{s.aqua.edge_share_min == null ? "too few" : `${pct(s.aqua.edge_share_min)}–${pct(s.aqua.edge_share_max)}`}</td>
                      <td className="num">{s.aqua.edge_share_sd_pp == null ? "–" : `±${s.aqua.edge_share_sd_pp} pts`}</td>
                      <td className="num">{r.inner.length ? mean(r.inner).toFixed(1) : "–"}</td>
                      <td className="num">{r.outer.length ? mean(r.outer).toFixed(1) : "–"}</td>
                    </tr>);
                })}</tbody>
              </table></div>
            )}
            <p className="small">Where fire is frequent (Punjab, Rondônia, Northern California, Niger Delta) the edge share moves only a few points a year, and the inner-half and outer-half ratios agree. So a ratio of totals carries the scan-angle effect evenly into every year. Where a season is made of a few large fires (Fort McMurray, South-east Australia), one fire caught at the swath edge can swing a year. Those areas have the widest intervals, and the calibration is still not stratified by scan angle (listed on Proof). Years with fewer than 50 Aqua detections are left out.</p>
          </Q>
          <Q n={1786} status="measured" ask="Some hotspots only VIIRS picks up, some only MODIS. Do they deserve to be harmonized?">
            <p>Same day, same pass, within about 1 km (3 × 3 cells of 0.01°), 2012 to 2020:</p>
            {c && (
              <div className="scroll"><table className="tbl">
                <thead><tr><th>Area</th><th>Aqua seen by Suomi-NPP</th><th>Suomi-NPP seen by Aqua</th><th>Median FRP, VIIRS alone</th><th>VIIRS matched</th></tr></thead>
                <tbody>{c.areas.map((a) => (
                  <tr key={a.id}>
                    <td>{a.name}</td>
                    <td className="num">{pct(a.match.aqua.share_seen_by_other)}</td>
                    <td className="num">{pct(a.match.snpp.share_seen_by_other)}</td>
                    <td className="num">{a.match.snpp.frp_median_alone_mw ?? "–"} MW</td>
                    <td className="num">{a.match.snpp.frp_median_matched_mw ?? "–"} MW</td>
                  </tr>))}</tbody>
              </table></div>
            )}
            <p className="small">Most VIIRS-only detections are small fires: their median fire radiative power is a fraction of the matched ones. Point-matching would throw away most of VIIRS. That is why Kiln Watch never pairs points. It calibrates totals, so the small fires VIIRS adds are carried in the ratio, and both originals stay in the downloads. The MODIS-against-VIIRS cross-check on every fire case uses the same idea. A match is a coincidence in space and time, not proof of one fire.</p>
          </Q>
          <Q n={1786} status="solved" ask="The global archive is about 45 GB of CSV. Global, or one place?">
            <p>Neither download is needed. DuckDB reads only an area's rows from the FIRMS archive mirrored as GeoParquet, in place. Nine areas are prebuilt; any box on Earth up to 16 square degrees builds in minutes from <a href="#pg=create" onClick={() => go("create")}>Create</a>, and the worldwide 30-day outlook comes from a single global aggregate.</p>
          </Q>
        </ol>
      </section>

      <section>
        <h2>Discussions #2016 and #1959: scope and own downloads</h2>
        <ol className="plain qa-list">
          <Q n={2016} status="solved" ask="Can we focus on one country or region?" official="yes, a selected area of interest; consider letting users pick other areas.">
            <p>Nine prebuilt areas on five continents, and any area anyone draws.</p>
          </Q>
          <Q n={1959} status="solved" ask="Can we use our own FIRMS downloads?" official="(Space Apps Navigator) yes; document source, product, period and coverage.">
            <p>Every area file records its FIRMS products and collection versions, the date range, the box, the build time and the code version. See provenance under Evidence on <a href="#pg=method" onClick={() => go("method")}>Proof</a>.</p>
          </Q>
        </ol>
      </section>

      <section>
        <h2>Still open</h2>
        <ol className="plain qa-list">
          <Q n={1879} status="open" ask="Cloud and view conditions (raised in a reply): no detection can mean no fire, or no clear view.">
            <p>Not solved yet. Kiln Watch divides by the days each satellite observed, but not by cloud-free views, so a cloudy month reads low for every satellite alike. The fix is to use the cloud class of the daily MODIS fire mask (MYD14A1) as a clear-sky denominator. It needs an Earth Engine build pass per area, and the calibration then has to be re-tested.</p>
          </Q>
        </ol>
      </section>

      <section>
        <h2>Raised elsewhere: NASA and partner sources</h2>
        <p className="muted small">Problems for anyone joining MODIS and VIIRS, named in NASA pages and papers rather than in the challenge threads.</p>
        <ol className="plain qa-list">
          <Q src={SRC.modis} status="solved" ask="Terra and Aqua are drifting and will stop." official="both platforms are drifting out of their designed orbits and will shut down in late 2026 / early 2027 (CAMS quotes January 2027 for Terra, around September 2027 for Aqua).">
            <p>Aqua's overpass time and archive version are read from the FIRMS timestamps. From the measured drift onset, the record runs on VIIRS alone, still on the Aqua 2002–2020 scale. The MODIS-denial test on <a href="#pg=after" onClick={() => go("after")}>After MODIS</a> shows what happens when MODIS is gone.</p>
          </Q>
          <Q src={SRC.snpp} status="open" ask="Terra is the only morning overpass; after it, no NASA morning fire detections." official="MODIS Terra provides the only morning overpass, about 3 hours before Aqua; NASA is investigating alternatives.">
            <p>The record stays consistent, because it is defined on Aqua's early-afternoon and post-midnight passes, which NOAA-20 and NOAA-21 continue. But it never measured morning burning, and nothing in Kiln Watch replaces Terra. Fires that burn and die out before the afternoon are under-counted in every year alike.</p>
          </Q>
          <Q src={SRC.faq} status="open" ask="Near-real-time data differ from standard processing." official="NRT positions can be less accurate (Aqua up to 12 hours after a manoeuvre), NRT has no hotspot type, and NRT sets day/night by orbit direction while standard data use the solar zenith angle.">
            <p>Partly handled: near-real-time months are labelled <i>provisional</i>, and cells are typed from their standard history. Not handled: the different day/night rule. Our calibration splits day and night, so at high latitudes a provisional month can put some detections in the other half. FIRMS publishes standard data for those months 2–3 months later, and an area has to be rebuilt to use them.</p>
          </Q>
          <Q src={SRC.li} status="open" ask="VIIRS fire radiative power is smaller than MODIS for large boreal fires (about 47% in that study).">
            <p>Kiln Watch harmonizes hotspot counts, not fire radiative power (FRP). FRP is shown per detection and used to describe fire size, but it is not put on one scale, so FRP totals must not be compared across the 2012 switch.</p>
          </Q>
          <Q src={SRC.night} status="solved" ask="Low-confidence VIIRS detections are systematically absent at night (preprint).">
            <p>We drop VIIRS low-confidence detections day and night alike, and calibrate day and night separately, so a night-only gap in that class cannot create a day/night step.</p>
          </Q>
          <Q src={SRC.pod} status="open" ask="The chance of detecting a fire differs by region: under 30% for MODIS in some equatorial areas (40% for VIIRS).">
            <p>Each area gets its own calibration, so a regional difference between the sensors is carried. A region where both sensors miss fires (cloud, short fires) stays low in every year, and that is the cloud question above, still open.</p>
          </Q>
        </ol>
      </section>

      <section>
        <h2>Our limitations, plainly</h2>
        <p>The scorecard on <a href="#pg=method" onClick={() => go("method")}>Proof</a> shows where the record misses, area by area: not every area lands inside its no-change range, and some intervals are too narrow in years unlike the calibration years. Beyond that:</p>
        <ul className="plain small">{LIMITS.map((l) => <li key={l}>{l}</li>)}</ul>
      </section>

      <section>
        <h2>Ask what we have not answered</h2>
        <p>Found a question, a limitation or a source we missed? <a href="#pg=contact" onClick={() => go("contact")}>Tell us</a>. A good question gets added to this page with its answer, or with "open" if we do not have one.</p>
      </section>

      <section>
        <h2>What we looked for and did not find</h2>
        <ul className="plain small">
          <li><b>nasa/MODIS-VIIRS-Data-Resources</b> (LP DAAC) is a set of access tutorials. Its five issues are closed documentation pull requests, with no harmonization issues.</li>
          <li>Other challenge threads ask about event rules (#2011 downloading before the start, #1932 tools, #1981 and #2057 eligibility), not science.</li>
          <li>Threads read on 14 November 2026. Numbers on this page come from <code>scripts/discussion_checks.py</code>{c ? `, built ${c.built_at.slice(0, 10)} at code ${c.code_version ?? "unknown"}` : ""}.</li>
        </ul>
      </section>
    </>
  );
}
