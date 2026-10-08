# Smart Obstacle Alert (Wi-Fi)

A Wi-Fi assistive device that helps blind people walk safely: an ESP32 with an HC-SR04
ultrasonic sensor measures the distance straight ahead, sends it to a FastAPI backend on a
PC over Wi-Fi, and the backend speaks an English voice alert when an object is too close.

## Features

- **Real-time distance** – live centimetre value from the ESP32, refreshed every 300 ms on the dashboard.
- **Two danger zones** – a *danger* zone (`DANGER_CM`, default 50 cm) and a *very close* zone (`VERY_CLOSE_CM`, default 20 cm).
- **English voice alerts** – offline text-to-speech with `pyttsx3`; danger messages are written by a local Ollama LLM with a built-in fallback sentence.
- **Repeat button** – speaks the last message again without calling the LLM or adding a history entry.
- **START / STOP control** – one big button; when stopped, no distance reading produces speech.
- **Last messages** – the 5 most recent spoken messages with timestamps.
- **ESP32 online/offline status** – the device is shown as *offline* if no reading arrives for 3 seconds.

## How it works

The ESP32 measures the distance and pushes it to the backend. The backend decides whether
the object is inside a danger zone and speaks a message. The dashboard only *reads* the
state; it never sends distances.

```mermaid
flowchart LR
    A[HC-SR04 sensor] --> B[ESP32<br/>sample + send every 250 ms]
    B -- POST /api/sensor {"distance":35} --> C[FastAPI backend<br/>backend/core.py]
    C --> D{Danger zone?}
    D -- yes --> E[Ollama LLM<br/>writes alert sentence]
    E --> F[pyttsx3<br/>English voice]
    D -- no --> G[State = CLEAR]
    F --> H[(State + history)]
    G --> H
    I[React dashboard] -- GET /api/state every 300 ms --> H
    J[START / STOP / Repeat buttons] -- POST /api/start|stop|repeat --> C
```

In short:

```
ESP32  --HTTP POST /api/sensor-->  backend  --speaks-->  speaker
                                        ^
React dashboard  --GET /api/state-------|
```

Key behaviour:

- The ESP32 takes the **median of 3 samples** and sends a reading every **250 ms**.
- Readings of **2 cm or less** (glitch) or **more than 200 cm** (out of range) are sent as **999**, which the dashboard shows as *Clear*.
- A danger alert is spoken when the state changes to DANGER, when the band becomes *very_close*, or every `REALERT_SEC` seconds while the object stays.
- The state returns to CLEAR only after `CLEAR_CONFIRM_READINGS` consecutive clear readings, then the backend says *"No object detected. Move straight."*
- While the LLM is writing a message, the dashboard shows **Analyzing...** (`busy: true`).

## Hardware

| Item | Notes |
| --- | --- |
| ESP32 Dev Module | 30-pin board, Arduino IDE target **ESP32 Dev Module** |
| HC-SR04 ultrasonic sensor | Fixed in front of the user, measures straight ahead |
| 1 kΩ and 2 kΩ resistors | Voltage divider on the ECHO line |
| Jumper wires + USB cable | For programming and power |

### Wiring

| HC-SR04 pin | Connect to | Note |
| --- | --- | --- |
| `VCC` | ESP32 `5V` | |
| `GND` | ESP32 `GND` | |
| `TRIG` | ESP32 `GPIO 5` | Output |
| `ECHO` | ESP32 `GPIO 19` | **via 1 kΩ / 2 kΩ divider** – the sensor's 5 V echo must be reduced to 3.3 V |

Divider: `ECHO → 1 kΩ → GPIO 19`, and `2 kΩ` from `GPIO 19` to `GND`.

## Tech stack

| Layer | Technology |
| --- | --- |
| Device | ESP32, Arduino framework (C++), built-in `WiFi.h` + `HTTPClient.h` |
| Backend | Python 3.12, FastAPI, uvicorn |
| Voice | pyttsx3 (offline OS speech, SAPI5 on Windows) |
| Messages | Ollama local LLM (`ollama` Python client) + static fallback sentence |
| Config | python-dotenv (`.env` files per package) |
| Dashboard | React 18 + Vite 5 |

## Project structure

```
obstacle_alert/
├── api/
│   ├── main.py            # FastAPI app: all HTTP routes, CORS, uvicorn startup
│   └── .env               # API host/port and allowed CORS origins
├── backend/
│   ├── core.py            # State, danger logic, pyttsx3 voice, message history
│   └── .env               # Danger thresholds, timers, volume, autostart
├── ollama_service/
│   ├── client.py          # Ollama chat client, alert prompt, fallback message
│   └── .env               # Ollama host, model name, timeout, keep-alive
├── frontend/
│   ├── src/
│   │   ├── main.jsx       # React entry point + error boundary
│   │   ├── App.jsx        # Dashboard: distance ring, START/STOP, Repeat, history
│   │   └── App.css        # Styling, zone colours, pulsing danger banner
│   ├── index.html         # Vite HTML entry
│   ├── vite.config.js     # React plugin, dev server on port 5173
│   ├── package.json       # npm scripts and dependencies
│   └── .env               # Backend URL, polling interval, max distance for the ring
├── arduino/
│   └── obstacle_wifi/
│       └── obstacle_wifi.ino   # ESP32 sketch: measure, filter, POST reading
├── requirements.txt       # Python dependencies
└── README.md
```

