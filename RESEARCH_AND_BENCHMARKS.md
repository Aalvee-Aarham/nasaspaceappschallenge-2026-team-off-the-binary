# Kiln Watch — Research Synthesis and Benchmarks

**Research snapshot:** 2026-11-14  
**Challenge:** NASA Space Apps Challenge 2026 — *Harmonization of MODIS and VIIRS Hot Spots*  
**Project:** Kiln Watch, Team Off The Binary  
**Decision audience:** project lead, science reviewers, submission team, and judges

> This is an evidence-first competitive and scientific synthesis, not a claim that every project output has been independently validated.
> Competitor metrics below are labelled as project claims unless the source notes say that they were reproduced.
> Kiln Watch metrics are project outputs unless explicitly identified as an external or peer-reviewed finding.

> **Counts in this document are a snapshot from the audit (2026-11-14):** the MCP server then declared 35 tools while the
> README advertised 31, and the public HTTP connector served all of them. Since the audit, `main` added more tools and
> this branch splits the list — **34 read-only tools over HTTP, all 39 in a trusted local/stdio server** — so the tool
> counts quoted below are historical, not the current state. `FIXES_AND_PLAN.md` carries the current numbers and the
> ledger of what was fixed.

---

## 1. Executive decision summary

### 1.1 Decision

Kiln Watch should enter the submission as a **transparent, deterministic, locally specific fire-record product with a visible evidence trail**, not as another broad dashboard, model zoo, or cinematic globe.

The strongest competitive claim is:

> **One auditable record that survives sensor retirement, shows its uncertainty, and turns NASA fire data into a concrete local decision — brick-kiln seasonality and heat-source exposure in Bangladesh.**

That claim is stronger than Kiln Watch's current public wording because it does not imply that a calibrated estimate is a direct measurement, a fire count, or burned area.

The project already has unusually good foundations: one deterministic calculation layer, a readable non-black-box estimator, satellite-denial and step tests, published intervals, and a memorable human application. It should preserve those foundations rather than imitate competitors' breadth.

The immediate decision is conditional:

1. Obtain written confirmation from the NASA GO Team that the pre-hackathon work and public repository history do not make the submission ineligible.
2. Correct the material scientific defects and claims in the report's P0 list.
3. Demonstrate one local decision workflow and one live, provenance-bearing agent workflow.
4. Do not spend the remaining effort on hardware, a generic chatbot, H3 complexity, or an opaque predictive model.

**[Inference]** Eligibility is a submission blocker; scientific polish cannot compensate for a compliance failure.
**[Inference]** The best award strategy is differentiated depth, not feature parity.

### 1.2 What Kiln Watch already does better

| Capability | Kiln Watch position | Evidence status | Why it is a competitive advantage |
|---|---|---|---|
| Auditable harmonization | Ratio-of-totals calibration by calendar month and day/night, empirical-Bayes shrinkage, inverse-variance combination | **[Verified]** in `server/kw/science.py` | Easier for a judge to inspect than an opaque learned score |
| Continuity test | MODIS-denial rehearsal, Suomi-NPP withholding, step and placebo tests, geographic hold-out | **[Verified]** implementations; **[Project output]** reported metrics | Tests the scientific claim rather than merely displaying it |
| Uncertainty | Split-conformal widening, chain-closure variance, published intervals | **[Verified]** implementation | More transparent than most direct competitors |
| One calculation path | REST, MCP, Gemini analyst, alerts, and charts share the same deterministic tools | **[Verified]** in `server/kw/tools.py` | Prevents the app and AI narrative from telling different numerical stories |
| Local specificity | Dhaka brick kilns are separated from vegetation fire and tied to a seasonal operating problem | **[Verified]** product scope | More memorable than generic “global wildfire” breadth |
| Presentation | Cinematic 3D story, live Earth, satellite timeline, calendar, proof chart, judge navigation | **[Verified]** in `web/src/pages/Home.tsx`; frontend timings are **[Project output]** quoted from `lead_synthesis_notes.md` | Makes sensor continuity understandable to non-specialist judges |
| Global interface | Worldwide 30-day climatological outlook, any-region AOI path, static JSON for hosted presets | **[Verified]** implementation | Demonstrates potential scale without claiming a live global forecast |
| Agent surface | 35 tools, four prompts/personas, five resources, visible tool traces | **[Verified]** by source inspection and MCP initialization | More complete than the common REST-only pattern |

### 1.3 Scientific risks that must be surfaced

| Priority | Risk | Required disclosure or correction |
|---|---|---|
| P0 | The Aqua-scale value is a **calibrated estimate**, not a MODIS observation after 2002 and not a count of fires | Use “estimated Aqua-MODIS-scale hotspots” in headlines, exports, and submission text |
| P0 | The 2000–2002 segment is Terra extrapolated onto the Aqua scale; the held-out Terra→Aqua bias is large in some areas | Label it modelled and attach the measured link uncertainty |
| P0 | The 2023 MODIS exclusion is triggered by a reported acquisition-time/archive shift, not a physical sun-synchronous orbital shift | Rename “orbit drift” to “acquisition-time shift” or “sampling-time change”; add a transition and placebo diagnostic |
| P0 | Near-real-time FIRMS rows have no `type`; untyped recent rows outside the static mask are assigned to vegetation by construction | Publish an `unclassified` share or label recent vegetation as “vegetation + unclassified” |
| P0 | Confidence values are not numerically equivalent across sensors | State that the crosswalk is class-level only and publish the filtering effect |
| P0 | The 95% interval is fitted in a VIIRS-only configuration and achieved 91.7% out-of-sample coverage in the audited result | Do not present every interval as empirically demonstrated 95% coverage |
| P0 | The charted 2023–2026 “now” record depends on a rule that materially changes values and is not step-tested | Add the 2023 transition to the step/placebo report before submission |
| P1 | Global observing days are not regional cloud-free observation opportunity | Say that a zero means “no detection under this observing opportunity,” not “no fire” |
| P1 | “Likely kilns” are not checked against an inventory | Keep “likely” prominent until a kiln inventory or field check is completed |
| P1 | FRP is sensor-specific and not cross-sensor comparable | Keep FRP diagnostic and per sensor; never present a mixed-sensor FRP sum as an estimand |
| P1 | No burned-area or local ground truth has been completed | MCD64A1/Planetary Computer, OSM, and APAD/kiln inventory are recommended validation paths, not results |
| P1 | Map-cell values can diverge materially from area totals | Use one area-level weighting rule for both and publish the reconciliation test |
| P2 | The raw cache is not committed and the upstream mirror is mutable | Publish per-input fingerprints and a rebuild manifest |
| P2 | View-angle and cloud effects remain in the model | Add them to the next method version; do not imply they are already corrected |

### 1.4 Highest-value improvements by award

#### Local Impact

1. Obtain one named Dhaka-area decision-maker and define one recurring decision: kiln-season brief, static-source anomaly, or exposure review.
2. Validate the Dhaka static class against an authoritative kiln inventory or documented field/operator evidence.
3. Ship a Bangla-first local view and a channel that works where email is unreliable.
4. Publish one before/after pilot result, such as response time, acknowledged alerts, or a corrected seasonal decision.

**[Inference]** The current product demonstrates a relevant local use case; it does not yet demonstrate a completed local outcome.
**[Inference]** One documented partner and one decision beat a list of dozens of potential beneficiaries.

#### Galactic Impact

1. Turn the record into maintained public infrastructure: scheduled refresh, stable schemas, versioned releases, and reproducible rebuilds.
2. Publish a compact global scale/audit bundle with no-data behavior, processed-row counts, coverage, and checksums.
3. Keep the post-MODIS continuity endpoint and migration notes visible.
4. Preserve the local pilot as the proof that global scale is useful rather than merely large.

**[Inference]** “Any place on Earth” is an interface promise; a versioned public dataset and reproducible refresh are the path to durable impact.

#### Best Use of Data

1. Add a defensible regional observation-opportunity denominator, using NASA gridded fire products or a documented cloud/opportunity mask.
2. Add one independent validation witness: burned area for physical extent and one local ground/agency source for local truth.
3. Publish the raw, Aqua-scale-estimated, VIIRS-native, and FRP series beside one another with explicit estimands.
4. Publish an audit/data bundle containing factors, intervals, coverage, input fingerprints, and code/config versions.
5. Add view-angle, land-cover, and fire-size stratification only as measured sensitivity analyses.

**[Inference]** More NASA layers will not win this award by themselves; better use of one NASA product with honest validation will.

#### Best Use of Technology

1. Make one MCP workflow the live centerpiece: audit an area, explain an anomaly, and prepare a response brief, with every numeric claim traceable.
2. Ship one command or release that reruns the scientific audit and checks the committed outputs.
3. Make the public MCP route read-only by default; keep write tools for trusted local/stdio use or protect them with authentication.
4. Prove the value of remote GeoParquet querying, including bytes transferred, query latency, and cache behavior.
5. Fix the live reliability issues that can turn a strong demo into a timeout or failed action.

**[Inference]** Tool count is not innovation. The technology award goes to a reliable workflow that changes a decision.

### 1.5 Non-negotiable decision gates

- **Gate A — eligibility:** written GO-team clarification before submission.
- **Gate B — scientific truth:** no “continuous observed record,” “fire count,” or “95% validated interval” language unless the caveat is attached.
- **Gate C — reproducibility:** one rebuild reproduces committed outputs from recorded inputs and code version.
- **Gate D — local proof:** one named partner and one completed or explicitly bounded pilot statement.
- **Gate E — demo reliability:** all judge-path routes complete within the deployment budget and no public write operation is unauthenticated.

---

## 2. Method and evidence labels

### 2.1 Label definitions

- **[Verified]**: directly visible in the inspected source file, official page, repository tree, Git metadata, or live HTTP response during the research snapshot. “Verified” means the artifact or statement was observed; it does not mean the scientific result was independently reproduced.
- **[Source claim]**: a number or capability stated by a project in its README, report, site, or metadata and not independently rerun. Competitor headline metrics use this label unless the notes say otherwise.
- **[Inference]**: a competitive, scientific, or product judgment derived from verified and claimed evidence.
- **[Project output]**: a Kiln Watch result generated by its own code and committed data. It may be reproducible from the project inputs, but it is not independent scientific validation.
- **[NASA fact]**: an equation, constant, product definition, mission status, or warning taken from a NASA primary source.
- **[Peer-reviewed]**: a finding from a peer-reviewed paper; it is external evidence, not a Kiln Watch result.
- **[KW synthesis]**: a reconciliation or recommendation produced from NASA facts, peer-reviewed findings, and project audit evidence.

### 2.2 Research date and methods

All live research was conducted on **2026-11-14**.

External discovery included:

- GitHub code search for `"Harmonization of MODIS and VIIRS" in:file`.
- GitHub code search for `MODIS VIIRS FIRMS "Space Apps" in:file`.
- GitHub repository search for `"NASA Space Apps Challenge 2026"`.
- GitHub repository search for `MODIS VIIRS FIRMS "NASA Space Apps 2026"` and `harmonized burning activity calendar`.
- Web searches for `NASA Space Apps Challenge 2026`, `Harmonization of MODIS and VIIRS`, `MODIS VIIRS FIRMS space apps`, and official 2024/2025 winner announcements.
- Live NASA primary-source retrieval of FIRMS documentation, user guides, algorithm documents, alerts, and peer-reviewed papers.
- Read-only inspection of Kiln Watch source, committed data, APIs, MCP declarations, tests, and deployed behavior documented in the supplied notes.

