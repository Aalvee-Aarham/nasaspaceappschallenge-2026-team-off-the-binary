import { useEffect, useState } from "react";
import { Meta, Num, RegionItem, api, fmt } from "../api";

const times = (v: Num | undefined) => (v == null ? "–" : `×${v.toFixed(2)}`);
const sgn = (v: Num | undefined) => (v == null ? "–" : `${v > 0 ? "+" : ""}${fmt(v, 1)}%`);
const cov = (v: Num | undefined) => (v == null ? "–" : `${fmt(v * 100, 0)}%`);
const inRange = (m: Meta) => {
  const h = m.steps.VIIRS_SNPP?.harmonized_excess;
  return h != null && m.placebo != null && h >= m.placebo.excess_p05 && h <= m.placebo.excess_p95;
};

/** One row per preset area; every cell is read from that area's meta.json. */
export function Scorecard({ regions }: { regions: RegionItem[] }) {
  const [rows, setRows] = useState<Meta[] | null>(null);
  const [err, setErr] = useState("");
  const presets = regions.filter((r) => r.preset);
  const key = presets.map((r) => r.id).join();
  useEffect(() => {
    if (!presets.length) return;
    let live = true;
    Promise.all(presets.map((r) => api.meta(r.id))).then((m) => live && setRows(m)).catch((e) => live && setErr(e.message));
    return () => { live = false; };
  }, [key]);

  if (err) return <p className="error">{err}</p>;
  if (!rows) return <div className="skeleton tall" />;

  const short = rows.filter((m) => m.steps.VIIRS_SNPP && !inRange(m));
  const worstTransfer = rows.filter((m) => (m.transfer_validation?.transferred_from_other_regions.bias_pct ?? 0) > 50 || (m.transfer_validation?.transferred_from_other_regions.bias_pct ?? 0) < -50);
  return (
    <>
      <div className="scroll">
        <table className="tbl">
          <caption className="muted small" style={{ textAlign: "left" }}>Each row is one area. Every value is read from that area's published results.</caption>
          <thead><tr>
            <th scope="col">Area</th>
            <th scope="col">Raw jump at the Suomi-NPP arrival</th>
            <th scope="col">Harmonized jump</th>
            <th scope="col">Error if MODIS had ended (raw → ours)</th>
            <th scope="col">Interval coverage (widened / out of sample)</th>
            <th scope="col">Chain closure</th>
            <th scope="col">Borrowed calibration error</th>
            <th scope="col">Fire-size term, log error (ours → with term)</th>
            <th scope="col">Early-warning skill, day 15</th>
          </tr></thead>
          <tbody>{rows.map((m) => {
            const s = m.steps.VIIRS_SNPP, d = m.denial.modis_ends_2016, bt = m.warning_backtest?.by_day?.["15"]?.elevated, fz = m.transfer_validation?.fire_size_term;
            return (
              <tr key={m.id}>
                <th scope="row">{m.name}</th>
                <td className="num">{times(s?.raw_all_sensors_excess)}</td>
                <td className="num">{times(s?.harmonized_excess)}{s && inRange(m) && <span className="muted small"> within no-change range</span>}</td>
                <td className="num">{sgn(d.uncalibrated.bias_pct)} → <b>{sgn(d.ours_seasonal_eb.bias_pct)}</b></td>
                <td className="num">{cov(d.ours_seasonal_eb.interval_coverage)} / {cov(d.ours_seasonal_eb.interval_coverage_out_of_sample)}</td>
                <td className="num">{sgn(m.closure.veg_det_D?.[0]?.mismatch_pct)}</td>
                <td className="num">{sgn(m.transfer_validation?.transferred_from_other_regions.bias_pct)}</td>
                <td className="num">{fz ? `${fmt(fz.ours.log_mae, 3)} → ${fmt(fz.with_size_term.log_mae, 3)}` : "–"}</td>
                <td className="num">{bt?.pss != null ? fmt(bt.pss, 2) : "not scored"}</td>
              </tr>
            );
          })}</tbody>
        </table>
      </div>
      <p className="muted small">How to read it: a harmonized jump near ×1.00 means the satellite arrival left no artificial step, and raw jumps show how large the artifact would have been. Error if MODIS had ended is the bias of rebuilding 2017–2020 from VIIRS alone. Chain closure is how far two routes to the Aqua scale disagree. The fire-size term column is the mean absolute log error of predicting Aqua from Suomi-NPP over 2017–2020, without and with a term for the month's mean VIIRS fire power (lower is better). Early-warning skill is the Peirce skill score of the percentile rule run as if it were day 15 of each past month (1 is perfect, 0 is no better than chance).</p>
      {(short.length > 0 || worstTransfer.length > 0) && (
        <>
          <h3>Where it falls short</h3>
          <ul className="plain small">
            {short.map((m) => <li key={`j${m.id}`}>{m.name}: the harmonized jump ({times(m.steps.VIIRS_SNPP.harmonized_excess)}) is outside the range of the no-change test{m.placebo ? ` (${times(m.placebo.excess_p05)} to ${times(m.placebo.excess_p95)})` : ""}.</li>)}
            {worstTransfer.map((m) => <li key={`t${m.id}`}>{m.name}: borrowing calibration from other areas is off by {sgn(m.transfer_validation!.transferred_from_other_regions.bias_pct)}, so a new area needs its own record.</li>)}
          </ul>
        </>
      )}
    </>
  );
}
