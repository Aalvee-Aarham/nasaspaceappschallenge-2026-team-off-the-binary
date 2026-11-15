import { useEffect, useRef, useState } from "react";
import { FarmCheck as Farm, PlaceLevel, PlaceRisk, api, farmCheck, placeRisk, ttsAudio } from "./api";
import { PlaceAlert } from "./exposure";
import Loader from "./Loader";

// Bangladesh: "What is near your field?" for farmers. Kilns from the APAD inventory (never FIRMS, which cannot find kilns),
// fire this week and fire months from /api/place-risk, Boro stages from the BAMIS crop calendar. Bangla first, few words.
// ponytail: Bangla strings written in-house; have a native speaker on the team read them before a wide release.

type Lang = "bn" | "en";
const LANG_KEY = "kw.lang";
const KILN = "#d95926", FIRE = "#FF3B2F", YOU = "#00A1FF";
const MON = {
  bn: ["জানু", "ফেব্রু", "মার্চ", "এপ্রি", "মে", "জুন", "জুলা", "আগ", "সেপ্টে", "অক্টো", "নভে", "ডিসে"],
  en: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
};
/** Boro by calendar month (1-12): the BAMIS crop-weather calendars (Dhaka, Rajshahi, Rangpur) run Dec-May, 150-155 days. */
const BORO: Record<number, "seed" | "plant" | "grow" | "flower" | "harvest"> = { 12: "seed", 1: "plant", 2: "grow", 3: "flower", 4: "harvest", 5: "harvest" };
const BORO_SRC = "https://bamis.gov.bd";
const HARVEST = [4, 5];
const EXAMPLES = [{ bn: "আমিনবাজার", en: "Aminbazar", q: "Aminbazar, Savar, Bangladesh" }, { bn: "ফরিদপুর", en: "Faridpur", q: "Faridpur, Bangladesh" },
  { bn: "ধামরাই", en: "Dhamrai", q: "Dhamrai, Bangladesh" }, { bn: "পাবনা", en: "Pabna", q: "Pabna, Bangladesh" }];