The exact GitHub snapshot found **192 indexed files across 58 unique repositories** for the exact challenge phrase and **352 files across 112 repositories** for the broader query.
Those counts are discovery snapshots, not a census of registered teams and not evidence of eligibility.

The frontend findings used here are those quoted in `lead_synthesis_notes.md`: navigation took about 1.4 seconds in the audit browser, the audit saw zero console warnings, and API responses were healthy.
Backend latency and failure findings come from `backend_latency.md`, where the stated measurements were reproduced read-only by that audit.

### 2.3 Limitations

1. GitHub code-search counts moved slightly during pagination; the unique-repository count is the more stable comparison.
2. No official 2026 participant-to-repository registry was found. Team names and repository ownership rely on self-identification.
3. Most competitor scale and accuracy claims were not rerun because that would require multi-gigabyte archives, external services, and model pipelines.
4. Live-site checks establish reachability and visible content, not full workflow correctness.
5. The award definitions were taken from the official 2025 awards page because the 2026 definitions were not retrievable at the snapshot.
6. The science notes and audits are read-only analyses of the current implementation; they are not a new independent Kiln Watch experiment.
7. MCD64A1/Planetary Computer burned-area validation, an OSM cross-check, and an APAD/kiln-inventory check are **recommended paths only** unless explicitly described as completed.
8. “375 m VIIRS is not a literal MODIS successor” is a scientific constraint, not a rhetorical downgrade of VIIRS. VIIRS samples smaller fires that MODIS often misses.

---

## 3. Official challenge and rubric fit

### 3.1 Exact challenge need

The official challenge page asks teams to build a **web application with a harmonized burning-activity calendar based on active-fire hotspots**.
The core test is that sensor origin should stop driving apparent trends, anomalies, and patterns.

Official page: <https://www.spaceappschallenge.org/2026/challenges/modis-and-viirs-hot-spots/?tab=details>

| Official need | Kiln Watch fit | Remaining gap |
|---|---|---|
| Harmonized burning-activity calendar | **[Verified]** monthly and weekly records, global outlook, local calendar | State all three estimands together and explain their differences |
| Sensor changes must not create apparent trends/anomalies | **[Verified]** calibration, chain, step/placebo tests, trend outputs | Add a measured diagnostic for the 2023 acquisition-time transition |
| Select a region and date range | **[Verified]** presets and AOI workflow | Hosted any-place builds are disabled; make that status explicit |
| Download analytics and visualizations | **[Verified]** CSV, calibration table, charts and brief | Stream large CSVs and document which files are generated artifacts |
| Cover the early 2000s to present | **[Verified]** record begins 2000-11-01 | 2000–2002 is a modelled Terra extrapolation, not direct Aqua-scale observation |
| Which periods burn most; which years burned most | **[Verified]** calendar, season, and trend outputs | Use “which periods show most detections” unless local ground truth supports “burn” |
| Compare current activity with previous years | **[Verified]** same-period percentile/rank and warning pages | Recent values are strongly affected by NRT classification and the 2023 rule |
| Accessible color ramps | **[Verified]** color-blind-safe calendar in the product notes | Include an automated accessibility check in the final UI pass |
| Downloadable hotspot CSV | **[Verified]** endpoint and tools | The shipped deployment lacks the global aggregate; large local CSVs are memory-heavy |
| Draw AOI or enter latitude/longitude | **[Verified]** AOI and place search | Region-build limits and deployment behavior need clear UI status |
| Support responders, scientists, land managers, firefighters | **[Verified]** audiences and products | Evidence of actual user use is still missing |

### 3.2 Official participant guidance

The official forum makes several scope decisions explicit:

- Either a MODIS-equivalent or VIIRS-equivalent scale is acceptable if justified: <https://github.com/nasa/spaceapps/discussions/1879>.
- FIRMS Standard archive is acceptable and NASA-suggested challenge resources should be used: same discussion.
- Continuing through NOAA-20 and NOAA-21 is encouraged: same discussion.
- Monthly is a solid operating scale; weekly may be useful; daily can be too variable: same discussion.
- A selected country or AOI is sufficient, and a well-implemented regional solution is preferable to weak global coverage: <https://github.com/nasa/spaceapps/discussions/2016>.
- The challenge-specific discussion describes planned spatial/temporal matching and preservation of unmatched records: <https://github.com/nasa/spaceapps/discussions/1786>.

**[Inference]** Kiln Watch's Aqua-scale choice is defensible under the official guidance because the forum permits either scale and the project publishes its loss and its raw/VIIRS-native alternatives.

### 3.3 Past-winner patterns

#### Official 2025 winners

Official announcement: <https://www.nasa.gov/learning-resources/stem-engagement-at-nasa/nasa-announces-2025-international-space-apps-challenge-global-winners>

| Award | Winner | Pattern that Kiln Watch should learn |
|---|---|---|
| Local Impact | QUEÑARIS, Peru — <https://www.spaceappschallenge.org/2025/find-a-team/watana-project/?tab=project> | One city, one ecosystem, one causal chain, and a concrete intervention |
| Galactic Impact | Astro Sweepers — <https://www.spaceappschallenge.org/2025/find-a-team/astro-sweepers-we-catch-what-space-leaves-behind/?tab=project> | An end-to-end compliance/risk infrastructure layer with scale and policy relevance |
| Best Use of Data | Resonant Exoplanets — <https://www.spaceappschallenge.org/2025/find-a-team/resonant-exoplanets/?tab=project> | A complete telescope/satellite pipeline with physics and false-positive validation |
| Best Use of Technology | Twisters / SkySense — <https://www.spaceappschallenge.org/2025/find-a-team/twisters/?tab=project> | Multi-source NASA/weather data transformed into a practical decision assistant and alerts |

The 2025 field was reported as more than 11,500 submissions, 551 local events, and 167 countries or territories.
The common pattern was depth, reproducibility, and a short evidence-to-decision path.

#### Official 2024 winners

Official announcement: <https://www.nasa.gov/learning-resources/stem-engagement-at-nasa/nasa-international-space-apps-challenge-announces-2024-global-winners>

| Award | Winner | Pattern that Kiln Watch should learn |
|---|---|---|
| Local Impact | Team I.O. / G.R.O.W. — <https://www.spaceappschallenge.org/nasa-space-apps-2024/find-a-team/team-io/?tab=project> | Hide complex GIS behind an accessible interface and name a human problem |
| Galactic Impact | NVS-knot / 2plant — <https://www.spaceappschallenge.org/nasa-space-apps-2024/find-a-team/nvs-knot/?tab=project> | Publish trust metrics and a credible path from research to product |
| Best Use of Data | GaamaRamma / Waterwise — <https://www.spaceappschallenge.org/nasa-space-apps-2024/find-a-team/gaamaramma/?tab=project> | Turn one expert NASA variable into one recurring decision |
| Best Use of Technology | 42 QuakeHeroes — <https://www.spaceappschallenge.org/nasa-space-apps-2024/find-a-team/42-quakeheroes/?tab=project> | Use advanced technology because it solves a hard method problem, and evaluate it honestly |

The 2024 field was reported as 9,996 submissions, 485 events, and 163 countries or territories.
**[Inference]** Kiln Watch has the technology and science substrate; the missing pieces are an externally witnessed local outcome and a judge-proof demonstration of consequence.

### 3.4 Award-specific implications

| Award | Judge question | Kiln Watch's best proof | Main reason it could lose |
|---|---|---|---|
| Local Impact | Who will act differently because this exists? | One named kiln manager/regulator/NGO receiving a monthly decision brief, plus inventory evidence | The project currently demonstrates relevance, not a completed outcome |
| Galactic Impact | Could this become maintained global infrastructure? | Versioned global record, post-MODIS continuity, public schema, and reproducible refresh | Current global claims and artifacts are narrower than the strongest rivals |
| Best Use of Data | Did NASA data enable a unique, valid answer? | One scientifically defined record with uncertainty, raw alternatives, and independent witness | No regional cloud denominator or independent burned-area/ground validation yet |
| Best Use of Technology | Did technology make a hard task reliable and useful? | One traceable MCP decision workflow over a deterministic scientific core | Public write tools, latency, and broken deployment-dependent routes weaken trust |

Official award definitions: <https://www.spaceappschallenge.org/2025/awards/>

- **Local Impact:** “The project that demonstrates the greatest potential for local impact.”
- **Galactic Impact:** “The project with the most potential to improve life on Earth or in the universe.”
- **Best Use of Data:** “The project that best makes space data accessible or leverages it for a unique application.”
- **Best Use of Technology:** “The project that exemplifies the most innovative use of technology.”

---

## 4. Competitor landscape

### 4.1 Concise comparison

