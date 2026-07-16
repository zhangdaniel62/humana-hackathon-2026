# Frontend & Voice Architecture Plan

Follow-up to [initial_plan.md](initial_plan.md). Covers two decisions and their
implementation: (1) how the frontend talks to the backend — FastAPI, not Flask —
and (2) how a caller speaks to the AI agent and hears its answer.

Status: the backend half of this plan is **implemented and verified** (see
"What exists today" below). The frontend half is the plan.

---

## 1. Decision: FastAPI, not Flask

We do not hand-roll endpoints in Flask. The ADK ships its own FastAPI
integration — `google.adk.cli.fast_api.get_fast_api_app()` — which generates
the agent-serving surface for us:

- `POST /run`, `POST /run_sse` — invoke an agent app (SSE variant streams)
- Session CRUD endpoints (`/apps/{app}/users/{user}/sessions/...`)
- `GET /list-apps`, plus the ADK dev UI at `/` (`web=True`)

Reasons over Flask: async-native (required for WebSocket voice and SSE
streaming), request/response validation straight from our existing Pydantic v2
models, and the ADK endpoints come for free. Custom routes (voice WebSocket,
future manager/dashboard APIs) are mounted on the same app.

## 2. Voice call flow (browser mic → live agent → spoken reply)

```
Browser mic ──PCM16 @16 kHz──► /ws/voice ──► LiveRequestQueue ──► Gemini Live
   ▲                          (FastAPI WS)        (ADK run_live)  (native audio)
   │                                                                   │
   └───────◄── PCM16 @24 kHz audio + transcript JSON ◄─────────────────┘
```

No separate STT/TTS services: ADK's `Runner.run_live()` drives a Gemini Live
native-audio model that accepts caller audio and produces spoken audio
directly. The voice layer is a thin adapter — the same root agent and tools
serve text chat (`/run_sse`) and voice (`/ws/voice`), so the golden-path demo
can fall back to text if audio misbehaves.

### WebSocket wire protocol (`/ws/voice`)

| Direction | Frame | Meaning |
|---|---|---|
| browser → server | binary | raw 16-bit PCM mono mic audio, 16 kHz |
| browser → server | text JSON `{"type":"text","text":...}` | typed fallback input |
| server → browser | binary | raw 16-bit PCM mono agent audio, 24 kHz |
| server → browser | text JSON `{"type":"user_transcript"\|"agent_transcript","text":...}` | live transcripts |
| server → browser | text JSON `{"type":"interrupted"}` | caller barged in — stop playback immediately |
| server → browser | text JSON `{"type":"turn_complete"}` | agent finished its turn |

### Agent topology

- `voice_orchestrator` (root; live model on voice, text model on chat — same
  factory, `model_name` override) — greets the caller, confirms claim IDs,
  speaks plainly; **never invents claim facts**.
- It calls the deterministic `lookup_claim_story` FunctionTool (backed by
  `ClaimStoryService` → BigQuery) and narrates from its exact JSON result.
- The structured `claim_story_agent` uses `mode='chat'` because ADK 2.4 runs
  agents wrapped by `AgentTool` through a child Runner, which accepts only chat
  roots. `include_contents='none'` preserves isolated, one-request behavior.
- The live voice orchestrator still calls the deterministic
  `lookup_claim_story` FunctionTool directly. This avoids making the live model
  wait for a second LLM pass before it can narrate the grounded result.

### Model availability (verified 2026-07-16 against our Vertex project)

- **Live/voice:** the only live-capable model this qwiklabs project can
  connect to is `gemini-live-2.5-flash-native-audio`, and only in
  `us-central1`. Rejected: `gemini-live-2.5-flash`,
  `gemini-2.0-flash-live-preview-04-09`, every Gemini 3.5 live spelling, and
  plain `gemini-3.5-flash` over a live connection.
- **Text:** `gemini-3.5-flash` is not served in `us-central1`, has no quota
  in `global` (persistent 429), but **works with quota in the `us`
  multi-region**. The live model 503s in `us`, so the two models need
  different locations. Solution: `GOOGLE_CLOUD_LOCATION=us` +
  `MODEL_NAME=gemini-3.5-flash` for text, while the voice agent pins its own
  client to `LIVE_MODEL_LOCATION=us-central1` via ADK's
  `Gemini(client_kwargs={"location": ...})`. Fallback if `us` misbehaves:
  `gemini-2.5-flash` works in `us-central1`.

## 3. What exists today (backend, verified end-to-end)

```
backend/
├── main.py                     # get_fast_api_app + voice router + /demo static mount
├── agents/claim_assist/agent.py  # ADK app: root_agent for /run, /run_sse, dev UI
├── src/
│   ├── agents/orchestrator.py  # create_voice_orchestrator() — live root agent
│   ├── agents/claim_story.py   # grounded claim-story specialist (pre-existing)
│   ├── api/voice.py            # /ws/voice bridge: browser audio ↔ run_live
│   └── settings.py             # + live_model_name, live_voice_name; exports .env
└── static/index.html           # browser-mic demo page at /demo
```

Run from `backend/`: `uv run uvicorn main:app --reload`, then open
`http://127.0.0.1:8000/demo/`. Verified: WS handshake, typed turn → ~3 s of
spoken audio back, tests green (`uv run python -m unittest discover -s tests`).

Gotcha fixed along the way: `pydantic-settings` reads `.env` privately, but
google-genai inside ADK reads `GOOGLE_GENAI_USE_VERTEXAI` / project / location
from `os.environ` — `settings.py` now calls `load_dotenv()` so both see it.

## 4. Frontend plan (two audiences, one backend)

Single React (Vite) app in `src/frontend` with two routes; both talk to the
same FastAPI server:

- **Caller/agent view** (`/call`): "Call the AI" button using the `/ws/voice`
  protocol above (port the working JS from `backend/static/index.html`), live
  transcript pane, and the structured claim-story card rendered from
  `claim_story.result` session state.
- **Manager view** (`/dashboard`): alert feed + metric tiles (AHT/FCR
  before/after, denial spikes, ROI-gap counts). Needs small new REST
  endpoints (`/api/events`, `/api/metrics`) once the event log from the
  initial plan exists — mount them next to the voice router in `src/api/`.

The `/demo` static page stays as the zero-dependency fallback demo.

## 5. Production path (out of hackathon scope)

Swap the browser-mic adapter for a Twilio Media Streams adapter: Twilio
answers the PSTN call and streams 8 kHz μ-law audio over a WebSocket; the
adapter transcodes to 16 kHz PCM into the same `LiveRequestQueue`. Agents,
tools, and session logic are unchanged — that is the point of keeping the
voice layer thin.

## 6. Next steps

1. Scaffold the React frontend (`/call` + `/dashboard` routes).
2. Add the event log + `/api/events`, `/api/metrics` endpoints (Sentinel feed).
3. Attach Benefits Q&A and ROI Gatekeeper as additional AgentTools on the
   orchestrator.
4. Cache/stub the golden-path responses for demo-day reliability.