const T = {
  bn: {
    ask: "আপনার জমির কাছে কী আছে?", why: "জমির কাছের ইটভাটা দেখান: তারিখসহ, স্যাটেলাইট ছবিতে মেলানো রেকর্ড। কৃষি অফিসে নিয়ে যান।",
    smoke: "ধোঁয়া, ৩ কিমির ইটভাটা (আনুমানিক)", tons: (pm: string, so2: string) => `বছরে ${pm} টন PM2.5 · ${so2} টন SO2`,
    nSmoke: "ধোঁয়া (আনুমানিক)", nSmokeS: "টন PM2.5 বছরে, সব ইটভাটা মিলে", ph: "গ্রাম বা বাজারের নাম", check: "দেখুন", checking: "খোঁজা হচ্ছে…", here: "আমার অবস্থান",
    empty: "জায়গার নাম লিখুন।", noPlace: "জায়গাটি পাওয়া যায়নি। কাছের উপজেলার নাম লিখুন।", noGeo: "অবস্থান পাওয়া যায়নি। নাম লিখুন।",
    failed: "উত্তর আসেনি। আবার চেষ্টা করুন।", you: "আপনার অবস্থান",
    kilns: "ইটভাটা", in1: "১ কিমির মধ্যে", in3: "৩ কিমির মধ্যে", nearest: "সবচেয়ে কাছে", piece: "টি",
    outside: "বাংলাদেশের বাইরে। তথ্য নেই।", noData: "এই এলাকার ইটভাটার তথ্য নেই।",
    fire: "এই সপ্তাহে আগুন", fire5: (n: string) => `৫ কিমির মধ্যে ${n}টি`, fire0: "৫ কিমির মধ্যে নেই", fireNear: (d: string) => `সবচেয়ে কাছে ${d}`,
    month: (more: boolean, k: string, n: string) => `এই মাসে আগুন আগের ${n} বছরের মধ্যে ${k} বছরের চেয়ে ${more ? "বেশি" : "কম"} (সব স্যাটেলাইট এক মাপে)।`,
    fireNo: "উত্তর আসেনি", fireWait: ["নাসার স্যাটেলাইটে গত ৭ দিন দেখা হচ্ছে"], fireEta: "সাধারণত ১ মিনিটের কম; ব্যস্ত থাকলে ২–৩ মিনিট",
    boro: "বোরো মৌসুম", rBoro: "বোরো", rFire: "আগুন", rKiln: "ইটভাটা",
    stage: { seed: "বীজ", plant: "রোপণ", grow: "বৃদ্ধি", flower: "ফুল", harvest: "কাটা" },
    harvestFire: (a: string, b: string, n: string) => `কাটার মাসে আগুন: এপ্রিলে ${a}, মে-তে ${b} বছর (গত ${n} বছরে)।`,
    harvestTip: "পাকা ধান ও খড় পোড়ানো জমি থেকে দূরে রাখুন।",
    harvestNow: "কাটার মৌসুমে এই সপ্তাহে কাছে আগুন দেখা গেছে।",
    key: (n: string) => `সংখ্যা = গত ${n} বছরে কত বছর আগুন দেখা গেছে।`,
    mail: "ইমেইলে পাঠান", print: "প্রিন্ট", listen: "শুনুন", stop: "থামুন", whatsapp: "হোয়াটসঅ্যাপে পাঠান",
    gloss: "PM2.5 = সূক্ষ্ম ধোঁয়ার কণা, ফুসফুসের ক্ষতি করে। SO2 = সালফার গ্যাস, ফসলের ক্ষতি করতে পারে।",
    mailHelp: "উপজেলা কৃষি অফিস বা পরিবেশ অধিদপ্তরে পাঠান। ছবি যোগ করুন।",
    more: "তথ্যের সীমা", emergency: "সরকারি সতর্কবার্তা নয়। আগুন দেখলে ৯৯৯।",
    lim: (f: string, p: string) => [
      "তালিকায় ইটভাটার অবস্থান আছে, আজ চলছে কি না নেই।",
      `সব ইটভাটা নেই: ঢাকার আশেপাশে স্যাটেলাইটে দেখা ইটভাটার ${f}%। অবস্থানের ${p}% স্যাটেলাইট ছবির সাথে মেলে।`,
      "তালিকা দেশের পশ্চিম অংশের। চট্টগ্রাম ও সিলেট নেই।",
      "আইন ভাঙা হয়েছে কি না, তা পরিবেশ অধিদপ্তর ঠিক করে।",
      "আগুনের চিহ্ন মানে তাপ: খড়, ইটভাটা বা কারখানাও হতে পারে।",
      "বোরো মাসগুলো BAMIS শস্য পঞ্জিকা থেকে; আপনার জমিতে কয়েক সপ্তাহ আগে-পরে হতে পারে।",
      "ধোঁয়ার হিসাব মডেল থেকে (ইটভাটার ধরন অনুযায়ী), মাপা নয়। ইটভাটা কোথায় আছে তা দেখায়; ফসলের ক্ষতি প্রমাণ করে না।",
    ],
    nation: "সারা দেশে", nKilns: "ইটভাটা", nCrop: "কৃষিজমির পাশে", nCropS: "চারপাশের অর্ধেক জমি কৃষিজমি",
    nKey: "কমলা = কৃষিজমির পাশে। মানচিত্রে চাপ দিন। দাগের পূর্বে তথ্য নেই।", report: "ইটভাটার কাছের জমি", src: "সূত্র",
  },
  en: {
    ask: "What is near your field?", why: "Show the kilns near your field: a dated record, checked against satellite images. Take it to the agriculture office.",
    smoke: "Smoke from kilns within 3 km (estimated)", tons: (pm: string, so2: string) => `${pm} t PM2.5 · ${so2} t SO2 a year`,
    nSmoke: "Smoke (estimated)", nSmokeS: "tonnes of PM2.5 a year, all kilns", ph: "Village or market", check: "Check", checking: "Checking…", here: "Use my location",
    empty: "Type a place name.", noPlace: "Place not found. Try the nearest upazila.", noGeo: "Location not available. Type a name.",
    failed: "No answer. Try again.", you: "your location",
    kilns: "Brick kilns", in1: "within 1 km", in3: "within 3 km", nearest: "nearest", piece: "",
    outside: "Outside Bangladesh. No data.", noData: "No kiln data for this area.",
    fire: "Fire this week", fire5: (n: string) => `${n} within 5 km`, fire0: "None within 5 km", fireNear: (d: string) => `closest ${d}`,
    month: (more: boolean, k: string, n: string) => `This month: ${more ? "more" : "less"} fire than in ${k} of the previous ${n} years (MODIS and VIIRS on one scale).`,
    fireNo: "No answer", fireWait: ["Asking NASA satellites about the last 7 days"], fireEta: "usually under a minute; up to 2 to 3 minutes when busy",
    boro: "Boro season", rBoro: "Boro", rFire: "Fire", rKiln: "Kilns",
    stage: { seed: "Seedbed", plant: "Plant", grow: "Grow", flower: "Flower", harvest: "Harvest" },
    harvestFire: (a: string, b: string, n: string) => `Fire in harvest months: April ${a}, May ${b} of the last ${n} years.`,
    harvestTip: "Keep ripe paddy and straw away from burning fields.",
    harvestNow: "Fire seen nearby this week, in harvest season.",
    key: (n: string) => `Number = years with fire, of the last ${n}.`,
    mail: "Email report", print: "Print", listen: "Listen", stop: "Stop", whatsapp: "Send on WhatsApp",
    gloss: "PM2.5 = fine smoke particles that harm lungs. SO2 = sulphur gas that can harm crops.",
    mailHelp: "Send to the Upazila Agriculture Office or the Department of Environment. Add photos.",
    more: "Limits of the data", emergency: "Not an official warning. Fire: call 999.",
    lim: (f: string, p: string) => [
      "The list shows where kilns stand, not whether one is firing today.",
      `It misses kilns: around Dhaka it has ${f}% of those seen by satellite; ${p}% of its positions match satellite images.`,
      "It covers the west of the country only. Chattogram and Sylhet are not in it.",
      "Whether a kiln breaks the law is for the Department of Environment.",
      "A fire spot is heat: burning straw, a kiln or a factory.",
      "Boro months are from the BAMIS crop calendar; your field can be a few weeks earlier or later.",
      "Smoke figures are modelled by kiln type, not measured. The record shows where kilns stand; it does not prove crop damage.",
    ],
    nation: "Across Bangladesh", nKilns: "Brick kilns", nCrop: "Next to farmland", nCropS: "half the land around them is cropland",
    nKey: "Orange = next to farmland. Tap the map. No data east of the dashed line.", report: "Farmland near brick kilns", src: "Sources",
  },
};
const LEVEL_WORD: Record<Lang, Record<PlaceLevel, string>> = {
  bn: { near: "কাছেই আগুন", watch: "সতর্ক থাকুন", season: "আগুনের মৌসুম", low: "এখন কম", unknown: "জানা যায়নি" },
  en: { near: "Fire close by", watch: "Stay alert", season: "Fire season", low: "Low right now", unknown: "Could not check" },
};