| Project | URL | Architecture / data / UI verified in repository | Standout | Important limitation | Threat |
|---|---|---|---|---|---|
| SHIFT | <https://github.com/squadronzero/project-shift> | Staged Python pipeline; static React/MapLibre; published site data; validation artifacts | Precommitted rules, audit labels, placebo/no-data handling, published errata | Multi-GB raw pipeline was not rerun by the audit | **Very high:** Data, Galactic |
| Flare-Chronos | <https://github.com/the-aris-club/flare-chronos> | Python `uv` monorepo; FIRMS adapter; FastAPI/LangGraph; Next.js/Three.js/H3 | Scan-angle footprint model, grounded AI harness, numeric verifier | Breadth exceeds measured validation; hold-out showed no significant FRP-RMSE gain | **Very high:** Technology; medium-high Data |
| Fire Harmony | <https://github.com/Warren-530/fire-harmony> | DuckDB/Parquet, H3, LightGBM, climate drivers, browser-side querying, Hugging Face release | Broadest global data product and public harmonized dataset | README and live dataset size differ; metrics were not rerun | **Highest:** Data, Galactic; high Technology |
| FireLens (`abubokkor-cse`) | <https://github.com/abubokkor-cse/firelens> | DuckDB tiles, FastAPI, React/MapLibre, Cloud Run, HistGradientBoosting, chronological split | Direct Bangladesh competitor with out-of-time model comparison | Six commits and 68 files cannot substantiate all global scale claims | **High:** Data, Technology, Local |
| Dahan / Phoenix007 | <https://github.com/Saobia3i/Phoenix007> | Browser-side H3/DuckDB-era ratios, compressed static files, bilingual React UI | Excellent low-cost static architecture and browser-reproducible statistics | Public data depends on separate release infrastructure | **High:** Local, Technology; medium-high Data |
| Parallax Fire | <https://github.com/Shahriar290900/Harmonisation-MODIS-VIIRS> | Three.js/GSAP/MapLibre, CelesTrak orbits, GIBS, three regional calendars | Real sun/satellite presentation and strong Bangladesh identity | Validation is less transparent than SHIFT or Kiln Watch | **High:** Local/storytelling; medium science |
| BD-FireOps | <https://github.com/shahriyarcse-arch/BD_FireOps---Nasa-Space-Apps-Challange> | Python, FIRMS chunks, geoBoundaries, Streamlit, Leaflet, audit, held-out slope model | Candid local comparison and real 98-point audit | CHT focus; NOAA-20 leg explicitly not fitted | **High:** Local, Data |
| Agun Panjika | <https://github.com/polymathicX/Agun-Panjika> | Negative-binomial + LightGBM, NASA POWER/FWI, Three.js, English/Bangla, CHT calendars | Honest leakage, refresh-failure, pilot, and uncertainty disclosure | No verified public deployment and archives are partial | **High if deployed:** Local, Data |
| Icarus | <https://github.com/mdhabibullahmahmudncs13/Icarus-Harmonization-of-MODIS-and-VIIRS-Hot-Spots> | FastAPI/React/DuckDB, YAML config, offline fixture, observed-data validation | Honest supported/partial verdicts and provenance hashes | Only partial verdicts; burned-area R² is low; no static mask applied | **Medium:** credibility benchmark |
| SparkGrid | <https://github.com/freefirenoobs/sparkgrid> | FastAPI/React HUD, DBSCAN, confidence fusion, wind enrichment, Open WebUI | Fast operational-console impression and AI hub | Created immediately before event; one-day regional benchmark; hand-coded flare basin | **Medium:** Technology/story; low-medium Data |
| Ignis-Atlassia / FireAtlas | <https://github.com/AhnafZ778/Ignis-Atlassia> | Evidence bundles, recount verifier, research boards, story/video/Remotion, assistant hooks | Broadest evidence-to-story-to-video workflow | Partial regional archives and simple count-ratio calibration | **High:** Technology/story; low-medium science |
| Zakarpattia Orbit | <https://github.com/Kolok2008/zakarpattia-orbit> | FIRMS calendar, ESP32-CAM ground station, MAVLink/SITL, OSRM routes | Concrete sensor-to-firefighter action loop | Narrow scope; firmware/SITL not physically tested; early ratio method | **Low direct; high concept:** Local/hardware |
| FireChronicle | <https://github.com/inan001/firechronicle> | Next.js, 50 km EASE-Grid blocks, negative-binomial GLM, temporal/geographic hold-outs, 37 tests | Small-region model with strict missingness semantics and tests | One Pará region, 2002–2020; different repository with same name is preparation-only | **Low-medium:** Data method |
| Four-Bits | <https://github.com/OmarHedaya/Four-Bits-and-a-Byte> | Vite/React/MapLibre shell, heatmap, anomaly panel, Zod, Vitest | Polished interface and typed contracts | Default app uses deterministic mock sample data; real exports not supplied | **Low currently:** UI only |
| Triton | <https://github.com/pulik181/triton-wildfire> | Streamlit, FIRMS NRT, clustering, FRP threshold, CSV/GeoJSON | Simple Kazakhstan operational interface | One-file app; hard-coded coefficients; 3 MW cut removes small-fire signal | **Low:** narrow prototype |
| Kelvin | <https://github.com/RomanMayor/Kelvin> | .NET MVC/Leaflet, quota-aware two-level cache, tile/chunk archive | Sensible cache and quota architecture | README says the harmonized layer is still to be implemented | **Very low direct:** engineering precursor |

### 4.2 Detailed profiles

#### SHIFT

- **URLs:** <https://github.com/squadronzero/project-shift> · live <https://squadronzero.github.io/project-shift/> · audit <https://github.com/squadronzero/project-shift/blob/main/docs/audit/VALIDATION_REPORT.md>
- **Architecture:** **[Verified]** staged Python pipeline for fetch, quality control, ingestion, aggregation, counts, continuity, source selection, FRP, worldwide factors, confidence, no-data handling, harmonization, checks, and export; static React/MapLibre site; committed configuration; published `site-data` release.
- **Data/UI:** **[Verified]** static calendar/site presentation, no-data and placebo concepts, and reproducible artifacts are committed.
- **Scientific claims:** **[Source claim]** raw global 2012 step of 2.64× becomes 0.97×; backward errors of 17.6% for hotspots and 21.9% for FRP; ten test regions and GFED4 comparison.
- **Standout:** **[Verified]** report labels pipeline results, audit measurements, and tests separately; it publishes two errata, including a coverage-independence correction and a monthly-error wording correction.
- **Limitation:** the audit notes that the raw multi-gigabyte pipeline was not rerun; its claim breadth is not independently reproduced here.
- **Threat:** **[Inference]** very high for Best Use of Data and Galactic Impact because it competes directly on scientific auditability and public artifacts.

#### Flare-Chronos

- **URLs:** <https://github.com/the-aris-club/flare-chronos> · live <https://flare-chronos.resonance.io.vn/>
- **Architecture:** **[Verified]** Python `uv` monorepo, pure harmonization core, FIRMS adapter, benchmark CLI, FastAPI LangGraph service, Next.js 16/Three.js/d3-geo/H3 workbench, CI/CD, and releases.
- **Data/UI:** **[Source claim]** scan-angle footprint reconstruction, fractional H3 allocation, solar-zenith day/night, a unified probability, 60-minute episodes, effort normalization, and a 26-by-73-pentad calendar.
- **Standout:** **[Verified]** the AI harness includes tool selection, a grounded facts ledger, numeric verification, event streaming, and human sign-off.
- **Limitation:** **[Verified]** the specification reports that a 2020 hold-out found no statistically significant FRP RMSE reduction; breadth is greater than measured evidence.
- **Threat:** **[Inference]** very high for Best Use of Technology and medium-high for Data, but more complex to trust than Kiln Watch's plain estimator.

#### Fire Harmony

- **URLs:** <https://github.com/Warren-530/fire-harmony> · live <https://warren-530.github.io/fire-harmony/> · dataset <https://huggingface.co/datasets/warrensaw530/fire-harmony>
- **Architecture:** **[Verified]** Python/DuckDB/Parquet pipeline, H3 levels 3–8, LightGBM Poisson model, area intervals, climate and weather drivers, outlook with Brier skill, haze layer, React/Vite/TypeScript, DuckDB-WASM, MapLibre/deck.gl, Observable Plot, and Quarto/Typst outputs.
- **Data/UI:** **[Source claim]** 640,601,590 FIRMS rows from 2000–2026; a VIIRS-to-MODIS model with physical and regional features; 90% ranges; static-source mask; opportunity masks.
- **Standout:** **[Verified]** the physics code compares VIIRS points against Aqua/Terra daily fire-mask layers and distinguishes clear, cloud, and no-data conditions; a public dataset exists.
- **Limitation:** **[Verified]** the README stated 1.08 GB while the live dataset card showed 7.94 GB at fetch time; model metrics were not rerun.
- **Threat:** **[Inference]** highest for Best Use of Data and Galactic Impact; high for Technology through browser-side remote querying.

#### FireLens by `abubokkor-cse`

- **URLs:** <https://github.com/abubokkor-cse/firelens> · live <https://firelens.tech>
- **Architecture:** **[Verified]** Python/DuckDB Parquet tiles, React/Vite/MapLibre, FastAPI, Cloud Run/Cloudflare R2/Pages, scheduled daily/weekly/monthly jobs, and fixed 52-week cells.
- **Data/UI:** **[Source claim]** 486 million detections, 647 monthly source files, a HistGradientBoosting Poisson harmonizer, train 2012–2021 and test 2022–2026 in 211 countries, alerts, live fires, and exports.
- **Standout:** **[Verified]** the training script confirms model type, features, chronological split, baseline comparisons, and a saved report.
- **Limitation:** **[Verified]** the repository had six commits and 68 files at the snapshot; that is not enough to establish the full processing scale claimed in the README.
- **Threat:** **[Inference]** high for Data and Technology and a credible Local Impact rival because it is Bangladesh-based and already frames alerts and current fire as products.

#### Dahan / Phoenix007

- **URLs:** <https://github.com/Saobia3i/Phoenix007> · live <https://dahan-3j4.pages.dev>
- **Architecture:** **[Verified]** Python/DuckDB/H3 build, React 19/Vite/TypeScript/ECharts/MapLibre/terra-draw, compressed gzip `.dhn`/`.dha` files, Cloudflare Pages/Functions/KV, Gemini with a server-side numeric allowlist, and Telegram alerts.
- **Data/UI:** **[Source claim]** 10 GB source and about 8,092 static files, H3 resolution-5 fire cell-days, local-solar dates, monthly/day/night shrinkage, overlap chains, bootstrap intervals, and a Pettitt seam test.
- **Standout:** **[Verified]** browser-side overlap ratios, bootstrap, and seam test are visible in source; the bilingual scope and static-first delivery are unusually practical.
- **Limitation:** public data is distributed outside Git, so reproducibility depends on the release infrastructure.
- **Threat:** **[Inference]** high for Local Impact and Technology; a good UX and low-cost architecture benchmark for Kiln Watch.

#### Parallax Fire

- **URLs:** <https://github.com/Shahriar290900/Harmonisation-MODIS-VIIRS> · live <https://parallaxfire.netlify.app> · manual <https://parallaxfire.netlify.app/Parallax-Fire-Manual.pdf>
- **Architecture:** **[Verified]** React/Vite/TypeScript, Three.js/GSAP/MapLibre/satellite.js, Netlify functions, Kaggle notebooks, CelesTrak orbit data, and NASA FIRMS/GIBS/Blue Marble.
- **Data/UI:** **[Source claim]** monthly calendars for Bangladesh, California, and New South Wales from 2001–2025, raw-versus-harmonized switching, and a held-back 2023–2024 check.
- **Standout:** real satellite positions, real sun position, NASA imagery, polished dark/light UI, and a manual make the product easy to understand.
- **Limitation:** validation details are less transparent than SHIFT or Kiln Watch, and the repository's generated assets are large.
- **Threat:** **[Inference]** high for Local Impact and presentation; medium for scientific depth.

#### BD-FireOps

- **URLs:** <https://github.com/shahriyarcse-arch/BD_FireOps---Nasa-Space-Apps-Challange> · live <https://bdfireops.vercel.app>
- **Architecture:** **[Verified]** Python analysis pipeline, FIRMS Area API chunks, geoBoundaries district gate, Streamlit plus standalone Leaflet/Chart.js, six-hour GitHub Actions synchronization, synthetic pipeline tests, and a 98-point audit.
- **Data/UI:** **[Source claim]** CHT monthly record from 2002–2021, chronological train/test split, OLS slope model, live NOAA-20/21, and bootstrap coefficient intervals.
- **Standout:** the project states that its fitted model gains only 1.7% RMSE over a scalar baseline and labels the NOAA-20 leg “not fitted.”
- **Limitation:** regional CHT scope and the unfitted NOAA-20 leg leave room for Kiln Watch's longer chain, subject to Kiln Watch's own transition risk.
- **Threat:** **[Inference]** high for Local Impact and Data; its candor is a credibility benchmark.

#### Agun Panjika

- **URL:** <https://github.com/polymathicX/Agun-Panjika>
- **Architecture:** **[Verified]** Python pipeline, negative-binomial plus bagged LightGBM ensemble, NASA POWER/FWI, Open-Meteo, geoBoundaries, static JSON/CSV, React/TypeScript, Three.js, sonification, and CHT calendars for 25 upazilas and 124 unions.
- **Data/UI:** **[Source claim]** weekly VIIRS-scale history from 2001, ensemble weights, national MAE, nominal interval coverage, NOAA bridge errors, and tests.
- **Standout:** the method page explicitly discusses leakage, hosted-refresh failure, absence of a field pilot, and non-nested uncertainty.
- **Limitation:** no verified public deployment; activity stopped before the main event.
- **Threat:** **[Inference]** high for Local Impact and Data if deployed; currently medium because the public product is incomplete.

#### Icarus

