import { useState } from "react";
import { api } from "../api";
import { PageHead, PageProps } from "./shared";

const KINDS: [string, string][] = [
  ["question", "A question about the method or the data"], ["suggestion", "Something we could add"],
  ["bug", "Something looks wrong"], ["data", "A place, dataset or fire we should look at"], ["other", "Anything else"],
];
const ISSUES = "https://github.com/Aalvee-Aarham/nasaspaceappschallenge-2026-team-off-the-binary/issues/new";

export default function Contact({ online }: PageProps) {
  const [f, setF] = useState({ kind: "question", name: "", email: "", message: "", website: "" });
  const [state, setState] = useState<"idle" | "busy" | "done">("idle");
  const [err, setErr] = useState<string | null>(null);
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });

  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null); setState("busy");
    try {
      await api.feedback({ ...f, page: location.hash.slice(1, 61) });
      setState("done");
    } catch (ex) {
      setErr((ex as Error).message); setState("idle");
    }
  };

  return (
    <>
      <PageHead kicker="Contact" title="Ask us, or tell us what to add"
        lead="A question we have not answered, a limitation we missed, a place to build, or something that looks wrong. Every message is read by the team." />
      <section className="contact">
        {state === "done" ? (
          <div>
            <p><b>Thank you, your message has reached us.</b> {f.email ? "If it needs an answer, we will write back to the address you gave." : "You left no email, so we cannot reply directly."}</p>
            <button className="btn ghost" onClick={() => { setF({ ...f, message: "" }); setState("idle"); }}>Send another</button>
          </div>
        ) : (
          <form onSubmit={send}>
            <label className="field">What is it about?
              <select value={f.kind} onChange={set("kind")}>{KINDS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
            </label>
            <label className="field">Message
              <textarea required minLength={10} maxLength={5000} rows={7} value={f.message} onChange={set("message")}
                placeholder="For example: does the Aqua scale hold for peat fires in Indonesia?" />
            </label>
            <div className="coord-grid">
              <label>Name (optional)<input value={f.name} onChange={set("name")} maxLength={120} autoComplete="name" /></label>
              <label>Email (optional, for a reply)<input type="email" value={f.email} onChange={set("email")} maxLength={254} autoComplete="email" /></label>
            </div>
            {/* Honeypot: hidden from people and screen readers, filled only by bots */}
            <input className="hp" tabIndex={-1} autoComplete="off" aria-hidden="true" value={f.website} onChange={set("website")} />
            {err && <p className="error small" role="alert">{err}</p>}
            {!online && <p className="warn small">The Kiln Watch server is not answering, so the form cannot send right now.</p>}
            <button className="btn" disabled={state === "busy" || !online || f.message.trim().length < 10}>{state === "busy" ? "Sending…" : "Send"}</button>
          </form>
        )}
        <p className="muted small">Your name and email are used only to answer you and are never published. Prefer it in the open? <a href={ISSUES} target="_blank" rel="noreferrer">Open a GitHub issue</a>.</p>
      </section>
    </>
  );
}