const num = (v: number, lang: Lang, d = 0) => v.toLocaleString(lang === "bn" ? "bn-BD" : "en-US", { maximumFractionDigits: d });
const dist = (k: number, lang: Lang) => k < 1
  ? `${num(Math.max(10, Math.round(k * 100) * 10), lang)} ${lang === "bn" ? "মিটার" : "m"}`
  : `${num(k, lang, 1)} ${lang === "bn" ? "কিমি" : "km"}`;

function useLang(): [Lang, (l: Lang) => void] {
  const [lang, set] = useState<Lang>(() => { try { return localStorage.getItem(LANG_KEY) === "en" ? "en" : "bn"; } catch { return "bn"; } });
  return [lang, (l) => { set(l); try { localStorage.setItem(LANG_KEY, l); } catch { /* private mode */ } }];
}

/** The browser's voice for the language, if it has one (desktop Chrome has no Bangla voice). */
function useVoice(lang: Lang) {
  const [v, setV] = useState<SpeechSynthesisVoice | null>(null);
  useEffect(() => {
    if (!("speechSynthesis" in window)) return;
    const pick = () => setV(speechSynthesis.getVoices().find((x) => x.lang.toLowerCase().startsWith(lang)) ?? null);
    pick();
    speechSynthesis.addEventListener("voiceschanged", pick);
    return () => { speechSynthesis.removeEventListener("voiceschanged", pick); speechSynthesis.cancel(); };
  }, [lang]);
  return v;
}

/** What a voice reads badly ("PM2.5", "SO2", "কিমি"), in words. */
const SPOKEN: Record<Lang, [RegExp, string][]> = {
  bn: [[/PM2\.5/g, "সূক্ষ্ম ধোঁয়ার কণা"], [/SO2/g, "সালফার গ্যাস"], [/কিমি/g, "কিলোমিটার"], [/ · /g, ", "]],
  en: [[/ t PM2\.5/g, " tonnes of fine smoke particles"], [/ t SO2/g, " tonnes of sulphur gas"], [/(\d) km\b/g, "$1 kilometres"], [/(\d) m\b/g, "$1 metres"], [/ · /g, ", "]],
};
const spoken = (s: string, lang: Lang) => SPOKEN[lang].reduce((a, [re, w]) => a.replace(re, w), s);

/** Read the sentences aloud: the browser's voice when it has one, else the server's neural voice, else the browser
 *  with the language set and no voice (some phones speak anyway). One utterance per sentence: some Chrome versions
 *  cut long ones off. */