- **URL:** <https://github.com/mdhabibullahmahmudncs13/Icarus-Harmonization-of-MODIS-and-VIIRS-Hot-Spots>
- **Architecture:** **[Verified]** Python 3.11, FastAPI, DuckDB/Parquet, Pydantic, pytest/Ruff, React 18/TypeScript/Vite/D3/Three.js, YAML parameters, offline fixtures, and provenance hashes.
- **Data/UI:** **[Source claim]** 0.05° presence-based cell-days, 1° tile/month VIIRS-to-MODIS ratios, coverage/climatology, synthetic mechanism tests, and observed E1–E9 checks.
- **Standout:** the validation file reports partial verdicts and a raw step of 3.031 becoming 2.122 after simple calibration, rather than hiding an inadequate result.
- **Limitation:** no homepage; burned-area R² is only 0.3424; the diagnostic static mask is not applied.
- **Threat:** **[Inference]** medium direct, but high as a credibility baseline: a simple method can remain materially biased after calibration.

#### SparkGrid

- **URLs:** <https://github.com/freefirenoobs/sparkgrid> · live <https://sparkgrid.masarat.app> · API <https://sparkgrid-api.masarat.app/docs> · AI hub <https://sparkgrid-ai.masarat.app>
- **Architecture:** **[Verified]** FastAPI, React 18/Vite/Leaflet dark HUD, Haversine DBSCAN at 1.5 km, 120-minute temporal fusion, FRP centroids, Bayesian confidence fusion, industrial-flare mask, Open-Meteo wind enrichment, and Open WebUI.
- **Data/UI:** **[Source claim]** one Northern/Central Africa 24-hour example compresses 26,137 raw detections to 11,660 clusters and identifies 72 dual-sensor fires.
- **Standout:** the fastest operational-console impression and a separate AI Coding Hub.
- **Limitation:** the repository was created immediately before the event; the benchmark is one day and one region; the flare basin is hand-coded; clustering is not a 26-year harmonized calendar.
- **Threat:** **[Inference]** medium for Technology and storytelling, low-medium for Data.

#### Ignis-Atlassia / FireAtlas

- **URLs:** <https://github.com/AhnafZ778/Ignis-Atlassia> · live <https://AhnafZ778.github.io/Ignis-Atlassia/>
- **Architecture:** **[Verified]** Python/SQLite/uv, static React-like workspaces, hash-bound evidence ZIPs and recount verifier, research boards, React Flow workflow composer, tldraw export, Liveblocks rooms, story/video rendering, Remotion, and assistant/MCP hooks.
- **Data/UI:** **[Source claim]** roughly two million VIIRS-equivalent cell-day records in two regions, 48 complete MODIS source-months per region, and seven 2024 evidence bundles.
- **Standout:** the most ambitious evidence-to-story-to-video/whiteboard system in the observed field.
- **Limitation:** archives are partial and the harmonization is explicitly a count-ratio method rather than a calibrated sensor-sensitivity model.
- **Threat:** **[Inference]** high for Technology and presentation; low-medium for raw harmonization science.

#### Zakarpattia Orbit

- **URL:** <https://github.com/Kolok2008/zakarpattia-orbit>
- **Architecture:** **[Verified]** Python ground station, FIRMS, 13 local drone bases, ESP32-CAM firmware with CO/temperature/GPS/thermal sensors, ArduPilot/MAVLink SITL, OSRM road routing, bilingual Ukrainian/English UI, and a mission log.
- **Data/UI:** **[Source claim]** a 2001–2026 local calendar, a 3.4× VIIRS/MODIS ratio, and a 10% annual error after harmonization.
- **Standout:** a concrete sensor-to-authority-to-firefighter loop makes local response visible.
- **Limitation:** the README says firmware and SITL flight were not tested and the image classifier is rule/colour based; the early method is simple.
- **Threat:** **[Inference]** low direct threat to the calendar, but a high conceptual Local Impact benchmark. Copying the hardware would not close Kiln Watch's evidence gap.

#### FireChronicle

- **URLs:** <https://github.com/inan001/firechronicle> · related preparation repository <https://github.com/bhavishyaone1/FireChronicle>
- **Architecture:** **[Verified]** for `inan001/firechronicle`: Next.js 16, 50 km EASE-Grid blocks, negative-binomial GLM, temporal and geographic hold-outs, strict null/missingness semantics, 37 tests, and static data.
- **Data/UI:** **[Source claim]** one Pará region and 2002–2020, predicting VIIRS-equivalent counts conditional on MODIS with explicit extrapolation discussion.
- **Standout:** small, testable scope with explicit extrapolation semantics.
- **Limitation:** one region and a short record; the repository with a similar name that says `PRE_HACKATHON_PREPARATION` is documentation, not a finished competitor.
- **Threat:** **[Inference]** low-medium direct threat, but useful evidence that a local model can be honest and rigorous.

#### Four-Bits

- **URL:** <https://github.com/OmarHedaya/Four-Bits-and-a-Byte>
- **Architecture:** **[Verified]** Vite/React/MapLibre shell, calendar heatmap, sensor-comparison chart, anomaly panel, audience modes, Zod contracts, and Vitest.
- **Data/UI:** **[Verified]** the default `public/sample-data` path is deterministic mock data.
- **Standout:** polished interface structure and typed contracts.
- **Limitation:** the README says real backend exports are still to be supplied; this must not be counted as a completed data competitor.
- **Threat:** **[Inference]** low current threat; a UI reference only.

#### Triton

- **URL:** <https://github.com/pulik181/triton-wildfire>
- **Architecture:** **[Verified]** Streamlit, FIRMS NRT, Haversine clustering at 1.11 km, Kazakhstan AOIs, and CSV/GeoJSON export.
- **Data/UI:** **[Source claim]** a power-law FRP calibration and a 3 MW detection threshold.
- **Standout:** a small operational interface with accessible output formats.
- **Limitation:** coefficients and threshold are hard-coded; the threshold removes small-fire signal central to the challenge; the application is essentially one file.
- **Threat:** **[Inference]** low direct threat and a warning against thresholding away the phenomenon.

#### Kelvin

- **URL:** <https://github.com/RomanMayor/Kelvin>
- **Architecture:** **[Verified]** .NET 10 MVC, Leaflet, FIRMS quota-aware two-level cache, 30° tiles, one-day chunks, country/bounding-box statistics, sensor ratios, and Azure deployment.
- **Data/UI:** **[Verified]** the engineering and query path are substantial.
- **Standout:** sensible handling of FIRMS quota, caching, and chunked retrieval.
- **Limitation:** the README explicitly says the harmonized layer is still something the team can add.
- **Threat:** **[Inference]** very low direct scientific threat; a useful retrieval-architecture reference.

### 4.3 Integrity notes on the wider field

- Do not count renamed copies as independent competitors; GeoHarmonix appears to duplicate Flare-Chronos.
- Several repositories share the FireLens and FireChronicle names; ownership and implementation evidence must accompany each comparison.
- A live site does not prove a complete 26-year pipeline; FireSync and the preparation-only FireChronicle make that distinction explicit.
- README metrics, repository size, and HTTP 200 are evidence of what is claimed and reachable, not reproduction of the underlying scientific result.

---

## 5. Gap analysis

### 5.1 Kiln Watch versus the field

| Dimension | Kiln Watch | Strongest field capability | Priority gap | Decision |
|---|---|---|---|---|
| Harmonization transparency | Readable ratio estimator and validation | SHIFT publishes a formal audit and errata | Add equally explicit claim provenance and one-command audit | Now |
| Observation opportunity | Global satellite observing days | Fire Harmony uses daily fire masks; SHIFT/Flare normalize effort | Regional cloud/opportunity denominator is missing | Next |
| Independent truth | Internal sensor tests only | SHIFT GFED4; Fire Harmony external datasets; Icarus partial burned-area check | Add burned-area and local/ground witnesses | Next |
| Static classification | Dynamic `type`-based 0.01° proxy, whole-record | Fire Harmony has richer static evaluation; FIRMS has an official precedent | Cross-check inventory and make NRT uncertainty explicit | Now/next |
| Global scale evidence | Nine committed regions; global code path and outlook | Fire Harmony, SHIFT, and FireLens publish much larger scale artifacts | Publish verified global coverage and a versioned release | Next/later |
| Public data reuse | Downloads for app outputs | SHIFT site-data, Fire Harmony dataset, Dahan static release | Publish harmonized values, factors, coverage, intervals, fingerprints | Next |
| Local outcome | Relevant kiln use case, no named completed pilot | QUEÑARIS, G.R.O.W., and 2plant name human decisions | One named partner and one completed/bounded pilot | Next |
| Local language | Reviewed primary UI is English | Dahan, Agun Panjika, and Parallax emphasize Bangla | Bangla-first local layer and explanation | Next |
| Agent technology | 35-tool deterministic MCP plus analyst | Flare has grounded/human-approved AI; Ignis has broad studio tools | One reliable judge-proof agent scenario | Now/next |
| Runtime and operations | Fast committed JSON path; live paths have latency/security gaps | Cloud competitors use scheduled jobs and static/browser data | Fix high-risk endpoints and deployment-dependent failures | Now |
| Presentation | Strong cinematic story and live Earth | Parallax/Flare/Ignis are also visually strong | Bind the 3D story to a current, area-specific evidence state | Next |

### 5.2 Explicit priority order

#### P0 — before submission freeze

1. Written GO-team eligibility clarification.
2. Canonical repository and 31-versus-35 tool-count cleanup.
3. Acquisition-time-shift terminology and transition/placebo diagnostic.
4. NRT unclassified share and corrected recent-class labels.
5. Nested-validation rule for estimator selection; no selection on the outer hold-out.
6. First incomplete ISO-week correction or explicit partial flag.
7. Chain-composition and interval-coverage caveats in method output.
8. Map-to-area reconciliation test and correction.
9. Public MCP write protection, AOI build caps, alert validation, and core read-path latency fixes.
10. Submission and README wording that calls the Aqua-scale output an estimate.

#### P1 — highest award value

1. Regional observation-opportunity denominator.
2. Independent burned-area and local/agency validation witnesses.
3. Sensor-independent, time-invariant static-site list with asset cross-checks.
4. One named Dhaka decision workflow and pilot evidence.
5. One live MCP decision workflow with visible provenance.
6. Bangla-first local UX and low-friction alert channel.
7. Versioned audit/data release with checksums and input fingerprints.

#### P2 — after correctness and compliance

1. View-angle-stratified count diagnostics and FRP sensitivity.
2. Better worldwide outlook refresh architecture and explicit snapshot age.
3. Low-bandwidth/offline packaging.
4. Public API schema/versioning policy.

#### P3 — only if core work is complete

1. One decision extension such as agricultural residue planning or smoke/health exposure.
2. A formal event layer using the peer-reviewed FEDS five-day association rule.
3. Additional local-language deployments beyond the first pilot.

### 5.3 What not to copy

