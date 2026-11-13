import { useState } from "react";
import { Gantt, Line, LineChart } from "../Record";
import { Num, SENSOR_COLOR, fmt } from "../api";
import { AreaSelect, PageHead, PageProps, useRegion } from "./shared";

const hhmm = (v: number) => `${Math.floor(v)}:${String(Math.round((v % 1) * 60) % 60).padStart(2, "0")}`;
const pct = (v: Num | undefined) => (v == null ? "–" : `${v > 0 ? "+" : ""}${fmt(v, 1)}%`);
const isoWeekOf = (d: string) => {
  const t = new Date(d + "T00:00:00Z");
  t.setUTCDate(t.getUTCDate() + 3 - ((t.getUTCDay() + 6) % 7));
  const y = t.getUTCFullYear();
  return `${y}-W${String(1 + Math.floor((t.getTime() - Date.UTC(y, 0, 1)) / 604800000)).padStart(2, "0")}`;
};

export default function AfterModis({ regions }: PageProps) {
  const [rid, setRid] = useState("");
  const [off, setOff] = useState<"modis" | "snpp">("modis");
  const id = rid || regions.find((r) => r.preset)?.id || regions[0]?.id || null;
  const { region, err } = useRegion(id);
  const m = region?.meta;
  const den = m?.denial.modis_ends_2016, wh = m?.denial.snpp_withheld, cut = m?.denial.snpp_cutover, ao = m?.aqua_overpass;
  const mode = off === "snpp" && wh ? "snpp" : "modis";

  // Raw VIIRS counts for the same months as the denial series: what you would see without calibrating.
  const rawViirs = (periods: string[]): Num[] => {
    const b = region!.monthly;
    return periods.map((p) => {
      const i = b.periods.indexOf(p);
      return i < 0 ? null : (b.raw.VIIRS_SNPP?.det[i] ?? 0) + (b.raw.VIIRS_NOAA20?.det[i] ?? 0);
    });
  };
  const years = ao ? Object.keys(ao.years) : [];
  const onsetYear = ao?.onset ? ao.onset.slice(0, 4) : null;

  return (
    <>
      <PageHead kicker="Continuity" title="After MODIS" lead="NASA's MODIS satellites are drifting and nearing the end of their lives, and Suomi-NPP has already stopped. Switch satellites off and see whether the record still holds." />
      {regions.length > 0 && id && <AreaSelect regions={regions} value={id} onChange={setRid} />}
      {err && <p className="error">{err}</p>}
      {!region && !err && <div className="skeleton tall" />}

      {region && m && den && (
        <>
          <section>
            <h2>Switch a satellite off</h2>
            <div className="seg" role="radiogroup" aria-label="Satellite to switch off">
              <button role="radio" aria-checked={mode === "modis"} className={mode === "modis" ? "on" : ""} onClick={() => setOff("modis")}>MODIS ends in {den.test[0].slice(0, 4)}</button>
              {wh && <button role="radio" aria-checked={mode === "snpp"} className={mode === "snpp" ? "on" : ""} onClick={() => setOff("snpp")}>Suomi-NPP withheld</button>}
            </div>
            {mode === "modis" && den.series ? (
              <>
                <LineChart x={den.series.periods} name={`${m.id}-after-modis`} label="Aqua observed, rebuilt from VIIRS alone, and raw VIIRS counts"
                  band={{ lo: den.series.lo, hi: den.series.hi, color: "#56B4E9" }}
                  lines={[
                    { name: "What Aqua MODIS saw", color: SENSOR_COLOR.MODIS_A, vals: den.series.aqua, wide: true },
                    { name: "Rebuilt from VIIRS alone, 95% interval", color: "#56B4E9", vals: den.series.predicted, dash: "4 3" },
                    { name: "Raw VIIRS detections, not harmonized", color: "#9AA8BC", vals: rawViirs(den.series.periods), dash: "1 3" },
                  ]} />
                <ul className="plain small">
                  <li>Raw VIIRS counts differ from what Aqua saw by <b>{pct(den.uncalibrated.bias_pct)}</b> on average.</li>
                  <li>The harmonized rebuild is off by <b>{pct(den.ours_seasonal_eb.bias_pct)}</b>.</li>
                  <li>Month-to-month rank agreement with Aqua (Spearman ρ): <b>{fmt(den.ours_seasonal_eb.spearman, 2)}</b>.</li>
                </ul>
                <p className="muted small">Calibrated on {den.train.join(" to ")} only, then {den.test.join(" to ")} rebuilt from VIIRS and compared with what Aqua recorded ({den.n} months).
                  {den.ours_seasonal_eb.interval_coverage_out_of_sample != null && ` The 95% interval contained Aqua's value in ${fmt(den.ours_seasonal_eb.interval_coverage_out_of_sample * 100, 0)}% of the months the widening factor never saw.`}</p>
              </>
            ) : mode === "snpp" && wh ? (
              <>
                <LineChart x={wh.series.periods} name={`${m.id}-after-snpp`} label="Harmonized record with and without Suomi-NPP"
                  lines={[{ name: "All satellites", color: "#FCFFA4", vals: wh.series.all, wide: true }, { name: "Suomi-NPP withheld", color: "#56B4E9", vals: wh.series.without_snpp, dash: "4 3" }]} />
                <p>Without Suomi-NPP the record moves by <b>{fmt(wh.mean_abs_diff_pct, 1)}%</b> on average over {wh.n} months ({wh.window.join(" to ")}).</p>
              </>
            ) : <p className="muted small">Not enough data for this chart.</p>}
          </section>

          {cut && (
            <section>
              <h2>The real switch-off</h2>
              <LineChart x={cut.periods} logY name={`${m.id}-snpp-cutover`} label="Weekly hotspots around the Suomi-NPP end"
                band={{ lo: cut.lo, hi: cut.hi, color: "#FCFFA4" }}
                marks={[{ at: Math.max(0, cut.periods.findIndex((k) => k >= isoWeekOf(cut.snpp_last_observed))), color: SENSOR_COLOR.VIIRS_SNPP, text: "S-NPP ends" }]}
                lines={[{ name: "Raw detections, all satellites", color: "#9AA8BC", vals: cut.raw_all, dash: "4 3" } as Line, { name: "Harmonized, 95% interval", color: "#FCFFA4", vals: cut.harmonized, wide: true }]} />
              <p className="muted small">The last Suomi-NPP detection in the data is dated {cut.snpp_last_observed}. The harmonized record carries on from NOAA-20 and NOAA-21; the latest week is still in progress.</p>
            </section>
          )}

          {ao && years.length > 0 && (
            <section>
              <h2>Aqua is drifting</h2>
              <LineChart x={years} name={`${m.id}-aqua-overpass`} label="Aqua MODIS local overpass hour by year" yFmt={hhmm}
                marks={onsetYear && years.includes(onsetYear) ? [{ at: years.indexOf(onsetYear), color: "#E69F00", text: "onset" }] : undefined}
                lines={[{ name: "Median local solar time of Aqua daytime detections", color: SENSOR_COLOR.MODIS_A, vals: years.map((y) => ao.years[y]), wide: true }]} />
              <p>Aqua's afternoon pass has moved from <b>{ao.baseline_hour == null ? "–" : hhmm(ao.baseline_hour)}</b> to <b>{hhmm(ao.years[years[years.length - 1]])}</b> local time.
                {ao.onset && <> From <b>{ao.onset}</b> the record uses VIIRS only, still on the Aqua 2002–2020 scale.</>}
                {ao.version_change && <> The MODIS archive also changed algorithm version (<b>{ao.version_change.version}</b>) in <b>{ao.version_change.from}</b>.</>}</p>
              <p className="muted small">{ao.rule}</p>
            </section>
          )}

          <section>
            <h2>Which satellites, when</h2>
            <Gantt sensors={m.sensors} through={m.data_through} />
          </section>
          <p className="muted small">Detections are not fires and not burned area. These are tests on past years, not forecasts.</p>
        </>
      )}
    </>
  );
}