`myenv/`, `node_modules/`, `__pycache__/` and `frontend/dist/` are generated and can be
deleted and recreated at any time.

## Setup and run (Windows / PowerShell)

### 1. Backend

```powershell
cd <path-to>\obstacle_alert
py -3.12 -m venv myenv
.\myenv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m api.main
```

The API listens on `http://0.0.0.0:8000`. Check it with:

```powershell
curl http://127.0.0.1:8000/api/health
```

### 2. Frontend

```powershell
cd <path-to>\obstacle_alert\frontend
npm install
npm run dev
```

Open <http://localhost:5173>. For a production bundle use `npm run build` (output in
`frontend/dist/`).

### 3. ESP32

1. Open `arduino/obstacle_wifi/obstacle_wifi.ino` in Arduino IDE.
2. **TODO – the whole sketch body is currently inside a `/* ... */` block comment.
   Remove the `/*` and `*/` markers around the code before uploading.**
3. Install the ESP32 board package (Board Manager → *esp32 by Espressif Systems*).
4. Set the three constants at the top of the file:

   ```cpp
   const char* WIFI_SSID  = "YOUR_WIFI_NAME";
   const char* WIFI_PASS  = "YOUR_WIFI_PASSWORD";
   const char* SERVER_URL = "http://192.168.1.100:8000/api/sensor";  // your PC IP
   ```

5. Find your PC's IP address with `ipconfig` (look for *IPv4 Address* on the Wi-Fi adapter) and
   use it in `SERVER_URL`.
6. Select **ESP32 Dev Module** and upload. Open the Serial Monitor at **115200 baud**; you
   should see the Wi-Fi IP and a `distance=... HTTP=200` line about 4 times per second.

### 4. Ollama (used for the alert wording)

```powershell
winget install Ollama.Ollama      # if Ollama is not installed yet
ollama serve
ollama pull llama3.2:1b
```

`LLM_MODEL` in `ollama_service/.env` must match the pulled model. If Ollama is not running or
the model fails, the backend prints `[ollama] llm error: ...` and uses the built-in fallback
sentence, so the device keeps working without the LLM.

## Configuration

Environment variables are read with `python-dotenv` from the `.env` file next to each package.

### `api/.env`

| Variable | Default | Meaning |
| --- | --- | --- |
| `API_HOST` | `0.0.0.0` | Interface uvicorn binds to. `0.0.0.0` lets the ESP32 and other devices connect. |
| `API_PORT` | `8000` | TCP port of the API. Must match `SERVER_URL` in the sketch. |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins for the dashboard, e.g. `http://localhost:5173,http://127.0.0.1:5173`. |

### `backend/.env`

| Variable | Default | Meaning |
| --- | --- | --- |
| `DANGER_CM` | `50` | Distance (cm) at which an object counts as a danger. |
| `VERY_CLOSE_CM` | `20` | Distance (cm) below which the alert is treated as urgent. |
| `REALERT_SEC` | `10` | Minimum seconds between two alerts while the object stays in the zone. |
| `CLEAR_CONFIRM_READINGS` | `3` | Consecutive clear readings needed to switch back to CLEAR. |
| `DEVICE_TIMEOUT_SEC` | `3` | Seconds without a reading before the ESP32 is shown as offline. |
| `DEFAULT_VOLUME` | `0.8` | Speech volume (0.0–1.0) used by pyttsx3. |
| `AUTOSTART` | `false` | Set to `true` to start listening automatically when the API starts. |

### `ollama_service/.env`

| Variable | Default | Meaning |
| --- | --- | --- |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server address. |
| `LLM_MODEL` | `llama3` (code default) | Model used to write the alert sentence. The `.env` file ships `llama3.2:1b`. |
| `LLM_TIMEOUT_SEC` | `4` | Timeout in seconds for one LLM request before the fallback sentence is used. |
| `KEEP_ALIVE` | `30m` | How long Ollama keeps the model loaded in memory. |

### `frontend/.env`

| Variable | Default | Meaning |
| --- | --- | --- |
| `VITE_API_URL` | `http://127.0.0.1:8000` | Backend base URL used by the dashboard. Use the PC IP to view the dashboard from a phone. |
| `VITE_POLL_MS` | `300` | Polling interval for `/api/state` in milliseconds. |
| `VITE_MAX_CM` | `200` | Distance (cm) that corresponds to 0 % on the proximity ring. |

