import { Suspense, lazy, useEffect, useState } from "react";
import { BurnedArea, KilnCheck, api, fmt } from "../api";
import { Method as Evidence } from "../Record";
import { Scorecard } from "./Proof";
import { AreaSelect, PageHead, PageProps, useRegion } from "./shared";

const Satellite = lazy(() => import("./SatelliteFigure")); // the figure and its kit load only on this page

const STEPS: [string, string][] = [
  ["Data", "Every FIRMS detection (MODIS C6.1, VIIRS 375 m C2, standard and near-real-time), read from the public Portolan GeoParquet mirror with DuckDB. No key needed; CC0."],
  ["Filtering", "Drop VIIRS low-confidence and MODIS confidence below 30, with the effect on totals reported. Persistent heat sources that FIRMS types as static (flares, industry, a few kilns) are separated into their own class; brick kilns are counted from a published kiln map and night lights instead, because FIRMS sees few of them."],
  ["Observing opportunity", "The share of days each satellite delivered data anywhere on Earth, measured per period from the data itself. Launches, gaps and the Suomi-NPP end are never hard-coded. Counts are divided by it."],
  ["Calibration", "A ratio of totals per calendar month, day and night separately, shrunk toward the pooled ratio by empirical Bayes. Chain: Terra to Aqua, Suomi-NPP to Aqua (before Aqua's orbit drift), NOAA-20 to Suomi-NPP, NOAA-21 to NOAA-20. Chain-closure mismatch is added to the error."],
  ["Stitching", "An inverse-variance mean of the satellites observing each period, with intervals widened to the coverage measured in the denial test."],
  ["Comparison", "Median, ratio, percentile and rank against the same period in other complete years. Fire counts are skewed, so there are no sigma thresholds. The Early warning level uses the same percentiles."],
];

const WHY: [string, string][] = [
  ["It is measured on what we publish.", "The gap between sensors is measured on monthly detection totals, the very quantity in the record, so no model of fire physics has to be right first. VIIRS sees many small fires MODIS cannot (Schroeder et al. 2014; Giglio et al. 2016), and the ratio absorbs that difference as it is."],
  ["A ratio of totals, not a regression.", "Both sensors count with error, so a regression of one on the other is biased toward zero (regression dilution, Frost & Thompson 2000). For Poisson counts with a common rate ratio, the ratio of the two totals is the maximum-likelihood estimate of that ratio."],
  ["Seasonal, but not over-fitted.", "Each calendar month has its own ratio, pulled toward the all-year ratio by empirical Bayes (Efron & Morris 1975), with the between-month variance estimated from the data by the method of moments (DerSimonian & Laird 1986). A month with little data borrows strength; a month with plenty keeps its own value."],
  ["No near-simultaneous pairs needed.", "Methods that match single fires or pixels need the two satellites to look within minutes. Aqua's afternoon pass has drifted later since 2020, so those pairs become rare. Monthly totals only need both satellites to have flown that month."],
  ["Tested by taking satellites away.", "MODIS is switched off in 2017–2020 and rebuilt from VIIRS; Suomi-NPP is withheld; calibration is borrowed from other areas. Intervals are widened by split conformal prediction (Lei et al. 2018) and checked on months the widening never saw. Trends use Sen's slope (Sen 1968)."],
  ["The main alternative was tried, and lost.", "MODIS detects a fire only above a certain fire power, so the sensor ratio could follow the fire mix. We added a term for the month's mean VIIRS fire power per detection, fitted on 2012–2016 and scored on 2017–2020. It helps a few areas with large fires, but it does not help on average and it inflates bias in others: see the fire-size column of the scorecard and the Evidence below. It is not used."],
];