function useSpeaker(lang: Lang): [boolean, (lines: string[]) => void] {
  const voice = useVoice(lang);
  const [on, setOn] = useState(false);
  const stop = useRef<() => void>(() => undefined);
  useEffect(() => () => stop.current(), []);
  const browser = (lines: string[]) => {
    if (!("speechSynthesis" in window)) { setOn(false); return; }
    speechSynthesis.cancel();
    lines.forEach((l, i) => {
      const u = new SpeechSynthesisUtterance(l);
      if (voice) u.voice = voice;
      u.lang = voice?.lang ?? (lang === "bn" ? "bn-BD" : "en-US");
      u.onerror = () => setOn(false);
      if (i === lines.length - 1) u.onend = () => setOn(false);
      speechSynthesis.speak(u);
    });
    stop.current = () => speechSynthesis.cancel();
  };
  const play = async (lines: string[]) => {
    if (on) { stop.current(); setOn(false); return; }
    const said = lines.map((l) => spoken(l, lang));
    setOn(true);
    if (voice) { browser(said); return; }
    const ac = new AbortController();
    stop.current = () => ac.abort();
    try {
      const url = URL.createObjectURL(await ttsAudio(said.join(" "), lang, ac.signal)), a = new Audio(url);
      a.onended = a.onerror = () => { setOn(false); URL.revokeObjectURL(url); };
      stop.current = () => { a.pause(); URL.revokeObjectURL(url); };
      await a.play();
    } catch {
      if (!ac.signal.aborted) browser(said);
    }
  };
  return [on, play];
}

type Target = { lat: number; lon: number; name: string };