Note: `DANGER_CM`, `VERY_CLOSE_CM` and the volume are sent to the dashboard inside
`/api/state`, so the UI always matches the backend.

## API reference

| Method | Route | Request body | Response example |
| --- | --- | --- | --- |
| `GET` | `/api/health` | – | `{"status": "ok"}` |
| `POST` | `/api/sensor` | `{"distance": 35}` (int, cm; `999` = clear path) | `{"ok": true}` |
| `GET` | `/api/state` | – | see below |
| `POST` | `/api/start` | – | `{"running": true}` |
| `POST` | `/api/stop` | – | `{"running": false}` |
| `POST` | `/api/repeat` | – | `{"repeated": true, "message": "Careful! Obstacle 30 centimeters ahead..."}` |

Interactive docs are available at <http://127.0.0.1:8000/docs>.

`GET /api/state` response:

```json
{
  "running": true,
  "state": "DANGER",
  "distance_cm": 35,
  "device_online": true,
  "spoken_message": "Careful! Obstacle 35 centimeters ahead. Please stop and turn left or right.",
  "history": [{ "time": "14:32:07", "text": "Careful! Obstacle 35 centimeters ahead..." }],
  "settings": { "volume": 0.8 },
  "danger_cm": 50,
  "very_close_cm": 20,
  "busy": false
}
```

- `state` is `STOPPED`, `CLEAR` or `DANGER`.
- `distance_cm` becomes `null` when the device is offline.
- `busy` is `true` while the LLM is writing a message.
- `history` holds at most the 5 newest messages, newest first.
- `POST /api/repeat` answers `{"repeated": false, "message": "There is no message to repeat."}`
  when nothing has been spoken yet.

## Troubleshooting

**ESP32 prints `Wi-Fi failed, will retry...`**

- The ESP32 only supports **2.4 GHz** Wi-Fi. It cannot connect to a 5 GHz-only network.
- The SSID and password are **case-sensitive**.
- On a phone hotspot, enable maximum compatibility mode (2.4 GHz, WPA2).

**ESP32 prints `HTTP=-1 (connection refused)`**

- The PC IP in `SERVER_URL` is wrong or has changed. Run `ipconfig` again after reconnecting
  to Wi-Fi.
- Windows Firewall blocks port 8000. Open it once as Administrator:

  ```powershell
  netsh advfirewall firewall add rule name="ObstacleAlert API" dir=in action=allow protocol=TCP localport=8000
  ```

- The ESP32 and the PC must be on the same network (same router, no guest/isolated network).
- Test from a phone on the same Wi-Fi: open `http://<PC-IP>:8000/api/health`. If that fails,
  the problem is the network or the firewall, not the sketch.

**Dashboard shows `Backend offline. Start FastAPI on ...`**

- Start the backend with `python -m api.main` from the project root.
- Check that `VITE_API_URL` in `frontend/.env` points at a URL the browser can reach. If the
  dashboard runs on another device, use the PC IP, not `127.0.0.1`.
- Restart Vite after editing `.env` – Vite only reads environment files at start-up.
- If the browser console shows a CORS error, add the dashboard origin to `CORS_ORIGINS` in
  `api/.env`.

**No voice is heard**

- Check the Windows sound output and volume; `DEFAULT_VOLUME` in `backend/.env` controls the
  speech level (0.0–1.0).
- Look at the backend console: `[tts] error: ...` means pyttsx3 failed, often because no
  speech engine or voice is installed.
- Verify the available voices in Python:

  ```powershell
  python -c "import pyttsx3; e=pyttsx3.init(); print([v.name for v in e.getProperty('voices')])"
  ```

- Make sure only one speech runs at a time – `pyttsx3` speaks in a background thread guarded by
  a lock, so a long message can delay the next one.

**Ollama: `model not found` or `failed to allocate buffer`**

- Pull a smaller model and set it in `ollama_service/.env`:

  ```powershell
  ollama pull llama3.2:1b
  ```

  then set `LLM_MODEL=llama3.2:1b`.
- `failed to allocate buffer` usually means the model does not fit in RAM or VRAM – use the
  smallest model available.
- These errors are not fatal: `backend/core.py` falls back to a fixed sentence so alerts keep
  working.

## Safety note

This project is a **helper**, not a safety device. It only measures straight ahead with one
ultrasonic sensor and cannot detect walls to the side, steps, moving people or low obstacles.
It must never be the only aid a blind person relies on. Test the setup carefully, keep a guide
dog, cane or companion available, and follow local accessibility and product-safety rules.

## Future improvements

- Add the LLM's suggested turn direction ("left" / "right") to the spoken message and drive a
  vibration or buzzer on the ESP32.
- Two sensors (left and right) so the system can tell which side is free.
- Battery operation on the ESP32 with a low-battery alert.
- Store readings in a database and draw a simple history chart.
- Configurable thresholds and volume from the dashboard instead of `.env` files.
- Configurable language for the voice alerts.

## License

TODO – add a license (for example MIT) before sharing the project publicly.