const REFS: [string, string][] = [
  ["Schroeder, Oliva, Giglio & Csiszar (2014). The New VIIRS 375 m active fire detection data product. Remote Sensing of Environment 143, 85–96", "https://doi.org/10.1016/j.rse.2013.12.008"],
  ["Giglio, Schroeder & Justice (2016). The collection 6 MODIS active fire detection algorithm and fire products. Remote Sensing of Environment 178, 31–41", "https://doi.org/10.1016/j.rse.2016.02.054"],
  ["Frost & Thompson (2000). Correcting for regression dilution bias. JRSS A 163(2), 173–189", "https://doi.org/10.1111/1467-985X.00164"],
  ["Efron & Morris (1975). Data analysis using Stein's estimator and its generalizations. JASA 70(350), 311–319", "https://doi.org/10.1080/01621459.1975.10479864"],
  ["DerSimonian & Laird (1986). Meta-analysis in clinical trials. Controlled Clinical Trials 7(3), 177–188", "https://doi.org/10.1016/0197-2456(86)90046-2"],
  ["Lei, G'Sell, Rinaldo, Tibshirani & Wasserman (2018). Distribution-free predictive inference for regression. JASA 113(523), 1094–1111", "https://doi.org/10.1080/01621459.2017.1307116"],
  ["Sen (1968). Estimates of the regression coefficient based on Kendall's tau. JASA 63(324), 1379–1389", "https://doi.org/10.1080/01621459.1968.10480934"],
];

export const LIMITS = [
  "Exposure is a static context layer joined to the 0.1° grid. Population is WorldPop's modelled 2020 surface, not a census; hospitals, schools and roads are an OpenStreetMap snapshot from the query date; farmland is ESA WorldCover 2021 cropland, one year of land cover. No fire perimeter, no smoke, no fire spread, no crop loss and no impact estimate.",
  "An outside event (EONET, GDACS) is one point on a fire that can span several cells and start before its first hotspots, so it is matched to the record in its 0.1° cell and the 8 around it, in the event month and the next. Those windows are judgement calls, not fitted. Press counts are matched by place names and fire words only, so a count says reports exist, not that they describe this fire; the press witness never says a fire did not happen, and a witness whose search failed or does not reach back that far is shown as \"could not look\".",
  "The burned-area witness (MODIS MCD64A1) sums the burn scar mapped in the case cell and its 8 neighbours that month. It confirms fire on the ground, but its mapping is guided by MODIS active fires, so it is not fully independent of the hotspot record.",
  "No cloud-cover denominator yet, so cloudy months read low for every satellite alike. Observing days are global, not regional clear-sky opportunity.",
  "Near-real-time rows carry no FIRMS type. Untyped heat anomalies outside the static mask remain in the vegetation series; the latest unclassified share is shown for each area.",
  "The interval widening factor is fitted on a VIIRS-only denial reconstruction; its measured out-of-sample coverage is shown rather than assumed to be exactly 95%.",
  "Calibration is per area, calendar month and day/night. It is not stratified by land cover, fire size or scan angle, so a year with an unusual fire mix is biased. A fire-size term was tested and did not help on average; in some large-fire areas it did (scorecard), so an area-specific version is the open next step.",
  "Terra to Aqua is the weakest link and is used only for 2000 to 2002. Aqua's data changed after 2020 (orbit drift, and a new MODIS archive version); from the onset measured from the data the record uses VIIRS only, still on the Aqua 2002–2020 scale.",
  "MODIS changes collection (6.03 to 61.03) at the start of 2023; this is listed but not yet step-tested.",
  "Near-real-time rows cannot be compared with standard processing from the mirror, so those months are labelled provisional, not adjusted.",
  "Brick-kiln evidence is a published Sentinel-2 kiln map (kiln structures in the 2024-25 dry season, about 8 in 10 right inside labelled footprints, about 2 in 10 outside) Black Marble night lights, a weak witness because city lights drown a kiln's, and Sentinel-1 radar contrast with the surroundings (dry season against monsoon), which also responds to buildings and moisture. It shows structures, not kilns in operation, and the map is licensed for non-commercial use.",
  "GDELT search starts in 2017 and GDACS wildfire events in 2021. Reports are matched by place and date only; Google News RSS returns at most about 100 items per query, so busy windows are split by year and language.",
  "The 30-day outlook is on the Aqua MODIS scale but counted by NOAA-20 VIIRS from Aqua's measured drift onset and for the last 30 days, with a per-cell ratio fitted on earlier years (the held-out error is on the Early warning page). It is a climatology plus the present anomaly, never a forecast, and it has not been backtested as a predictor of later seasons.",
  "The outlook drops cells whose typed history is 30% or more static sources; a new gas-flare field can look above normal until FIRMS types it.",
];

