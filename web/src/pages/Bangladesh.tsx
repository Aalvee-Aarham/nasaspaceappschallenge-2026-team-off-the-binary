import { LineChart } from "../Record";
import { MONTH_SHORT, Num, fmt } from "../api";
import { PageHead, PageProps, useRegion } from "./shared";

const median = (xs: number[]) => {
  if (!xs.length) return null;
  const s = [...xs].sort((a, b) => a - b), h = s.length >> 1;
  return s.length % 2 ? s[h] : (s[h - 1] + s[h]) / 2;
};

// ponytail: English only. A Bangla toggle needs strings written or reviewed by a native speaker; add { en, bn } here then.
export default function Bangladesh({ go, openRegion }: PageProps) {
  const { region, err } = useRegion("dhaka-kilns");
  const m = region?.meta, b = region?.monthly;

  // median per calendar month over complete months, harmonized (Aqua scale)
  const byMonth = (v: Num[]) => MONTH_SHORT.map((_, mo) => median(b!.periods.flatMap((p, i) => (+p.slice(5) === mo + 1 && !b!.partial[i] && v[i] != null ? [v[i] as number] : []))));
  const st = m?.steps.VIIRS_SNPP;

  return (
    <>
      <PageHead kicker="Local impact" title="Bangladesh" lead="The brick-kiln belt around Dhaka: thousands of small, steady fires that VIIRS sees and MODIS mostly cannot, kept apart from crop and vegetation fire." />
      {err && <p className="error">{err}</p>}
      {!region && !err && <div className="skeleton tall" />}
      {region && m && b && (
        <>
          <section>
            <h2>Why Dhaka</h2>
            <p>When VIIRS arrived in {st?.period.slice(0, 4)}, raw detection counts here rose to <b>{times(st?.raw_all_sensors_excess)}</b> what Aqua MODIS alone would imply, while the harmonized record changed by <b>{times(st?.harmonized_excess)}</b>. Kilns are small and burn all season, so the sharper sensor counts many more of them. Kiln Watch puts this heat in its own class so it neither inflates the vegetation-fire record nor gets lost in it.</p>
            <p className="muted small">{m.story}</p>
          </section>

          <section>
            <h2>Kiln season and crop-fire season</h2>
            <LineChart x={[...MONTH_SHORT]} name="dhaka-kilns-seasons" label="Median monthly hotspots by calendar month: kilns and other static heat, and vegetation fire"
              lines={[
                { name: "Kilns, flares and industry (static heat)", color: "#E69F00", vals: byMonth(b.classes.static.hotspots.v), wide: true },
                { name: "Vegetation fire", color: "#56B4E9", vals: byMonth(b.classes.veg.hotspots.v) },
              ]} />
            <p className="muted small">Median of complete months, 2000 to {m.data_through.slice(0, 4)}, hotspots on the Aqua scale. Static heat sources are labelled <i>likely kilns</i>: they are not yet checked against a mapped kiln inventory. Detections are not fires.</p>
          </section>

          <section>
            <h2>What you can do with it</h2>
            <p className="row">
              <button className="btn" onClick={() => openRegion("dhaka-kilns")}>Open the Dhaka calendar</button>
              <button className="btn ghost" onClick={() => go("warning")}>Set an alert</button>
              <button className="btn ghost" onClick={() => go("download")}>Download the CSV</button>
            </p>
          </section>
        </>
      )}
    </>
  );
}

const times = (v: Num | undefined) => (v == null ? "–" : `×${fmt(v, 1)}`);