- **Do not copy H3 or ML breadth.** It adds operational complexity without closing Kiln Watch's observation, validation, or local-proof gaps.
- **Do not copy a generic chatbot.** Dahan's numeric allowlist and Flare's verifier are better models than free-form narration; Kiln Watch already has deterministic tools.
- **Do not copy hardware for spectacle.** A drone or ground station does not prove the record is right or useful.
- **Do not copy hand-coded flare basins.** Static classification must be reproducible and asset-cross-checked.
- **Do not copy sample-data defaults without a real backend.** Four-Bits' polished shell is not a data competitor.
- **Do not copy high-threshold detection filters.** Triton's 3 MW cut removes the small-fire phenomenon the challenge is about.
- **Do not copy unverified row-count claims.** Fire Harmony's and FireLens's scale claims are useful as targets, not as reproduced facts.
- **Do not turn detections into fires, perimeters, emissions, or impact.** FIRMS explicitly warns against using active-fire locations to estimate burned area.
- **Do not choose an estimator on its hold-out test set.** That leaks the test and makes the reported skill optimistic.

---

## 6. Scientific backbone

### 6.1 Source hierarchy and estimand

The source hierarchy used in this report is:

1. **NASA primary facts:** equations, constants, product definitions, mission status, and product caveats.
2. **Peer-reviewed findings:** cross-sensor detection, FRP, viewing-angle, cloud, and continuity evidence.
3. **Kiln Watch synthesis:** how those facts should be implemented and worded in this project.
4. **Kiln Watch project outputs:** numbers generated by this repository; these require independent witnesses for scientific validation.

The primary Kiln Watch estimand is an **estimated number of vegetation-fire detections on the Aqua MODIS scale**, day and night separately.
It is not a direct Aqua observation after the calibration period, not a number of distinct fire objects, not burned area, and not a physical emission inventory.

**[NASA fact]** FIRMS says each detection is the center of a flagged pixel containing one or more fires or other thermal anomalies and that active-fire locations are not recommended for burned-area estimation.
**[KW synthesis]** Keep the Aqua-scale estimate, but always show the VIIRS-native and raw series beside it.

### 6.2 MODIS Collection 6 detection backbone

**[NASA fact]** Giglio et al. (2016) define the Collection 6 algorithm as potential-pixel selection, background characterization, tentative detection, rejection tests, confidence assignment, and FRP retrieval.

#### Potential-fire thresholds

```text
T4* = mean(T4)large-window + 5 K, constrained to 300 K <= T4* <= 330 K
dT* = mean(dT)large-window + 5 K, constrained to 10 K <= dT* <= 35 K
```

- The large window is approximately 306 km × 30 km at nadir and grows to about 740 km × 33 km at the scan edge.
- Pixels with `T4 > 360 K` (`320 K` at night) are excluded from the background average.
- Averages based on fewer than 2,000 valid pixels fall back to conservative Collection 5 thresholds.

#### Absolute and contextual detection tests

```text
(1) T4 > 360 K                         (320 K at night)

(2) dT > dTbar + 3.5 * delta_dT
(3) dT > dTbar + 6 K
(4) T4 > T4bar + 3 * delta_4
(5) T11 > T11bar + delta_11 - 4 K
(6) delta'_4 > 5 K
```

Decision rule:

```text
Day:   (1) OR [ (2) AND (3) AND (4) AND ((5) OR (6)) ]
Night: (1) OR [ (2) AND (3) AND (4) ]
```

`T4` is 4-µm brightness temperature, `T11` is 11-µm brightness temperature, `dT = T4 - T11`, and `delta` is the mean absolute deviation of the background window.

#### Important rejection and cloud rules

```text
MODIS cloud test:
(rho_0.65 + rho_0.86) / 1.2
OR T12 < 265 K
OR ((rho_0.65 + rho_0.86) / 0.7 AND T12 < 285 K)
OR (water pixel AND rho_0.86 / 0.25 AND T12 < 300 K)

MODIS forest-clearing rejection:
T11 > T11bar + 3.7 * delta_11
AND rho_0.86 < 0.28
AND T4 < 325 K
```

**[NASA fact]** The cloud test is adequate for larger, cooler clouds but misses many small clouds and cloud edges.
**[KW synthesis]** These limitations remain relevant to Kiln Watch because a no-detection result is not evidence of no fire.

### 6.3 VIIRS 375 m detection backbone

**[NASA fact]** The VIIRS 375 m product is not the MODIS-continuity product. The 750 m VIIRS product is the NASA product designed for continuity with MODIS 1 km; the 375 m product samples different, smaller footprints and finds many small fires MODIS misses.

#### Candidate pixels

```text
BT4M = MAX[325, M + 25] K
BT4S = MIN[330, BT4M] K

Day candidate:
BT4 > BT4S AND dBT45 > 25 K

Night candidate:
BT4 > 295 K AND dBT45 > 10 K
```

`M` is the median `BT4` over a 501×501 sampling window; at least 10 valid observations are required, otherwise `BT4S = 330 K`.

#### Contextual tests

```text
Day:
dBT45 > dBT45B + 2 * delta_45B
AND dBT45 > dBT45B + 10 K
AND BT4 > BT4B + 3.5 * delta_4B
AND (BT5 > BT5B + delta_5B - 4 K OR delta'_4B > 5 K)

Night:
dBT45 > dBT45B + 3 * delta_45B
AND dBT45 > dBT45B + 9 K
AND BT4 > BT4B + 3 * delta_4B
```

The background window grows from 11×11 to 31×31 until at least 25% or at least 10 valid same-class pixels are available.
Cloud, background-fire, and non-nominal-quality pixels are excluded from that background.

#### Secondary tests

```text
Saturation-like:
BT5 >= 325 K OR BT4 = 355 K OR dBT45 < 0 K
-> downgrade to low confidence when a nominal/high neighbour exists

Glint:
dBT45 <= 30 K OR glint_angle < 15 degrees
-> downgrade to low confidence under the adjacent-pixel rule

Glint angle:
cos(glint_angle) = cos(view) * cos(sun)
                    - sin(view) * sin(sun) * cos(azimuth_difference)
```

**[NASA fact]** VIIRS day/night thresholds are not rescalable from MODIS by one factor; the night `dBT45` offset is +9 K rather than +6 K, and the day branch has a different fourth condition.

### 6.4 Confidence equations and crosswalk

#### MODIS confidence

```text
S(x; alpha, beta) = 0                              if x <= alpha
                  = (x - alpha) / (beta - alpha)   if alpha < x < beta
                  = 1                              if x >= beta

z4    = (T4 - T4bar) / delta_4
z_dT  = (dT - dTbar) / delta_dT

C1 = S(T4; T4bar, 360 K)
C2 = S(z4; 3.0, 6)
C3 = S(z_dT; 3.5, 6)
C4 = 1 - S(N_ac; 0, 4)
C5 = 1 - S(N_aw; 0, 4)

C = (product of included C_i) ^ (1/n)
n = 5 for daytime land
n = 3 for nighttime
n = 4 for daytime water
```

At night, `C1` uses 320 K and `C4`/`C5` are omitted; for daytime water, `C5` is omitted.

MODIS confidence classes:

```text
0%  <= C < 30%   low
30% <= C < 80%   nominal
80% <= C <= 100% high
```

#### VIIRS confidence and the only defensible crosswalk

VIIRS confidence is a class label: `l`, `n`, or `h`.

| MODIS class | FIRMS numeric field | VIIRS class | FIRMS label field |
|---|---|---|---|
| low | 0–29 | low | `l` |
| nominal | 30–79 | nominal | `n` |
| high | 80–100 | high | `h` |

- **[NASA fact]** FIRMS states there is no optimal confidence cutoff a priori and that confidence meaning differs between sensors.
- **[KW synthesis]** Crosswalk only at class level. Never map VIIRS `n` to “50%” or apply a numeric threshold to VIIRS.
- **[Project output]** The local audit found the current SQL correctly selects MODIS `>=30%` and VIIRS non-low classes, but the filters differ in strictness: roughly 3–5% of MODIS and 13–26% of daytime VIIRS rows are removed.

### 6.5 FRP equations and constants

#### MODIS Collection 6

```text
FRP ~= (A_pix * sigma) / (a * tau4) * (L4 - L4bar)

sigma = 5.6704e-8 W m^-2 K^-4
a     = 3.0e-9 W m^-2 sr^-1 um^-1 K^-4
tau4  = 1 in the Level 2 swath product
```

`A_pix` varies with scan angle.
**[NASA fact]** Collection 6 uses the Wooster-style radiance-difference retrieval; the common detection mean FRP changed from 56.9 MW in Collection 5 to 47.7 MW in Collection 6 for commonly detected pixels.

#### VIIRS 375 m

```text
FRP_i = (A * sigma / a) * (L13 - L13B)

sigma = 5.67e-8 W m^-2 K^-4
a     = 2.88e-9 W m^-2 sr^-1 um^-1 K^-4
transmittance = 1 assumed
surface emissivity = 1 assumed
```

A single 750 m FRP retrieval is divided among the coincident 375 m fire pixels:

```text
FRP_i = FRP_750m / number_of_coincident_375m_fire_pixels
```

For two coincident pixels, `FRP_i = FRP / 2`.

#### MODIS pixel geometry constants

```text
R_e = 6378.137 km
h   = 705 km
s   = 0.0014184397
theta = s * (sample - 676.5) radians
A_pix = deltaS * deltaT
```

#### Why raw FRP cannot be merged

- **[NASA fact]** `a`, background definition, pixel area, and spectral response differ.
- **[NASA fact]** The M13 channel overlaps a CO2 absorption band, potentially causing systematic VIIRS underestimation relative to MODIS.
- **[NASA fact]** Residual bow-tie pixels duplicate FRP; algorithm-QA bit 22 should be used to prevent double counting, but that bit is absent from FIRMS exports.
- **[KW synthesis]** FRP is a per-sensor diagnostic. A mixed-sensor FRP sum is not a defensible product.

### 6.6 Spatial gridding

**[NASA fact]** MODIS pixels are approximately 1 km at nadir and grow at the swath edge; VIIRS 375 m has three onboard aggregation zones and a more nearly constant footprint.
A nadir MODIS pixel contains about 4–9 VIIRS 375 m pixels depending on alignment; a swath-edge MODIS pixel can contain far more.

Consequences:

1. Never sum MODIS and VIIRS raw detections into a “fire count.”
2. Within VIIRS, one fire can also generate multiple 375 m detections.
3. Use a common-footprint metric, such as occupied 0.1° cell-days, for temporal comparison.
4. Preserve the Aqua-scale estimate, VIIRS-native counts, and raw counts as distinct series.

**[NASA fact]** MODIS has diamond-shaped equatorial swath gaps near ±30°; peer-reviewed work reported up to 12.5% underestimation of monthly MODIS FRP in a tropical study.
**[Peer-reviewed]** The 2026 fusion paper reports roughly 1–115 VIIRS pixels inside one MODIS footprint depending on geometry.

**[Project output]** Kiln Watch's 0.1° map cells and calendar totals can disagree by about −50% to +100% in individual months because empty observers receive nonzero weight at cell level.
**[KW synthesis]** Apply the area-level sensor weights to cells so that the map reconciles to the published area total by construction.

### 6.7 Count calibration

The current Kiln Watch estimator is transparent and auditable.
For calendar month `m`, with coverage-normalized reference and source totals `R_m` and `S_m`:

```text
r_m    = R_m / S_m
pooled = sum(R_m) / sum(S_m)
L      = log(pooled)
v_m    = 1 / R_m + 1 / S_m
tau2   = max(0, mean((log(r_m) - L)^2) - mean(v_m))
lambda = tau2 / (tau2 + v_m)
beta_m = exp(lambda * log(r_m) + (1 - lambda) * L)
```

