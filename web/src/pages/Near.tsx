import { Suspense, lazy, useState } from "react";
import { PageHead, PageProps } from "./shared";

// The place check draws a MapLibre map: lazy, so the map library stays out of the entry chunk.
const PlaceRiskCheck = lazy(() => import("../PlaceRisk"));

/** "Is fire near you?": any place on Earth. A place inside a study area opens its full record in the Explorer. */
export default function Near({ online, openRegion }: PageProps) {
  // deep link #pg=near&q=Ludhiana, India: read at first render, before App rewrites the hash (PlaceRisk loads later)
  const [q0] = useState(() => new URLSearchParams(location.hash.slice(1)).get("q")?.trim() || undefined);
  return (
    <>
      <PageHead kicker="Any place on Earth" title="Is fire near you?"
        lead="Type any town, village, school or address. See if NASA satellites saw fire near it this week, which schools and hospitals are close to that fire, and when fire usually comes." />
      <Suspense fallback={<div className="skeleton tall" />}>
        <PlaceRiskCheck online={online} onArea={openRegion} initialQ={q0} />
      </Suspense>
    </>
  );
}
