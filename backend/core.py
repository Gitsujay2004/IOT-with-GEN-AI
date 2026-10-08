"""Backend core (Wi-Fi version): readings arrive over HTTP from the ESP32. No servo, no camera."""
import os
import re
import threading
import time
from collections import deque
from pathlib import Path

import pyttsx3
from dotenv import load_dotenv

from ollama_service import client as ai

load_dotenv(Path(__file__).parent / ".env")

DANGER_CM = int(os.getenv("DANGER_CM", "50"))
VERY_CLOSE_CM = int(os.getenv("VERY_CLOSE_CM", "20"))
REALERT_SEC = int(os.getenv("REALERT_SEC", "10"))
CLEAR_CONFIRM = int(os.getenv("CLEAR_CONFIRM_READINGS", "3"))
DEVICE_TIMEOUT_SEC = int(os.getenv("DEVICE_TIMEOUT_SEC", "3"))
AUTOSTART = os.getenv("AUTOSTART", "false").lower() == "true"

CLOSE_CM = int(os.getenv("CLOSE_CM", "35"))     # "close" band ceiling
NAME_MAX = 20
_NAME_BAD = re.compile(r"[^A-Za-z0-9 .,'\-]")

_lock = threading.RLock()
_tts_lock = threading.Lock()
_s = {"running": False, "state": "STOPPED", "distance": None, "last_seen": 0.0,
      "spoken": "", "history": deque(maxlen=5), "band": None, "last_alert": 0.0,
      "clear_count": 0, "busy": False,
      "settings": {"volume": float(os.getenv("DEFAULT_VOLUME", "0.8")), "name": ""}}


def level_for(d):
    """Distance level used for the prompt and the fallback templates."""
    if d <= VERY_CLOSE_CM:
        return "very_close"
    if d <= CLOSE_CM:
        return "close"
    return "approaching"


def get_name():
    with _lock:
        return _s["settings"]["name"]


def set_name(name):
    """Store the user name: trimmed, max 20 chars, letters/numbers/spaces/basic punctuation."""
    clean = _NAME_BAD.sub("", str(name or "").strip())[:NAME_MAX].strip()
    with _lock:
        _s["settings"]["name"] = clean
    return clean


def warmup():
    ai.warmup()


def _speak(text, log=True):
    with _lock:
        if log:
            _s["spoken"] = text
            _s["history"].appendleft({"time": time.strftime("%H:%M:%S"), "text": text})
        vol = _s["settings"]["volume"]

    def run():
        with _tts_lock:
            try:
                e = pyttsx3.init()
                e.setProperty("volume", vol)
                e.say(text)
                e.runAndWait()
            except Exception as ex:
                print("[tts] error:", ex)
    threading.Thread(target=run, daemon=True).start()


def _alert_worker(dist, band):
    try:
        msg = ai.make_alert_message(dist, band, get_name())
        with _lock:
            if not _s["running"] or _s["state"] != "DANGER":
                return                       # object already left / system stopped
            _speak(msg)
    finally:
        with _lock:
            _s["busy"] = False


def update_distance(d):
    """Called for every Wi-Fi reading from the ESP32."""
    with _lock:
        _s["last_seen"] = time.time()
        _s["distance"] = d
        if not _s["running"]:
            return
        if d <= DANGER_CM:
            band = "very_close" if d <= VERY_CLOSE_CM else "danger"
            first = _s["state"] != "DANGER"
            changed = band != _s["band"]
            now = time.time()
            _s["state"], _s["clear_count"] = "DANGER", 0
            due = first or (changed and band == "very_close") or now - _s["last_alert"] > REALERT_SEC
            if due and not _s["busy"]:
                _s["last_alert"], _s["band"], _s["busy"] = now, band, True
                threading.Thread(target=_alert_worker, args=(d, band), daemon=True).start()
        elif _s["state"] == "DANGER":
            _s["clear_count"] += 1
            if _s["clear_count"] >= CLEAR_CONFIRM:
                _s["state"], _s["band"], _s["last_alert"] = "CLEAR", None, 0.0
                name = _s["settings"]["name"]
                _speak(f"No object detected, {name}. Move straight." if name
                       else "No object detected. Move straight.")
        else:
            _s["state"] = "CLEAR"


def start():
    with _lock:
        _s.update(running=True, state="CLEAR", band=None, last_alert=0.0, clear_count=0)
        name = _s["settings"]["name"]
        _speak(f"System started. Hello {name}, path is clear. Move straight." if name
               else "System started. Path is clear. Move straight.")


def stop():
    with _lock:
        _s.update(running=False, state="STOPPED", band=None, clear_count=0)


def get_state():
    with _lock:
        online = time.time() - _s["last_seen"] < DEVICE_TIMEOUT_SEC
        return {"running": _s["running"], "state": _s["state"],
                "distance_cm": _s["distance"] if online else None,
                "device_online": online, "spoken_message": _s["spoken"],
                "history": list(_s["history"]), "settings": dict(_s["settings"]),
                "user_name": _s["settings"]["name"],
                "danger_cm": DANGER_CM, "very_close_cm": VERY_CLOSE_CM, "busy": _s["busy"]}


def repeat_last():
    """Speak the last message again: no LLM call and no duplicate history entry."""
    with _lock:
        msg = _s["spoken"]
    if not msg:
        msg = "There is no message to repeat."
        _speak(msg)
        return {"repeated": False, "message": msg}
    _speak(msg, log=False)
    return {"repeated": True, "message": msg}