The excess-Poisson log-ratio variance is estimated from residuals after the monthly factor is applied, with a conservative fallback when too few periods exist.

Sensor estimates in reference units are combined by inverse variance.
For estimates `(e_i, sigma2_i, cv_i)` with pooled mean `mu`:

```text
weight_i = 1 / max(mu^2 * sigma2_i + counting_variance_i, 1e-9)
combined = sum(weight_i * e_i) / sum(weight_i)
variance = 1 / sum(weight_i)
```

**[KW synthesis]** This is a good estimator to preserve because a judge can understand it in one slide.
**[Project output]** The audit identified three issues that must not be hidden: chain-composition bias, a non-stationary Terra→Aqua link, and a NOAA-21 estimator that performed worse than identity in the audited validation table.

#### Nested validation rule

Estimator or hyperparameter selection **requires nested validation**:

1. Reserve an outer temporal or geographic hold-out that is never consulted during model or estimator selection.
2. Within the remaining training data, use inner temporal folds to select identity, pooled, or seasonal empirical-Bayes calibration and to tune any parameter.
3. Refit the selected estimator on the allowed training data.
4. Evaluate the chosen estimator once on the untouched outer hold-out.

Selecting the estimator after looking at the outer test result leaks the test.
The existing validation table may guide a new nested experiment, but it cannot be reused as an unbiased selection-and-test result without a fresh outer split.

### 6.8 Static and dynamic thermal-anomaly masking

#### Official FIRMS precedent

```text
Static Thermal Anomaly mask:
400 m grid
calendar year 2023
VIIRS 375 m detection centroids
at least 5 detections in the year
AND spatial filtering with industrial / power-plant location databases
```

The FIRMS detections layer then includes MODIS, VIIRS, and Landsat detections intersecting or adjacent to masked areas.
The mask is for reference and is not distributed by FIRMS.

#### Dynamic MODIS `type`

```text
0 = presumed vegetation fire
1 = active volcano
2 = other static land source
3 = offshore
```

- `type` is available only in standard-quality MCD14ML, not NRT.
- NASA documents that some static sources remain unflagged.
- The flag therefore is a per-detection signal, not a complete physical classification.

#### Current Kiln Watch rule

```text
0.01 degree cell is static when:
count(typed rows) >= 3
AND count(static typed rows) >= 0.5 * count(typed rows)
```

Untyped rows are classified as static only if their cell is already in the mask; otherwise they are classified as vegetation.

**Risks:**

1. The 0.01° cell is coarser than the 375 m detection and a roughly 400 m official STA precedent.
2. The mask is computed over the whole record and applied to every year.
3. NRT rows lack `type`; 27–35% of the 2024–2026 published vegetation detections are NRT rows, rising to much higher shares in some areas and 100% in the last five published periods.
4. New industrial sites can be invisible until standard processing supplies a typed row.
5. The mask is not yet cross-checked against an industrial-asset or kiln inventory.

**[KW synthesis]** Build a sensor-independent, time-invariant static-site list from standard-quality data, cross-check it against assets, and keep the `type` signal as an independent field.
Until then, publish an explicit `unclassified` series.

### 6.9 FRP handling

The defensible output set is:

- **Aqua-scale estimated count:** for cross-era trend and anomaly comparison.
- **VIIRS-native count:** for what the higher-resolution sensor observed.
- **Per-sensor FRP summary:** for intensity diagnostics.

Do not create a mixed MODIS-plus-VIIRS FRP total.

A peer-reviewed duplicate rule can be applied within one sensor:

```text
duplicate if:
same sensor
AND absolute acquisition-time difference < 8 seconds
AND footprint overlap > 30%

Retain the highest-confidence record; break ties by earliest time.
Assign the group's mean FRP to the retained record.
```

**[Project output]** The local audit found 208 exact-location within-eight-second pairs among 7,959,277 cached detections, or 0.0026%.
**[KW synthesis]** This is useful cleanup but not a headline feature.

An optional VIIRS-to-MODIS-footprint cloud correction is:

```text
FRP_VIIRS_cor = FRP_VIIRS * (A + B) / (A + alpha * B^2 / (A + B))
alpha = 0.25
skip correction when cloud-free fraction is below 5%
```

`A` and `B` are cloud-free and cloud-covered area within the MODIS footprint.
This belongs to FRP diagnostics, not to the primary count estimator.

### 6.10 Temporal continuity

#### Sensor/product continuity

- **[NASA fact]** MODIS pre-November-2000 fire products contain striping, missed small and large fires, and rare false scan-line fires; NASA does not distribute the inconsistent CMG/location products for that period.
- **[NASA fact]** MODIS C6.1 high-quality coverage begins with Terra in November 2000 and Aqua on 2002-07-04.
- **[NASA fact]** VIIRS 375 m's effective record starts on 2012-01-20.
- **[NASA fact]** Suomi NPP ceased new science delivery at 15:40 UTC on 2026-11-02; NOAA-20 and NOAA-21 are the direct 375 m successors, about 50 minutes apart.
- **[NASA fact]** Terra and Aqua end-of-science dates have moved and should not be hard-coded; NASA's continuity research describes dynamic continuity for Aqua observations.

#### The 2023 Aqua change

**[Project output]** Kiln Watch measures a large shift in the reported local-solar acquisition time of MODIS daytime detections after 2022, coincident with the 6.03-to-61.03 archive version change.
Terra shifts in the opposite direction and VIIRS remains stable.

This is evidence of a **reported acquisition-time/archive shift**, not physical orbital drift.
The real orbital drift reported by NASA is on a much smaller scale than the two-hour metadata shift observed in the archive.
The response—being cautious about MODIS after the change—may be defensible, but the causal wording must be corrected.

#### Event continuity

**[NASA fact]** The FEDS algorithm associates new VIIRS detections with an existing fire object within five days, explicitly accounting for episodic detection gaps and clouds.
**[KW synthesis]** If Kiln Watch later adds a formal event layer, use and cite the FEDS rule rather than inventing a bespoke cluster window.

### 6.11 Uncertainty and validation

#### Current uncertainty mechanisms

1. **Counting uncertainty:** propagated through coverage normalization and inverse-variance combination.
2. **Calibration uncertainty:** empirical-Bayes between-month variance plus excess-Poisson log-ratio variance.
3. **Chain uncertainty:** variances add along the sensor chain; closure mismatch is added to the budget.
4. **Interval calibration:** split-conformal widening, with a separate fit/test coverage check.
5. **Sampling disclosure:** coverage is published beside values.

#### Current internal validation

- MODIS-denial reconstruction.
- Suomi-NPP withholding.
- Launch-transition step and placebo tests.
- Geographic hold-out/transfer validation.
- Mann-Kendall and Sen trends.
- Like-for-like acquisition-time comparison.
- Grid, mask, calibration-table, and data-integrity checks.

#### Unresolved uncertainty

- **[Project output]** the audited out-of-sample interval coverage was 91.7%, not 95%.
- **[Project output]** the conformal widening factor was fitted in a VIIRS-only configuration and then applied more broadly.
- **[Project output]** the 2023 acquisition-time transition was not included in the transition test.
- **[Project output]** the Terra→Aqua link had a −36.8% held-out bias in the audited Punjab case.
- **[Project output]** recent NRT class assignments are structurally uncertain.
- **[Verified]** no burned-area, ground-truth, or kiln-inventory validation is implemented.

#### Validation ladder

| Level | Question | Current state |
|---|---|---|
| Internal sensor consistency | Does the record survive withholding one sensor? | Implemented |
| Temporal stability | Are transitions and placebo dates flat? | Implemented for launches; missing for 2023 transition |
| Geographic transfer | Does the calibration work on unseen places? | Implemented with reported caveats |
| Detection opportunity | Can low counts be explained by clouds/no-data? | Only global observing-day denominator |
| Physical extent | Do detections correspond to burned area? | Recommended, not completed |
| Local truth | Do likely kilns match real facilities/operator evidence? | Recommended, not completed |
| Decision outcome | Did a user act better because of the product? | Recommended, not completed |

### 6.12 Peer-reviewed findings that should shape the next version

- **[Peer-reviewed]** MODIS and VIIRS sample differently; VIIRS generally detects more small and lower-intensity fires.
- **[Peer-reviewed]** In one global comparison, MODIS fire count fell about 67% from nadir to 60° view zenith angle while mean FRP per detection rose about 300%.
- **[Peer-reviewed]** In an Africa study, 79% of VIIRS fires missed by MODIS were in grids where MODIS view zenith angle exceeded 30°.
- **[Peer-reviewed]** MODIS can omit roughly 52% of VIIRS fires from nadir to scan edge in the cited 5° bands.
- **[Peer-reviewed]** VIIRS 375 m detects about 3× as many daytime and 17× as many nighttime fire pixels as VIIRS 750 m; 53% and 85%, respectively, have no 750 m match.
- **[Peer-reviewed]** The two sensors' FRP differences vary with fire size, season, and region; large boreal fires are a notable exception to simple equivalence.
- **[Peer-reviewed]** Equatorial swath gaps and cloud omission can create apparent cross-sensor steps independent of fire behavior.
- **[Peer-reviewed]** Super-heated plume parallax can displace isolated nighttime VIIRS detections, especially for very large fires at high scan angle.

### 6.13 Claim boundary

| Safe claim, with caveat | Claim to avoid |
|---|---|
| “Estimated hotspots on the Aqua-MODIS scale” | “The number of fires” |
| “FIRMS detections in occupied cells” | “Burned area” or “emissions” |
| “A calibrated estimate of what Aqua would have recorded” | “A continuous direct MODIS-to-VIIRS observation record” |
| “VIIRS native detections reveal smaller fires MODIS often misses” | “VIIRS is more accurate” |
| “Static thermal anomalies are separated by a published heuristic” | “Every static source is correctly identified” |
| “The 95% interval is a model-based uncertainty band” | “Every interval is empirically validated at 95%” |
| “The reported acquisition-time series changed after 2022” | “Aqua physically drifted two hours” |
| “The outlook is a climatological comparison” | “A 30-day forecast” |

---

## 7. Recommended implementation matrix

The matrix names exact current files where the change belongs.
A proposed new file is marked **new** rather than presented as existing code.

### 7.1 Now — P0/P1 submission blockers and high-certainty corrections