/** What the independent checks found. A check that has not been run reads as "not done", never as a zero. */
function Validation({ burned, kilns }: { burned: BurnedArea | null; kilns: KilnCheck | null }) {
  if (!burned && !kilns) {
    return <p className="muted">Neither independent check has been run in this deployment. They are run by
      <code>scripts/validation/burned_area.py</code> and <code>scripts/validation/kilns.py</code> and their
      results are published here when they complete.</p>;
  }
  return (
    <>
      {burned && (
        <div className="method-body">
          <p><b>Burned area (NASA MCD64A1 C6.1).</b> Burned area is an independent physical measurement: it
            counts the pixels that changed, not the fires a satellite saw. The harmonized record is compared
            with it month by month over {burned.window.first.slice(0, 4)}–{burned.window.last.slice(0, 4)} in
            {" "}{Object.keys(burned.per_area).length} areas.</p>
          <table className="tbl">
            <thead><tr><th>Series against burned area</th><th>Rank correlation (median of the areas)</th></tr></thead>
            <tbody>
              <tr><td>Harmonized Aqua-scale estimate</td><td className="num">{fmt(burned.summary.median_spearman_harmonized_vs_burned, 2)}</td></tr>
              <tr><td>Raw all-sensor detections</td><td className="num">{fmt(burned.summary.median_spearman_raw_vs_burned, 2)}</td></tr>
            </tbody>
          </table>
          <p><b>The 2012 step.</b> VIIRS Suomi-NPP joined in 2012. MCD64A1 is built from MODIS alone, so burned
            area must not move when VIIRS arrives. The same twelve calendar months of 2012 against the same
            months of 2009–2011, as a ratio:</p>
          <table className="tbl">
            <thead><tr><th>Series</th><th>2012 ÷ 2009–2011</th></tr></thead>
            <tbody>
              <tr><td>Raw all-sensor detections</td><td className="num">×{fmt(burned.summary.median_step_2012_raw, 2)}</td></tr>
              <tr><td>Harmonized Aqua-scale estimate</td><td className="num">×{fmt(burned.summary.median_step_2012_harmonized, 2)}</td></tr>
              <tr><td>Burned area (independent)</td><td className="num">×{fmt(burned.summary.median_step_2012_burned_area, 2)}</td></tr>
            </tbody>
          </table>
          <p className="muted small">The raw count jumps, burned area does not, so the jump was an instrument
            change and not a change on the ground. {burned.summary.areas_harmonized_at_least_as_good_as_raw != null &&
              <>The harmonized record tracks burned area at least as well as the raw counts in{" "}
                {burned.summary.areas_harmonized_at_least_as_good_as_raw} of {burned.summary.areas_compared} areas. </>}
            {Object.keys(burned.catalogue_gaps ?? {}).length > 0 &&
              <>The Planetary Computer mirror is missing a few product months; they are listed in the file and left
                out of the comparison. </>}</p>
        </div>
      )}
      {kilns && (
        <div className="method-body">
          <p><b>Brick kilns (APAD inventory, {kilns.area.name}).</b> The published persistent-heat cells are
            compared with the {kilns.inventory.name} list of operating kilns, and with randomly placed cells of
            the same number in the same area:</p>
          <table className="tbl">
            <thead><tr><th>Match radius</th><th>Cells on a kiln</th><th>By chance</th><th>Kilns covered</th><th>By chance</th></tr></thead>
            <tbody>
              {kilns.results.map((r) => (
                <tr key={r.radius_km}>
                  <td>{r.radius_km} km</td>
                  <td className="num">{r.cells_matching_a_kiln} of {r.published_cells} ({fmt(r.precision * 100, 1)}%)</td>
                  <td className="num">{fmt(r.random_baseline_precision * 100, 1)}%</td>
                  <td className="num">{r.kilns_matching_a_cell} of {r.inventory_kilns_in_area} ({fmt(r.recall * 100, 1)}%)</td>
                  <td className="num">{fmt(r.random_baseline_recall * 100, 1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="warn">{kilns.verdict}</p>
          <p className="muted small">Inventory: {kilns.inventory.name}, {kilns.inventory.licence}, retrieved
            {" "}{kilns.inventory.retrieved_at.slice(0, 10)} (SHA-256 {kilns.inventory.sha256.slice(0, 12)}…). The
            Sentinel-2 kiln map behind the Bangladesh page is a second, independent inventory; it reaches the same
            conclusion about the persistent-heat class.</p>
        </div>
      )}
    </>
  );
}

export default function MethodPage({ regions }: PageProps) {
  const [rid, setRid] = useState("");
  const id = rid || regions.find((r) => r.preset)?.id || regions[0]?.id || null;
  const { region, err } = useRegion(id);
  const [burned, setBurned] = useState<BurnedArea | null>(null);
  const [kilns, setKilns] = useState<KilnCheck | null>(null);
  const [checked, setChecked] = useState(false);
  useEffect(() => {
    let live = true;
    Promise.all([api.burnedArea(), api.kilnCheck("dhaka-kilns")]).then(([b, k]) => {
      if (!live) return;
      setBurned(b); setKilns(k); setChecked(true);
    });
    return () => { live = false; };
  }, []);
  return (
    <>
      <PageHead kicker="How it works" title="Proof" lead="How MODIS and every VIIRS satellite are put on one scale, how that is tested on years the calibration never saw, and what the result does not mean." />

      <section>
        <h2>Nine areas, one scorecard</h2>
        <Scorecard regions={regions} />
      </section>

      <section>
        <h2>The reference instrument</h2>
        <Suspense fallback={<div className="skeleton tall" />}><Satellite /></Suspense>
      </section>

      <section>
        <h2>The question</h2>
        <p>Can MODIS and VIIRS detections be combined into one record whose level does not change when satellites arrive or leave, and how accurate is it on data the calibration never saw?</p>
        <p><b>Primary unit: hotspots on the Aqua MODIS scale</b>, the vegetation-fire detections Aqua MODIS would have recorded in its early-afternoon and post-midnight passes. That orbit is the only one observed continuously from 2002 through Suomi-NPP, NOAA-20 and NOAA-21. Converting VIIRS down to the MODIS scale discards information and is well-posed; the reverse would have to invent small fires MODIS never saw, so the VIIRS-scale view is marked <i>modelled</i> before 2012.</p>
      </section>

      <section>
        <h2>Six steps</h2>
        <ol className="steps long">{STEPS.map(([t, d]) => <li key={t}><b>{t}.</b> {d}</li>)}</ol>
      </section>

      <section>
        <h2>Why this method</h2>
        <ul className="plain">
          {WHY.map(([t, d]) => <li key={t}><b>{t}</b> {d}</li>)}
        </ul>
        <p className="muted small">Each part is a published, standard tool; the way they are put together for MODIS and VIIRS is ours, and the tests on this page are its proof.</p>
        <ul className="plain small">
          {REFS.map(([t, u]) => <li key={u}><a href={u} target="_blank" rel="noreferrer">{t}</a></li>)}
        </ul>
      </section>

      <section>
        <h2>The 30-day outlook</h2>
        <p>The globe in the Explorer and on Early warning shows, for every half-degree cell on Earth, two things measured from the same instrument since 2003: <b>what the next 30 calendar days usually bring</b> (median and 90th percentile of earlier years) and <b>how unusual the last 30 days were</b> (percentile against the same days in each earlier year). Aqua MODIS is used alone because it is the one sensor observed every year since 2003, so no calibration enters the comparison.</p>
        <ul className="plain">
          <li><b style={{ color: "#F6C64F" }}>Season ahead</b>: the next 30 days usually bring at least 5 hotspots.</li>
          <li><b style={{ color: "#FF9A3C" }}>Above normal</b>: the last 30 days are at or above the 90th percentile of the same days in earlier years, and at least 5 hotspots.</li>
          <li><b style={{ color: "#FF3B2F" }}>Watch</b>: both at once, a usually active season starting while already above normal. These pulse on the globe and can trigger email alerts.</li>
          <li><b>Rising</b>: the usual next 30 days are at least twice the usual last 30, so the season normally ramps up now.</li>
        </ul>
        <p className="muted small">One pass over the whole-Earth aggregate (about 10 seconds), cached per data day. Watch cells are grouped and named with OpenStreetMap so a person can read where to look.</p>
      </section>

      <section>
        <h2>News and events</h2>
        <table className="tbl">
          <thead><tr><th>Source</th><th>What it adds</th><th>Coverage</th></tr></thead>
          <tbody>
            <tr><td>NASA EONET</td><td>Curated natural-event records with coordinates</td><td>mostly 2016 onward</td></tr>
            <tr><td>GDACS (EU JRC, UN OCHA)</td><td>Wildfire alerts with burned area from GWIS</td><td>2017 onward, global</td></tr>
            <tr><td>Google News RSS</td><td>Local outlets in English, Spanish, Portuguese, French, Indonesian, Hindi and Bangla</td><td>all years, about 100 items per query</td></tr>
            <tr><td>GDELT DOC 2.0</td><td>Global online news in 65 languages, monthly volume timelines</td><td>2017 onward</td></tr>
            <tr><td>ReliefWeb (optional)</td><td>Humanitarian situation reports</td><td>with an approved app name</td></tr>
          </tbody>
        </table>
        <p className="muted small">Each source is listed with its count and any error, so a failed source is never read as "no reports". Gemini may only drop headlines that are not about a vegetation fire there; it never adds data.</p>
      </section>

      <section>
        <h2>Fire cases and their witnesses</h2>
        <p>Every fire we publish is a case with several independent witnesses: the harmonized record, a MODIS-against-VIIRS cross-check, NASA EONET, GDACS and the press. A witness that could not see says so. Where an agency recorded a fire the record does not show, the case says that too. Absence of a report is never evidence of absence.</p>
        <p className="muted small">The Cases tab in the Explorer lists them with a verdict: corroborated, reported, satellites only, record missed it, could not see, or nobody saw. The cross-check agreement band (within 25%) is a judgement band, not a statistical test.</p>
      </section>

      <section>
        <h2>What is in the fire cells</h2>
        <p>Population (WorldPop 2020, 1 km) and infrastructure (OpenStreetMap) inside the 0.1° cells where the record shows fire. This is a context layer: FIRMS gives detections, not a fire perimeter, so nothing here says the fire reached a place, and nothing here models smoke or fire spread. Population is modelled 2020 data.</p>
      </section>

      <section>
        <h2>What this is not</h2>
        <ul className="plain">
          <li>Detections are not fires, and not burned area.</li>
          <li>Missing news is never evidence that nothing happened, and a report is never proof of a detection.</li>
          <li>The early warning compares with history. It does not forecast.</li>
          <li>Nothing on screen is typed in: every number comes from the pipeline, and each file records its code version.</li>
        </ul>
      </section>

      <section>
        <h2>Evidence for an area</h2>
        <p className="muted small">Hold-out tests, sensor-denial rehearsals, placebo steps, chain closure, calibration factors and provenance, computed for the area you pick.</p>
        {id && <AreaSelect regions={regions} value={id} onChange={setRid} />}
        <div className="method-body">
          {err && <p className="error">{err}</p>}
          {!region && !err && <div className="skeleton tall" />}
          {region && <Evidence r={region} cls="veg" />}
        </div>
      </section>

      <section>
        <h2>Checked against other data</h2>
        <p>Checks that run outside the pipeline and publish their results, whether they pass or not. A check that
          fails, or that has not been run, is written down as such: no result is ever quietly omitted.</p>
        {checked ? <Validation burned={burned} kilns={kilns} /> : <div className="skeleton tall" />}
      </section>

      <section>
        <h2>Known limitations</h2>
        <ul className="plain">{LIMITS.map((l) => <li key={l}>{l}</li>)}</ul>
      </section>

      <section>
        <h2>Data and credits</h2>
        <p className="small">We acknowledge the use of data and/or imagery from NASA's Fire Information for Resource Management System (FIRMS) (https://earthdata.nasa.gov/firms), part of NASA's Earth Observing System Data and Information System (EOSDIS). Burned area for the area-level check is NASA MCD64A1 Collection 6.1, from the LP DAAC via the public Planetary Computer catalogue; the per-case burned-area witness uses the same product through Google Earth Engine. The APAD brick-kiln inventory (CC BY 4.0) backs the independent kiln cross-check. Detections via the Portolan FIRMS mirror (CC0). Imagery: NASA GIBS. Night lights: NASA Black Marble (VIIRS Day/Night Band) via GIBS. Events: NASA EONET and GDACS (European Commission JRC, UN OCHA). News: The GDELT Project and Google News RSS (personal, non-commercial use). Place names: OpenStreetMap Nominatim. Base map: OpenFreeMap and OpenStreetMap contributors. Kiln Watch is an independent project and not an official NASA product.</p>
      </section>
    </>
  );
}