export default function FarmCheck({ online }: { online: boolean }) {
  const [lang, setLang] = useLang();
  const t = T[lang];
  const [q, setQ] = useState("");
  const [nat, setNat] = useState<Farm | null>(null);
  const [target, setTarget] = useState<Target | null>(null);
  const [farm, setFarm] = useState<Farm | null>(null);
  const [fire, setFire] = useState<PlaceRisk | null>(null);
  const [fireErr, setFireErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [fireBusy, setFireBusy] = useState(false);
  const [err, setErr] = useState("");
  const latest = useRef(0);
  const out = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!online) return;
    let live = true;
    farmCheck().then((d) => live && setNat(d)).catch(() => undefined);   // the national map is extra; the check still works
    return () => { live = false; };
  }, [online]);

  const run = (x: Target) => {
    history.replaceState(null, "", placeLink(x).slice(location.origin.length));   // the address bar now opens this answer
    const id = ++latest.current;
    const mine = () => latest.current === id;
    setTarget(x); setFarm(null); setFire(null); setFireErr(""); setErr(""); setBusy(true); setFireBusy(true);
    requestAnimationFrame(() => out.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
    farmCheck(x.lat, x.lon).then((d) => mine() && setFarm(d)).catch((e) => mine() && setErr(`${t.failed} (${e.message})`)).finally(() => mine() && setBusy(false));
    placeRisk({ lat: x.lat, lon: x.lon, label: x.name, radius_km: 5, facilities: false })
      .then((d) => mine() && setFire(d)).catch((e) => mine() && setFireErr(e.message)).finally(() => mine() && setFireBusy(false));
  };
  const find = async (query: string) => {
    const s = query.trim();
    if (!s) { setErr(t.empty); return; }
    setErr(""); setBusy(true);
    try {
      const r = await api.findPlace(/bangladesh|বাংলাদেশ/i.test(s) ? s : `${s}, Bangladesh`);
      const c = r.candidates?.find((x) => x.country_code === "bd") ?? (r.found && r.country_code === "bd" ? r : null);
      if (!c || c.lat == null || c.lon == null) { setErr(t.noPlace); setBusy(false); return; }
      run({ lat: +c.lat.toFixed(5), lon: +c.lon.toFixed(5), name: (c.name ?? s).split(",")[0] });
    } catch { setErr(t.failed); setBusy(false); }
  };
  const here = () => {
    if (!navigator.geolocation) { setErr(t.noGeo); return; }
    navigator.geolocation.getCurrentPosition(
      (p) => { setQ(""); run({ lat: +p.coords.latitude.toFixed(5), lon: +p.coords.longitude.toFixed(5), name: t.you }); },
      () => setErr(t.noGeo), { timeout: 15000, maximumAge: 600000 });
  };

  // deep link: #pg=bangladesh&at=23.79,90.32&n=Aminbazar (or &q=Aminbazar) opens a finished answer
  useEffect(() => {
    const h = new URLSearchParams(location.hash.slice(1)), at = (h.get("at") ?? "").split(",").map(Number), q0 = h.get("q");
    if (at.length === 2 && at.every(Number.isFinite)) run({ lat: at[0], lon: at[1], name: h.get("n") || `${at[0]}, ${at[1]}` });
    else if (q0) { setQ(q0); find(q0); }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (!online) return <p className="warn">{t.failed}</p>;

  return (
    <div className="fk" lang={lang}>
      <form className="pr-search fk-search" onSubmit={(e) => { e.preventDefault(); find(q); }} role="search">
        <div className="fk-top">
          <label htmlFor="fk-q" className="pr-ask">{t.ask}</label>
          <div className="fk-lang" role="group" aria-label="Language / ভাষা">
            <button type="button" className={lang === "bn" ? "on" : ""} aria-pressed={lang === "bn"} onClick={() => setLang("bn")} lang="bn">বাংলা</button>
            <button type="button" className={lang === "en" ? "on" : ""} aria-pressed={lang === "en"} onClick={() => setLang("en")} lang="en">English</button>
          </div>
        </div>
        <p className="fk-why">{t.why}</p>
        <button type="button" className="fk-here" onClick={here} disabled={busy}><span aria-hidden>📍</span> {t.here}</button>
        <div className="pr-row">
          <input id="fk-q" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t.ph} autoComplete="off" enterKeyHint="search" />
          <button className="pr-go" type="submit" disabled={busy}>{busy ? t.checking : t.check}</button>
        </div>
        <p className="pr-try">{EXAMPLES.map((x) => <button type="button" key={x.q} onClick={() => { setQ(x[lang]); find(x.q); }}>{x[lang]}</button>)}</p>
      </form>

      <div ref={out} aria-live="polite">
        {err && <p className="pr-err" role="alert">{err}</p>}
        {target && busy && !farm && <div className="skeleton tall" />}
        {target && farm?.place && <Result lang={lang} x={target} farm={farm} fire={fire} fireBusy={fireBusy} fireErr={fireErr} />}
      </div>

      {nat && <Nation lang={lang} d={nat} onPick={(lat, lon) => run({ lat, lon, name: `${num(lat, lang, 3)}, ${num(lon, lang, 3)}` })} />}
    </div>
  );
}

function Result({ lang, x, farm, fire, fireBusy, fireErr }: { lang: Lang; x: Target; farm: Farm; fire: PlaceRisk | null; fireBusy: boolean; fireErr: string }) {
  const t = T[lang];
  const p = farm.place!;
  const cc = farm.cross_check;
  const [speaking, listen] = useSpeaker(lang);
  const say = summary(lang, x, farm, fire);
  const r = fire?.recent, mo = fire?.built_area?.month;
  return (
    <article className="fk-res">
      <p className="fk-where"><span aria-hidden>📍</span> <b>{x.name}</b></p>

      {!p.covered ? <p className="pr-err">{p.in_bangladesh ? t.noData : t.outside}</p> : (
        <section className={`fk-kiln ${p.within_1km ? "hot" : p.within_3km ? "warm" : "ok"}`} aria-label={t.kilns}>
          <h3><span aria-hidden>🧱</span> {t.kilns}</h3>
          <div className="fk-big">
            <div><b>{num(p.within_1km!, lang)}{t.piece}</b><span>{t.in1}</span></div>
            <div><b>{num(p.within_3km!, lang)}{t.piece}</b><span>{t.in3}</span></div>
            <div><b>{p.nearest_km! <= 3 ? dist(p.nearest_km!, lang) : "–"}</b><span>{t.nearest}</span></div>
          </div>
          {!!p.within_3km && p.pm25_t_yr_3km != null && p.so2_t_yr_3km != null &&
            <p className="fk-smoke"><span>{t.smoke}</span> <b>{t.tons(num(p.pm25_t_yr_3km, lang), num(p.so2_t_yr_3km, lang))}</b><small>{t.gloss}</small></p>}
        </section>
      )}

      <div className="fk-pair">
        <section className="pr-sec fk-fire" aria-label={t.fire}>
          <h3><span aria-hidden>🔥</span> {t.fire}</h3>
          {fireBusy ? <Loader compact steps={t.fireWait} expected={30} eta={t.fireEta} />
            : fireErr || !fire || r == null ? <p className="pr-err">{t.fireNo}</p>
            : <>
              <p className="fk-lvl" data-l={fire.level}>{LEVEL_WORD[lang][fire.level]}</p>
              {r.count === 0 ? <p className="fk-ok">{t.fire0}</p> : <p className="fk-hot"><b>{t.fire5(num(r.count, lang))}</b> · {t.fireNear(dist(r.nearest_km!, lang))}</p>}
              {mo && <p className="fk-help">{monthLine(lang, mo)}</p>}
            </>}
        </section>
        <section className="pr-sec fk-mapbox">
          <LocalMap lang={lang} x={x} kilns={p.kilns ?? []} fires={r?.detections ?? []} />
        </section>
      </div>

      <Boro lang={lang} season={fire?.season ?? null} kilnMonths={farm.kiln_months} fireNow={(r?.count ?? 0) > 0} />

      <section className="pr-sec fk-act">
        <div className="fk-btns">
          <a className="pr-go fk-btn" href={mailto(lang, x, say)}><span aria-hidden>✉️</span> {t.mail}</a>
          <a className="pr-here fk-btn" href={`https://wa.me/?text=${encodeURIComponent([...say, placeLink(x)].join("\n"))}`} target="_blank" rel="noreferrer"><span aria-hidden>💬</span> {t.whatsapp}</a>
          <button type="button" className="pr-here fk-btn" onClick={() => window.print()}><span aria-hidden>🖨️</span> {t.print}</button>
          <button type="button" className="pr-here fk-btn" onClick={() => listen(say)} aria-pressed={speaking}><span aria-hidden>🔊</span> {speaking ? t.stop : t.listen}</button>
          <PlaceAlert lat={x.lat} lon={x.lon} label={x.name} />
        </div>
        <p className="fk-help">{t.mailHelp}</p>
      </section>

      <p className="fk-help fk-emer">{t.emergency}</p>
      <details className="cx-more fk-lim">
        <summary>{t.more}</summary>
        <ul>{t.lim(num(cc?.s2_labelled_with_apad_within_500m_pct ?? 0, lang), num(cc?.apad_within_300m_of_s2_pct ?? 0, lang, 1)).map((s) => <li key={s}>{s}</li>)}</ul>
        <p className="muted small">{t.src}: <a href={farm.inventory.registry} target="_blank" rel="noreferrer">APAD</a> ({farm.inventory.licence}) · <a href={farm.cropland.url} target="_blank" rel="noreferrer">ESA WorldCover</a> · NASA FIRMS, MODIS, Black Marble · <a href={BORO_SRC} target="_blank" rel="noreferrer">BAMIS</a></p>
      </details>
    </article>
  );
}

/** The study area's harmonized month to date against the same days of earlier years (meta.current, by rank). */
const monthLine = (lang: Lang, m: NonNullable<NonNullable<PlaceRisk["built_area"]>["month"]>) => {
  const more = m.value >= m.median;
  return T[lang].month(more, num(more ? m.higher_than : m.rank - 1, lang), num(m.n_prior, lang));
};

/** The sentences read aloud and put in the report email; every number from the two API answers. */
function summary(lang: Lang, x: Target, farm: Farm, fire: PlaceRisk | null) {
  const t = T[lang], p = farm.place!, r = fire?.recent, end = lang === "bn" ? "।" : ".", out: string[] = [];
  if (!p.covered) out.push(p.in_bangladesh ? t.noData : t.outside);
  else {
    out.push(`${x.name} · ${t.kilns}: ${num(p.within_1km!, lang)} ${t.in1}, ${num(p.within_3km!, lang)} ${t.in3}${p.nearest_km! <= 3 ? `, ${t.nearest} ${dist(p.nearest_km!, lang)}` : ""}${end}`);
    if (p.within_3km && p.pm25_t_yr_3km != null && p.so2_t_yr_3km != null) out.push(`${t.smoke}: ${t.tons(num(p.pm25_t_yr_3km, lang), num(p.so2_t_yr_3km, lang))}${end}`);
  }
  if (r) out.push(`${t.fire}: ${r.count ? `${t.fire5(num(r.count, lang))}, ${t.fireNear(dist(r.nearest_km!, lang))}` : t.fire0}${end}`);
  if (fire?.built_area?.month) out.push(monthLine(lang, fire.built_area.month));
  return out;
}

/** A link that reopens this exact check. */
const placeLink = (x: Target) => `${location.origin}${location.pathname}#pg=bangladesh&at=${x.lat},${x.lon}&n=${encodeURIComponent(x.name)}`;

function mailto(lang: Lang, x: Target, say: string[]) {
  const t = T[lang];
  const body = [
    ...say, "",
    `${x.name} (${x.lat}, ${x.lon})`, `https://www.openstreetmap.org/?mlat=${x.lat}&mlon=${x.lon}#map=15/${x.lat}/${x.lon}`,
    new Date().toLocaleDateString(lang === "bn" ? "bn-BD" : "en-GB", { day: "numeric", month: "long", year: "numeric" }), "",
    lang === "bn" ? "ছবি: (যোগ করুন)" : "Photos: (attach)", "",
    `${t.src}: Kiln Watch ${placeLink(x)} · APAD (CC BY 4.0) · NASA FIRMS`,
  ].join("\n");
  return `mailto:?subject=${encodeURIComponent(`${t.report}: ${x.name}`)}&body=${encodeURIComponent(body)}`;
}

/** 3.5 km around the field, drawn without a base map so it loads on a weak connection and prints. */
function LocalMap({ lang, x, kilns, fires }: { lang: Lang; x: Target; kilns: { lat: number; lon: number }[]; fires: { lat: number; lon: number }[] }) {
  const W = 320, c = W / 2, s = c / 3.5;
  const px = (lat: number, lon: number) => [c + (lon - x.lon) * 111.32 * Math.cos((x.lat * Math.PI) / 180) * s, c - (lat - x.lat) * 111.32 * s];
  const inBox = ([a, b]: number[]) => a >= 0 && a <= W && b >= 0 && b <= W;
  const km = lang === "bn" ? "কিমি" : "km";
  return (
    <svg viewBox={`0 0 ${W} ${W}`} className="fk-map" role="img"
      aria-label={lang === "bn" ? `মাঝে আপনার জমি, ${num(kilns.length, lang)}টি ইটভাটা, ${num(fires.length, lang)}টি আগুন` : `Your field in the middle, ${kilns.length} kilns, ${fires.length} fire spots`}>
      <rect width={W} height={W} rx={10} className="fk-map-bg" />
      {[1, 3].map((r) => <g key={r}>
        <circle cx={c} cy={c} r={r * s} fill="none" stroke={YOU} strokeWidth={1.5} strokeDasharray="5 4" opacity={0.8} />
        <text x={c + 4} y={c - r * s - 5} className="fk-map-t">{num(r, lang)} {km}</text>
      </g>)}
      {fires.map((f) => px(f.lat, f.lon)).filter(inBox).map(([a, b], i) => <g key={`f${i}`}><circle cx={a} cy={b} r={11} fill={FIRE} opacity={0.2} /><circle cx={a} cy={b} r={5} fill={FIRE} stroke="#FFE1A8" strokeWidth={1.5} /></g>)}
      {kilns.map((k) => px(k.lat, k.lon)).filter(inBox).map(([a, b], i) => <rect key={`k${i}`} x={a - 5} y={b - 5} width={10} height={10} rx={2} fill={KILN} stroke="#030508" strokeWidth={1} />)}
      <circle cx={c} cy={c} r={8} fill={YOU} stroke="#fff" strokeWidth={3} />
      <text x={W - 18} y={24} className="fk-map-n" textAnchor="middle">{lang === "bn" ? "উ" : "N"}</text>
      <path d={`M${W - 18} 30l-6 12h12z`} className="fk-map-arrow" />
      <g className="fk-map-key" transform={`translate(10 ${W - 14})`}>
        <circle r={5} cx={5} cy={0} fill={YOU} /><text x={14} y={4}>{lang === "bn" ? "আপনি" : "You"}</text>
        <rect x={62} y={-5} width={10} height={10} rx={2} fill={KILN} /><text x={77} y={4}>{lang === "bn" ? "ইটভাটা" : "Kiln"}</text>
        <circle r={5} cx={140} cy={0} fill={FIRE} /><text x={149} y={4}>{lang === "bn" ? "আগুন" : "Fire"}</text>
      </g>
    </svg>
  );
}

/** Boro stages, the local fire months (MODIS 2003-2025) and the kiln season (night lights) on one 12-month strip. */
function Boro({ lang, season, kilnMonths, fireNow }: { lang: Lang; season: PlaceRisk["season"]; kilnMonths: number[] | null; fireNow: boolean }) {
  const t = T[lang];
  const now = new Date().getMonth();
  const yrs = season ? season.last_year - season.first_year + 1 : 0;
  const hf = HARVEST.map((m) => season?.by_month[m - 1]?.years_with_fire ?? 0);
  return (
    <section className="pr-sec fk-boro" aria-label={t.boro}>
      <h3><span aria-hidden>🌾</span> {t.boro}</h3>
      {fireNow && HARVEST.includes(now + 1) && <p className="pr-err">{t.harvestNow}</p>}
      {/* All 12 months in a row on wide screens; two blocks of six on a phone, where Bangla month names need the room. */}
      {[[0, 12, "fk-wide"], [0, 6, "fk-half"], [6, 12, "fk-half"]].map(([a, b, cls]) => {
        const ms = MON[lang].map((m, i) => [m, i] as const).slice(a as number, b as number);
        return (
          <div className={`fk-year ${cls}`} role="table" key={`${a}-${b}`} style={{ ["--n" as string]: ms.length }}>
            <div role="row" className="fk-yrow fk-yhead"><span role="columnheader" />{ms.map(([m, i]) => <span role="columnheader" key={m} className={i === now ? "now" : ""}>{m}</span>)}</div>
            <div role="row" className="fk-yrow">
              <span role="rowheader"><i aria-hidden>🌾</i> {t.rBoro}</span>
              {ms.map(([m, i]) => { const st = BORO[i + 1]; return <span role="cell" key={m} className={`fk-bc ${st ?? ""}`}>{st ? t.stage[st] : ""}</span>; })}
            </div>
            {season && <div role="row" className="fk-yrow">
              <span role="rowheader"><i aria-hidden>🔥</i> {t.rFire}</span>
              {ms.map(([m, i]) => {
                const bm = season.by_month[i];
                const sh = bm.record_years ? bm.years_with_fire / bm.record_years : 0;
                return <span role="cell" key={m} className="fk-fc" style={{ ["--a" as string]: 0.08 + 0.92 * sh }} title={`${bm.years_with_fire} / ${bm.record_years}`}>{num(bm.years_with_fire, lang)}</span>;
              })}
            </div>}
            {kilnMonths && <div role="row" className="fk-yrow">
              <span role="rowheader"><i aria-hidden>🧱</i> {t.rKiln}</span>
              {ms.map(([m, i]) => <span role="cell" key={m} className={`fk-kc ${kilnMonths.includes(i + 1) ? "on" : ""}`}>{kilnMonths.includes(i + 1) ? "●" : ""}</span>)}
            </div>}
          </div>
        );
      })}
      {season && <p className="fk-say">{t.harvestFire(num(hf[0], lang), num(hf[1], lang), num(yrs, lang))}{Math.max(...hf) > 0 && <> {t.harvestTip}</>}</p>}
      {season && <p className="muted small">{t.key(num(yrs, lang))}</p>}
    </section>
  );
}

function Nation({ lang, d, onPick }: { lang: Lang; d: Farm; onPick: (lat: number, lon: number) => void }) {
  const t = T[lang];
  const rings = d.boundary?.rings ?? [];
  const all = rings.flat();
  const w = Math.min(...all.map((p) => p[0])), e = Math.max(...all.map((p) => p[0]));
  const s = Math.min(...all.map((p) => p[1])), n = Math.max(...all.map((p) => p[1]));
  const W = 420, k = Math.cos((((s + n) / 2) * Math.PI) / 180), H = Math.round((W * (n - s)) / ((e - w) * k));
  const x = (lon: number) => ((lon - w) / (e - w)) * W, y = (lat: number) => ((n - lat) / (n - s)) * H;
  const cl = d.cropland, inv = d.inventory;
  const click = (ev: React.MouseEvent<SVGSVGElement>) => {
    const r = ev.currentTarget.getBoundingClientRect();
    onPick(+(n - ((ev.clientY - r.top) / r.height) * (n - s)).toFixed(5), +(w + ((ev.clientX - r.left) / r.width) * (e - w)).toFixed(5));
  };
  return (
    <section className="pr-sec fk-nation" aria-label={t.nation}>
      <h3>{t.nation}</h3>
      <div className="fk-npair">
        <svg viewBox={`0 0 ${W} ${H}`} className="fk-nmap" onClick={click} role="img"
          aria-label={lang === "bn" ? `বাংলাদেশের মানচিত্রে ${num(inv.n, lang)}টি ইটভাটা` : `Map of Bangladesh with ${inv.n} brick kilns`}>
          {rings.map((r, i) => <path key={i} d={"M" + r.map((p) => `${x(p[0]).toFixed(1)} ${y(p[1]).toFixed(1)}`).join("L") + "Z"} className="fk-land" />)}
          <line x1={x(inv.east_edge_lon)} x2={x(inv.east_edge_lon)} y1={0} y2={H} className="fk-edge" />
          {(d.kilns ?? []).map((q, i) => <circle key={i} cx={x(q[1])} cy={y(q[0])} r={1.4} fill={q[2] != null && q[2] >= 50 ? KILN : "#8B95A3"} opacity={0.85} />)}
        </svg>
        <div className="fk-nstats">
          <div className="pr-tile"><span>{t.nKilns}</span><b>{num(inv.n, lang)}</b></div>
          <div className="pr-tile"><span>{t.nCrop}</span><b>{num((100 * cl.kilns_with_half_or_more) / cl.kilns_measured, lang)}%</b><small>{t.nCropS}</small></div>
          {d.emissions && <div className="pr-tile"><span>{t.nSmoke}</span><b>{num(d.emissions.pm25_total, lang)}</b><small>{t.nSmokeS}</small></div>}
          <p className="muted small">{t.nKey}</p>
        </div>
      </div>
    </section>
  );
}