| ID | Item | Exact current files | Value | Scientific risk | Awards |
|---|---|---|---|---|---|
| N1 | Obtain written eligibility clarification | `docs/demo/SUBMISSION.md`, `README.md`; external GO-team request | Prevents an overriding disqualification risk | Submission eligibility | All |
| N2 | Make one canonical repository and correct tool count | `README.md`, `docs/demo/SUBMISSION.md`, `server/kw/mcp_server.py` | Stops judges landing on an older or contradictory project | No method change; integrity risk | All |
| N3 | Rename acquisition-time shift and add transition/placebo | `server/kw/build.py`, `server/kw/science.py`, `web/src/pages/Method.tsx`, `data/aqua_overpass.json`, `server/tests/test_build_rules.py` | Makes the largest rule auditable | Medium; diagnostic only | Data, Galactic |
| N4 | Add NRT `unclassified` share/class | `server/kw/firms.py`, `server/kw/build.py`, `server/kw/globe.py`, `web/src/pages/Method.tsx`, `server/tests/test_build_rules.py` | Stops recent untyped heat from silently becoming vegetation | High; published classes change | Data, Local |
| N5 | Implement nested estimator selection | `server/kw/science.py`, `server/kw/build.py`, `server/tests/test_science.py`, `server/tests/test_data_integrity.py` | Replaces a worse audited NOAA-21 estimator without test leakage | High; all published values change | Data |
| N6 | Mark or remove the first partial ISO week | `server/kw/science.py`, `server/kw/build.py`, `server/tests/test_science.py` | Removes a roughly 40% first-week inflation in the audited Punjab series | Medium; weekly/baseline values change | Data |
| N7 | Publish chain-composition bias and interval-coverage caveat | `server/kw/build.py`, `web/src/pages/Method.tsx`, `web/src/pages/Proof.tsx` | Makes uncertainty honest and judge-readable | Low; diagnostic/display change | Data |
| N8 | Reconcile map cells to area totals | `server/kw/build.py`, `web/src/Map.tsx`, `server/tests/test_data_integrity.py` | Removes −50%/+100% cell/calendar divergence | Medium; map values change | Data, Technology |
| N9 | Protect public MCP writes and cap custom builds | `server/kw/api.py`, `server/kw/mcp_server.py`, `server/kw/tools.py`, `server/kw/alerts.py`, `server/kw/regions.py` | Prevents abuse and the audited 500 error | Low science risk; high security/availability risk | Technology |
| N10 | Fix news/cache/CSV/read-path behavior | `server/kw/news.py`, `server/kw/news_more.py`, `server/kw/tools.py`, `server/kw/api.py`, `server/kw/outlook.py`, `server/kw/regions.py`, `server/kw/alerts.py` | Removes cold-path timeouts, torn cache reads, and memory-heavy CSV response | Low science risk; operational risk | Technology, Local |
| N11 | Make deployment reproducible and bounded | `Dockerfile`, `requirements.txt`, `server/requirements.txt`, `.dockerignore` **new**, `vercel.json` | Removes virtualenv bloat and dependency drift | Low | Technology, Galactic |
| N12 | Correct submission and public wording | `README.md`, `docs/demo/SUBMISSION.md`, `web/src/pages/Method.tsx`, `web/src/pages/Home.tsx` | Aligns claims with the audited estimand and caveats | High reputational/scientific risk if omitted | All |
| N13 | Add one judge-proof MCP workflow | `server/kw/mcp_server.py`, `server/kw/agent.py`, `server/kw/api.py`, `web/src/pages/Connect.tsx`, `web/src/pages/Home.tsx` | Converts tool count into a visible decision benefit | Low if numbers remain deterministic | Technology |
| N14 | Add focused regression tests | `server/tests/test_science.py`, `server/tests/test_build_rules.py`, `server/tests/test_data_integrity.py` | Prevents recurrence of coverage, mask, chain, and grid defects | Low | Data, Technology |

### 7.2 Next — highest award value after blockers

| ID | Item | Exact current files | Value | Scientific risk | Awards |
|---|---|---|---|---|---|
| X1 | Regional cloud/opportunity denominator | `server/kw/firms.py`, `server/kw/build.py`, `server/kw/outlook.py`, `server/tests/test_data_integrity.py` | Separates “not observed” from “not detected” | High; changes normalization and comparisons | Data, Galactic |
| X2 | Sensor-independent static-site list | `server/kw/build.py`, `server/kw/firms.py`, `server/kw/globe.py`, `web/src/pages/Method.tsx` | Removes a structural sensor-transition discontinuity | High; static/vegetation series change | Data, Local |
| X3 | Burned-area validation witness | `server/kw/cases.py`, `scripts/validate_burned_area.py` **new**, `server/tests/test_data_integrity.py` | Adds physical-extent truth without claiming perimeter equivalence | Medium; MCD64A1/Planetary Computer comparison scope must be explicit | Data, Galactic |
| X4 | Kiln-inventory/field validation | `scripts/validate_kiln_inventory.py` **new**, `server/kw/cases.py`, `web/src/pages/Bangladesh.tsx`, `docs/demo/SUBMISSION.md` | Converts “likely kiln” into evidence-backed local classification | Medium; OSM/APAD/inventory sources must be cited and limitations shown | Local, Data |
| X5 | Named local pilot | `web/src/pages/Bangladesh.tsx`, `server/kw/cases.py`, `server/kw/alerts.py`, `docs/demo/SUBMISSION.md` | Demonstrates a human outcome rather than a use case | Low science risk; evidence quality depends on partner documentation | Local |
| X6 | Bangla-first local UX | `web/src/App.tsx`, `web/src/pages/Bangladesh.tsx`, `web/src/pages/shared.tsx`, `web/src/pages/Warning.tsx` | Reaches the intended local audience | Low | Local |
| X7 | Versioned audit/data release | `server/kw/report.py`, `server/kw/build.py`, `server/kw/globe.py`, `server/tests/test_data_integrity.py` | Makes the record reusable and globally auditable | Medium; release must preserve estimand distinctions | Data, Galactic, Technology |
| X8 | Input fingerprints and rebuild manifest | `server/kw/firms.py`, `server/kw/build.py`, `server/kw/report.py` | Separates method change from mutable upstream data | Low | Data, Technology |
| X9 | Regional cloud-free and static-source audit release | `server/kw/report.py`, `web/src/pages/Proof.tsx`, `web/src/pages/Method.tsx` | Publishes no-data behavior beside every headline | Medium | Data |
| X10 | Fix deployment-dependent feature honesty | `server/kw/tools.py`, `server/kw/mcp_server.py`, `server/kw/api.py`, `web/src/pages/Connect.tsx`, `Dockerfile`, `vercel.json` | Prevents advertised tools from failing on the demo | Low | Technology |
| X11 | Strengthen accessibility verification | `web/src/pages/Record.tsx`, `web/src/pages/Proof.tsx`, `web/src/pages/Data.tsx` | Verifies keyboard and color-ramp behavior required by the challenge | Low | Local, Technology |

### 7.3 Later — scientifically valuable after the core is stable

| ID | Item | Exact current files | Value | Scientific risk | Awards |
|---|---|---|---|---|---|
| L1 | View-angle-stratified count sensitivity | `server/kw/firms.py`, `server/kw/build.py`, `server/kw/science.py`, `server/tests/test_science.py` | Addresses a first-order geometric omission mechanism | High; requires careful strata and nested evaluation | Data |
| L2 | FRP VZA/cloud sensitivity at common footprint | `server/kw/science.py`, `server/kw/build.py`, `server/kw/report.py` **new fields** | Separates geometry from radiometry for intensity diagnostics | High; FRP is not the primary count estimand | Data |
| L3 | FEDS-based event layer | `server/kw/build.py`, `server/kw/science.py`, `server/kw/cases.py`, `server/tests/test_science.py` | Adds scientifically citable temporal continuity | High; an event is not the current cell-day metric | Data, Galactic |
| L4 | Scheduled global refresh and stable public schema | `server/kw/globe.py`, `server/kw/outlook.py`, `server/kw/report.py`, `Dockerfile`, `vercel.json`, `.gitignore` | Moves from demo to maintained infrastructure | Medium; requires reproducibility and no-data semantics | Galactic, Data |
| L5 | One additional decision domain | `web/src/pages/Home.tsx`, `web/src/pages/Warning.tsx`, `server/kw/cases.py`, `docs/demo/SUBMISSION.md` | Extends impact without replacing the core record | Medium; scope dilution and unsupported claims | Galactic, Local |
| L6 | Low-bandwidth/offline package | `web/src/api.ts`, `web/src/App.tsx`, `server/kw/report.py`, `scripts/readme_figures.mjs` | Improves access where connectivity is weak | Low | Local, Galactic |

### 7.4 Sequencing rule

- Do not rebuild published data until the estimator, NRT class, first-week, and transition decisions are frozen.
- Run a fresh outer hold-out after estimator selection; preserve the old artifacts for audit comparison.
- Rebuild once, compare every changed series, and publish a migration note.
- Do not add a new model or event layer before the observation denominator and static-source uncertainty are visible.

---

## 8. Eligibility and repository hygiene warning

### 8.1 P0 submission blocker: pre-start work

The official GO Team response in “asking about the resources” states that teams should refrain from starting projects until the official 14–15 November hackathon, beginning at 9 a.m. local time, because **working ahead can lead to disqualification**.
Before the hackathon, teams may select a challenge, review resources, research the topic, and form teams.
At least one NASA data source from the challenge Resources tab is required for Global Awards.

Official source: <https://github.com/nasa/spaceapps/discussions/1827>

A separate participant discussion, “Clarification on eligibility of a project developed before November 14,” records that disclosure is not automatic permission and that the GO Team must make the determination.

Discussion: <https://github.com/nasa/spaceapps/discussions/1981>

**Implication for Kiln Watch:**

- The public `kiln-watch` repository was created on 2026-10-05, the current origin on 2026-11-13, and `docs/demo/SUBMISSION.md` already acknowledges prior work and a live site.
- The official wording says prior work **can** lead to disqualification; the source does not establish that every pre-start project is automatically ineligible.
- A README disclosure does not convert into permission.
- The project must obtain a **written GO-team clarification before submission** and record the response in the submission package.
- Until that response exists, eligibility is an unresolved P0 risk, not a footnote.

### 8.2 Canonical repository cleanup

The current Git origin is:

- <https://github.com/Aalvee-Aarham/nasaspaceappschallenge-2026-team-off-the-binary>

Older or parallel public repositories can redirect judges to different claims and partial products, including `kiln-watch`, `kiln-watch-video`, and `kiln-watch-2026`.
The submission should:

1. Name the current repository as the canonical submission repository.
2. Put a short archive/status banner on each older repository pointing to the canonical project.
3. Keep one README headline and one architecture diagram.
4. Make the submission link use the canonical URL.
5. Do not delete history or rewrite Git state merely to improve discoverability.

### 8.3 Tool-count inconsistency

- **[Verified]** `server/kw/mcp_server.py` declares **35** tools, four prompts/personas, and five resources.
- **[Verified]** the README top badge and image alternative text say **31 tools**.
- **[Verified]** the README product table image alternative text also says 31 while the adjacent text says 35.
- The backend audit independently received 35 tools from `tools/list`.

The submission should use **35** everywhere and add a small test or generator check so the count cannot drift silently.
This is a judge-facing credibility issue, not a scientific defect.

### 8.4 Additional hygiene before freeze

- Remove unresolved draft placeholders from the submission copy.
- Ensure the demo video and submission links point to the canonical repository and live deployment.
- Verify that every “live” feature works in the shipped environment or is visibly marked unavailable there.
- Keep the prior-work disclosure factual and do not describe disclosure as GO-team approval.
- Preserve source labels and claim provenance in the final deck; do not convert project outputs into “validated results.”

---

## 9. Sources

### 9.1 Official challenge, guidance, rules, and awards

