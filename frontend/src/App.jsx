import { useEffect, useLayoutEffect, useRef, useState } from "react";
import "./App.css";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
const POLL = Number(import.meta.env.VITE_POLL_MS || 300);
const MAX_CM = Number(import.meta.env.VITE_MAX_CM || 200);

const EMPTY = {
  running: false, state: "STOPPED", distance_cm: null, device_online: false,
  spoken_message: "", history: [], busy: false, danger_cm: 50, very_close_cm: 20,
  settings: { volume: 0.8 }, user_name: "",
};
const ICON = { STOPPED: "⏸️", CLEAR: "✅", DANGER: "🚨" };
const NAME_KEY = "obstacleAlertName";

function readName() {
  try { return (localStorage.getItem(NAME_KEY) || "").trim(); } catch { return ""; }
}
function writeName(n) {
  try { localStorage.setItem(NAME_KEY, n); } catch { /* storage blocked, ignore */ }
}

function zoneColor(d, s) {
  if (d == null || d >= 999) return "#2ee59d";
  if (d <= s.very_close_cm) return "#ff2e63";
  if (d <= s.danger_cm) return "#ff9f1c";
  if (d <= s.danger_cm * 2) return "#ffd60a";
  return "#2ee59d";
}

/* Long spoken messages stay collapsed to `lines` lines with a "..." tail.
   Click, Enter or Space expands them. Used in the banner and in the history list. */
