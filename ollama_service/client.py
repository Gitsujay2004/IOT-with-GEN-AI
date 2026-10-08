import os
from pathlib import Path

import ollama
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

LLM_MODEL = os.getenv("LLM_MODEL", "llama3")
KEEP_ALIVE = os.getenv("KEEP_ALIVE", "30m")
_client = ollama.Client(host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
                        timeout=float(os.getenv("LLM_TIMEOUT_SEC", "4")))


def _chat(prompt, **kw):
    r = _client.chat(model=LLM_MODEL, keep_alive=KEEP_ALIVE,
                     messages=[{"role": "user", "content": prompt}], **kw)
    return r["message"]["content"].strip()


def warmup():
    try:
        _chat("Say OK")
        print("[ollama] model warmed up")
    except Exception as e:
        print("[ollama] warmup failed:", e)

def fallback_message(dist, band, name=""):
    who = f"{name}, " if name else ""
    if band == "very_close":
        return f"{who}Stop! Object detected {dist} centimeters ahead. Please wait."
    return f"{who}Object detected {dist} centimeters ahead. Please stop and wait."


def make_alert_message(dist, band, name=""):
    urgency = "VERY CLOSE, be urgent" if band == "very_close" else "close"
    name_rule = (
        f"The person's name is {name}. Use the name {name} in the sentence naturally. "
        "Do not put the name in quotation marks.\n"
        if name else ""
    )
    prompt = (
        "You are a friendly voice assistant for a blind person walking.\n"
        f"Fact: an obstacle is straight ahead at {dist} cm ({urgency}). "
        "The sensor cannot tell which side is free.\n"
        f"{name_rule}"
        "Write ONE or TWO very short spoken sentences: include the distance in centimeters, "
        "tell them to stop or slow down and turn carefully left or right. "
        "No emojis, no extra text.\n"
        'Example: "Careful! Obstacle 30 centimeters ahead. Please stop and turn left or right."'
    )
    try:
        return _chat(prompt) or fallback_message(dist, band, name)
    except Exception as e:
        print("[ollama] llm error:", e)
        return fallback_message(dist, band, name)