- **NASA Space Apps 2026 — Harmonization of MODIS and VIIRS Hot Spots** — <https://www.spaceappschallenge.org/2026/challenges/modis-and-viirs-hot-spots/?tab=details>
- **Space Apps forum — Harmonization of MODIS and VIIRS approaches** — <https://github.com/nasa/spaceapps/discussions/1786>
- **Space Apps forum — Method, scale, FIRMS Standard, and NOAA continuation guidance** — <https://github.com/nasa/spaceapps/discussions/1879>
- **Space Apps forum — Regional AOI guidance** — <https://github.com/nasa/spaceapps/discussions/2016>
- **Space Apps forum — Team formation discussion** — <https://github.com/nasa/spaceapps/discussions/1823>
- **Space Apps forum — Official GO Team pre-start rule** — <https://github.com/nasa/spaceapps/discussions/1827>
- **Space Apps forum — Pre-November project eligibility clarification** — <https://github.com/nasa/spaceapps/discussions/1981>
- **Space Apps 2025 award definitions** — <https://www.spaceappschallenge.org/2025/awards/>
- **NASA — 2025 International Space Apps Challenge Global Winners** — <https://www.nasa.gov/learning-resources/stem-engagement-at-nasa/nasa-announces-2025-international-space-apps-challenge-global-winners>
- **NASA — 2024 International Space Apps Challenge Global Winners** — <https://www.nasa.gov/learning-resources/stem-engagement-at-nasa/nasa-international-space-apps-challenge-announces-2024-global-winners>
- **CONAE challenge partner description** — <https://www.argentina.gob.ar/noticias/desafio-nasa-space-apps-challenge-2026-crea-soluciones-para-monitorear-incendios-con-datos>

### 9.2 NASA primary science and product sources

- **Giglio, Schroeder, and Justice (2016), “The Collection 6 MODIS active fire detection algorithm and fire products”** — <https://www.earthdata.nasa.gov/sites/default/files/imported/Giglio2016_C6_Fire.pdf>
- **NASA LP DAAC (2020), MODIS Collection 6 Active Fire Product User's Guide, Rev. C** — <https://lpdaac.usgs.gov/documents/876/MOD14_User_Guide_v6.pdf>
- **Schroeder et al. (2014), “The New VIIRS 375 m active fire detection data product”** — <https://www.earthdata.nasa.gov/sites/default/files/imported/Schroeder_et_al_2014b_RSE.pdf>
- **NASA Land SIPS, VNP14IMG Algorithm Theoretical Basis Document** — <https://viirsland.gsfc.nasa.gov/PDF/VIIRS_activefire_375m_ATBD.pdf>
- **NASA Land SIPS (2018), VIIRS 375 m and 750 m Active Fire User's Guide** — <https://viirsland.gsfc.nasa.gov/PDF/VIIRS_activefire_User_Guide.pdf>
- **NASA Land SIPS (2025), Collection 2 VIIRS 375 m User's Guide v1.2** — <https://www.earthdata.nasa.gov/s3fs-public/2025-06/VIIRS_C2_AF-375m_User_Guide_1.2.pdf>
- **NASA Earthdata, Active Fire Data Attributes for MODIS and VIIRS** — <https://www.earthdata.nasa.gov/data/tools/firms/active-fire-data-attributes-modis-viirs>
- **NASA FIRMS FAQ** — <https://www.earthdata.nasa.gov/data/tools/firms/faq>
- **NASA FIRMS/LANCE, VIIRS Fire Hotspots description** — <https://firms.modaps.eosdis.nasa.gov/descriptions/FIRMS_VIIRS_Firehotspots.html>
- **NASA FIRMS Team (2026), “Transitioning from Suomi NPP VIIRS & OMPS”** — <https://www.earthdata.nasa.gov/news/blog/transitioning-from-suomi-npp-viirs-omps-what-firms-users-need-know>
- **NASA Earthdata (2026), Suomi NPP observation cessation alert** — <https://www.earthdata.nasa.gov/data/alerts-outages/reminder-new-suomi-npp-observations-cease-november-2-2026>
- **NASA Earthdata (2025), Transition from MODIS to VIIRS** — <https://www.earthdata.nasa.gov/data/alerts-outages/transition-from-modis-viirs>
- **NASA LAADS DAAC (2025), MODIS to VIIRS transition** — <https://ladsweb.modaps.eosdis.nasa.gov/learn/modis-to-viirs-transition/MODIS-VIIRS_Transition.pdf>
- **NASA VIIRS Land Products, Active Fire products** — <https://viirsland.gsfc.nasa.gov/Products/NASA/FireESDR.html>
- **NASA FIRMS Download Readme, product naming** — <https://firms.modaps.eosdis.nasa.gov/download/Readme.txt>
- **MODIS Land Team, MODIS Land validation status** — <https://modis-land.gsfc.nasa.gov/ValStatus.php?ProductID=MYD14>
- **NASA NTRS (2019), FIRMS: Near Real-Time Global Fire Monitoring** — <https://ntrs.nasa.gov/citations/20190032007>
- **Copernicus CAMS (2026), “Drifting away from MODIS in CAMS GFAS”** — <https://atmosphere.copernicus.eu/drifting-away-modis-cams-global-fire-assimilation-system>

### 9.3 Peer-reviewed and official literature

- **Csiszar et al. (2014), “Active fires from the Suomi NPP VIIRS”** — <https://doi.org/10.1002/2013JD020453>
- **Hall/Wang et al. (2018), “Comparison of Fire Radiative Power Estimates From VIIRS and MODIS Observations”** — <https://doi.org/10.1029/2017JD027823>
- **Zhang et al. (2020), MODIS versus VIIRS in Northeast Asia** — <https://www.mdpi.com/2072-4292/12/18/2870>
- **Zhang et al. (2020), FRP missed by MODIS in Africa** — <https://www.mdpi.com/2072-4292/12/10/1561>
- **Sundar et al. (2018), MODIS Aqua versus VIIRS in Punjab** — <https://pmc.ncbi.nlm.nih.gov/articles/PMC6108185/>
- **Román et al. (2024), MODIS C6.1 to VIIRS C2 continuity** — <https://doi.org/10.1016/j.rse.2023.113963>
- **Remote Sensing 18(10):1650 (2026), FRP correction and spatiotemporal fusion** — <https://www.mdpi.com/2072-4292/18/10/1650>
- **Giglio et al. (2018), Collection 6 MODIS burned-area algorithm** — <https://doi.org/10.1016/j.rse.2018.08.005>
- **Giglio et al. (2025), VIIRS burned-area product and intercomparison** — <https://doi.org/10.1016/j.rse.2025.115006>
- **Chen et al. (2022), FEDS event-detection method and five-day association** — <https://earth-information-system.github.io/fireatlas/docs>

### 9.4 Competitor and prior-project links

- **SHIFT** — <https://github.com/squadronzero/project-shift>
- **Flare-Chronos** — <https://github.com/the-aris-club/flare-chronos>
- **Fire Harmony** — <https://github.com/Warren-530/fire-harmony>
- **Fire Harmony dataset** — <https://huggingface.co/datasets/warrensaw530/fire-harmony>
- **FireLens (`abubokkor-cse`)** — <https://github.com/abubokkor-cse/firelens>
- **Dahan / Phoenix007** — <https://github.com/Saobia3i/Phoenix007>
- **Parallax Fire** — <https://github.com/Shahriar290900/Harmonisation-MODIS-VIIRS>
- **BD-FireOps** — <https://github.com/shahriyarcse-arch/BD_FireOps---Nasa-Space-Apps-Challange>
- **Agun Panjika** — <https://github.com/polymathicX/Agun-Panjika>
- **Icarus** — <https://github.com/mdhabibullahmahmudncs13/Icarus-Harmonization-of-MODIS-and-VIIRS-Hot-Spots>
- **SparkGrid** — <https://github.com/freefirenoobs/sparkgrid>
- **Ignis-Atlassia / FireAtlas** — <https://github.com/AhnafZ778/Ignis-Atlassia>
- **Zakarpattia Orbit** — <https://github.com/Kolok2008/zakarpattia-orbit>
- **FireChronicle (`inan001`)** — <https://github.com/inan001/firechronicle>
- **FireChronicle preparation repository** — <https://github.com/bhavishyaone1/FireChronicle>
- **Four-Bits and a Byte** — <https://github.com/OmarHedaya/Four-Bits-and-a-Byte>
- **Triton wildfire** — <https://github.com/pulik181/triton-wildfire>
- **Kelvin** — <https://github.com/RomanMayor/Kelvin>
- **Team I.O. GROW prior art** — <https://github.com/Florianopolis-NASA-Space-Apps/wildfires_chat_dashboard>
- **Team Starflock FIREX-AQ prior art** — <https://github.com/GaelleMG/starflock_firexaq>
- **Spot That Fire V2 prior art** — <https://github.com/rcslaney/NASA-Space-Apps-Spot-The-Fire-v2.0>
- **Project Firewatch 2017 prior art** — <https://github.com/osteth/project-firewatch>

### 9.5 Local evidence paths

- `/tmp/opencode/nasa-space-apps-2026/research_notes/github_competitors.md` — live competitor discovery, official challenge fit, award patterns, eligibility rule, and source index.
- `/tmp/opencode/nasa-space-apps-2026/research_notes/nasa_science.md` — NASA primary-source equations, constants, product caveats, peer-reviewed findings, and implementation synthesis.
- `/tmp/opencode/nasa-space-apps-2026/research_notes/system_map.md` — Kiln Watch architecture, data flow, tests, deployment, and simulated-versus-real inventory.
- `/tmp/opencode/nasa-space-apps-2026/research_notes/backend_latency.md` — read-only backend security, latency, memory, cache, and deployment findings.
- `/tmp/opencode/nasa-space-apps-2026/research_notes/science_pipeline_audit.md` — read-only reproduction of committed pipeline outputs and material science findings.
- `/tmp/opencode/nasa-space-apps-2026/research_notes/lead_synthesis_notes.md` — frontend findings quoted from the parent-session summary, award patterns, strengths, risks, and synthesis priorities.

### 9.6 Repository files most relevant to implementation

- `server/kw/science.py` — ratio calibration, combination, conformal interval, drift onset, trends, warning statistics.
- `server/kw/build.py` — data classification, coverage, calibration chain, gridding, validation, generated artifacts.
- `server/kw/firms.py` — FIRMS source, confidence filter, sensor days, cache behavior.
- `server/kw/globe.py` — whole-Earth aggregation and outlook data path.
- `server/kw/tools.py` — shared deterministic public functions and custom-area builds.
- `server/kw/mcp_server.py` — 35 MCP tools, prompts, and resources.
- `server/kw/agent.py` — optional Gemini tool-call trace and deterministic fallback.
- `server/kw/api.py` — REST surface and public MCP mount.
- `server/kw/cases.py` — evidence casebook and reserved burned-area/inventory fields.
- `server/kw/report.py` — generated report path.
- `web/src/pages/Home.tsx` — cinematic story and judge entry point.
- `web/src/pages/Method.tsx` — method explanation and disclosed limitations.
- `web/src/pages/Proof.tsx` — validation scorecard.
- `web/src/pages/Bangladesh.tsx` — local kiln use case.
- `web/src/pages/Connect.tsx` — MCP and integration surface.
- `README.md` — headline claims, data table, architecture, awards, and current count inconsistency.
- `docs/demo/SUBMISSION.md` — submission text and prior-work disclosure.

---

## Closing assessment

**[Inference]** Kiln Watch does not need to become the broadest project in the field.
It needs to become the project that a judge can trust in three minutes: a real local problem, one NASA record with a clearly defined estimand, uncertainty that matches the method, and an agent workflow whose numbers can be traced back to the same pipeline.

The highest-value work is therefore corrective and integrative:
clarify eligibility, repair the most material estimate/label issues, make the scientific limits visible, obtain independent witnesses, and turn the existing deterministic tool layer into one reliable local decision demo.

Everything else is lower priority than doing those things well.