function ExpandableText({ text, lines = 2, className = "", banner = false }) {
  const el = useRef(null);
  const [open, setOpen] = useState(false);
  const [box, setBox] = useState({ clipped: false, full: 0, collapsed: 0 });

  // every new message starts collapsed again
  const [lastText, setLastText] = useState(text);
  if (lastText !== text) { setLastText(text); setOpen(false); }

  // measure the natural height while collapsed (only then is the clamp active)
  useLayoutEffect(() => {
    const node = el.current;
    if (!node || open) return;
    const measure = () => {
      const collapsed = node.clientHeight;
      const full = node.scrollHeight;
      setBox({ clipped: full > collapsed + 1, full, collapsed });
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [text, open]);

  const toggle = () => setOpen((o) => !o);
  const onKey = (e) => {
    if (e.key === "Enter" || e.key === " " || e.key === "Spacebar") {
      e.preventDefault();               // Space must not scroll the page
      toggle();
    }
  };

  const style = { "--ex-lines": lines };
  if (!banner && box.collapsed > 0) {
    style.maxHeight = open ? box.full : box.collapsed;
  }

  return (
    <span className={`ex ${open ? "open" : ""} ${banner ? "ex-banner" : ""} ${className}`}>
      <span className="ex-body" role="button" tabIndex={0} aria-expanded={open}
        onClick={toggle} onKeyDown={onKey}>
        <span ref={el} className="ex-text" style={style}>{text}</span>
        {box.clipped && <span className="ex-hint">{open ? "Show less" : "Tap to read more"}</span>}
      </span>
    </span>
  );
}

export default function App() {
  const [s, setS] = useState(EMPTY);
  const [offline, setOffline] = useState(false);
  const [busyBtn, setBusyBtn] = useState(false);
  const [nameInput, setNameInput] = useState("");
  const [userName, setUserName] = useState("");
  const [nameFlash, setNameFlash] = useState(false);

  const refresh = async () => {
    try {
      const r = await fetch(API + "/api/state");
      setS({ ...EMPTY, ...(await r.json()) });
      setOffline(false);
    } catch { setOffline(true); }
  };
  useEffect(() => { refresh(); const t = setInterval(refresh, POLL); return () => clearInterval(t); }, []);

  const post = (path, body) => fetch(API + path, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });

  // on page load: restore the saved name and hand it to the backend
  useEffect(() => {
    const n = readName();
    if (!n) return;
    setNameInput(n);
    setUserName(n);
    post("/api/name", { name: n }).catch(() => {});
  }, []);

  const saveName = async () => {
    const n = nameInput.trim().slice(0, 20);
    setNameInput(n);
    writeName(n);
    setUserName(n);
    setNameFlash(true);
    setTimeout(() => setNameFlash(false), 1800);
    try { await post("/api/name", { name: n }); await refresh(); } catch {}
  };

  const toggle = async () => {
    setBusyBtn(true);
    try { await post(s.running ? "/api/stop" : "/api/start"); await refresh(); } catch {}
    setBusyBtn(false);
  };
  const repeat = async () => {
    try { await post("/api/repeat"); await refresh(); } catch {}
  };

  const d = s.distance_cm;
  const color = zoneColor(d, s);
  const savedName = userName || s.user_name || "";
  const prox = d == null || d >= 999 ? 0 : Math.round((1 - Math.min(d, MAX_CM) / MAX_CM) * 100);
  const distText = !s.running || d == null ? "—" : d >= 999 ? "Clear" : `${d} cm`;
  const message = !s.running ? "System is off. Press START." : s.busy ? "Analyzing..." :
    s.spoken_message || "Silent. Path is clear.";

  return (
    <div className={`app st-${s.state}`}>
      {offline && <div className="offline">Backend offline. Start FastAPI on {API}</div>}

      <header>
        <h1>🦯 Smart Obstacle Alert</h1>
        <div className="chips">
          <span className={`chip ${s.device_online ? "on" : "off"}`}>
            📡 ESP32 {s.device_online ? "online" : "offline"}
          </span>
          <span className="chip">🔊 {Math.round(s.settings.volume * 100)}%</span>
        </div>
      </header>

      <section className="banner" aria-live="assertive">
        <div className="badge">{ICON[s.state]} {s.state}</div>
        <p className="message"><ExpandableText text={message} lines={3} banner /></p>
      </section>

      <main className="grid">
        <div className="card center">
          <h2>Distance ahead</h2>
          <div className="ring" style={{ background: `conic-gradient(${color} ${prox * 3.6}deg, rgba(255,255,255,.15) 0)` }}>
            <div className="ring-in"><span style={{ color }}>{distText}</span></div>
          </div>
          <p className="muted">Danger zone: {s.danger_cm} cm</p>
        </div>

        <div className="card center">
          <h2>Control</h2>
          <button className={`power ${s.running ? "stop" : "start"}`} onClick={toggle} disabled={busyBtn}>
            {busyBtn ? "..." : s.running ? "⏹ STOP" : "▶ START"}
          </button>
          <div className="row">
            <button className="btn blue" disabled={!s.running} onClick={repeat}>🔁 Repeat</button>
          </div>
        </div>

        <form className="card" onSubmit={(e) => { e.preventDefault(); saveName(); }}>
          <h2>Your name</h2>
          <div className="row">
            <input
              className="name-input"
              value={nameInput}
              onChange={(e) => setNameInput(e.target.value.slice(0, 20))}
              placeholder="Enter your name"
              maxLength={20}
              aria-label="Your name"
              autoComplete="given-name"
            />
            <button className="btn blue save" type="submit" disabled={nameInput.trim() === savedName}>
              Save
            </button>
          </div>
          <p className="muted">
            {nameFlash && savedName ? `Saved. Hello, ${savedName}!`
              : savedName ? `Hello, ${savedName} — your voice alerts use this name.`
                : "Saved in this browser and used inside the voice alerts."}
          </p>
        </form>

        <div className="card history-card">
          <h2>Last messages</h2>
          <div className="history-wrap">
            <ul className="history">
              {s.history.length === 0 && <li className="muted">No messages yet</li>}
              {s.history.map((h, i) => (
                <li key={i} style={{ borderLeftColor: ["#38bdf8", "#a78bfa", "#f472b6", "#fbbf24", "#34d399"][i % 5] }}>
                  <small>{h.time}</small>
                  <ExpandableText text={h.text} lines={2} />
                </li>
              ))}
            </ul>
          </div>
        </div>
      </main>
    </div>
  );
}
