# Claim Story AI — Implementation Plan

Hackathon project: multi-agent Member & Claims Intelligence system using the Google Agent Development Kit (GADK / google-adk). Shifts a health-plan call center from reactive explanation to proactive prevention and self-service transparency.

This document is a planning input for Claude Code. Read fully before scaffolding. Open questions are flagged at the bottom — resolve those with me before implementing the affected sections.

---

## 1. Goal & success criteria

Build a demoable system where one orchestrator routes caller interactions to four specialist agents sharing a single session context:

1. **Claim Story Agent** — turns denial codes into a plain-language "claim story" timeline with required actions and estimated resolution time.
2. **Benefits Q&A Agent** — answers CPT lookups, prior-auth requirements, and cost-sharing questions via RAG.
3. **ROI Gatekeeper Agent** — pre-screens every session: detects callers acting on behalf of adult members without a Release of Information on file; routes/flags before a human agent is involved.
4. **Sentinel Agent** — async monitor consuming events from the other agents; surfaces compliance/ops risk to a dashboard.

Judged success metrics (simulate these): Average Handle Time reduction, First Call Resolution increase, repeat-contact rate decrease, preventable denials caught before final rejection. Log per-interaction metrics so a before/after panel can be shown.

## 2. Architecture summary

```
Caller (demo UI / CLI)
        │
        ▼
Orchestrator (GADK root agent)
  - intent classification
  - owns SessionContext (shared, mutable, passed to every agent)
  - runs ROI Gatekeeper first on every session, then routes
        │
   ┌────┼──────────┬─────────────┐
   ▼    ▼          ▼             │ (async events)
Claim  Benefits   ROI            ▼
Story  Q&A       Gatekeeper   Sentinel
   │    │          │             │
   ▼    ▼          ▼             ▼
Claims  Benefits  Member/ROI   Ops dashboard
data    KB (RAG)  records      (alerts, metrics)
(mock)  (vector)  (mock)
```

Key decisions (already made — do not relitigate unless blocked):

- **Shared session context, not agent-to-agent messaging.** One `SessionContext` object owned by the orchestrator. Agents are stateless and swappable.
- **Sentinel is an event consumer, not a poller, and never sits in the request path.** Agents fire-and-forget structured events to an in-process event log (simple append-only list or queue for the hackathon; framed as "Kafka topic in production").
- **All external data mocked behind clean interfaces.** Protocol classes (`ClaimsClient`, `MemberRecordsClient`, `BenefitsKB`) backed by JSON fixtures. Production swap = one class per integration.
- **ROI Gatekeeper runs first, always.** Its finding is written into `SessionContext` and downstream agents read it.

## 3. Tech stack

- Python 3.12+ (use whatever GADK supports; prefer modern syntax — `list[]`, `|` unions)
- `google-adk` (Agent Development Kit) — orchestrator + agents; confirm current package name/APIs at implementation time
- Pydantic v2 for all data models (claims, events, session context, agent outputs)
- Vector store for RAG: start with an in-memory option (e.g., chromadb or FAISS) for hackathon speed; keep behind a `BenefitsKB` protocol so pgvector is a drop-in later
- LLM: whatever model GADK wires to by default (Gemini); keep model IDs in config
- Demo UI: pick ONE — (a) simple Streamlit chat + dashboard tabs, or (b) CLI chat + Streamlit dashboard. Optimize for demo reliability over polish
- Config: single `settings.py` using `pydantic-settings` `BaseSettings`, singleton instance, `self.settings = settings or Settings()` pattern for test injection

## 4. Proposed repo structure

```
claim-story-ai/
├── README.md
├── pyproject.toml
├── data/
│   ├── claims.json              # mock claims w/ denial codes
│   ├── members.json             # members, relationships, ROI status
│   ├── denial_codes.json        # code → cause → required action → est. resolution
│   └── benefits_docs/           # markdown/text docs for RAG ingestion
├── src/
│   ├── settings.py
│   ├── models/                  # Pydantic: Claim, Member, DenialCode,
│   │                            #   SessionContext, AgentEvent, ClaimStory
│   ├── clients/                 # ClaimsClient, MemberRecordsClient protocols
│   │   └── mock/                #   + JSON-fixture implementations
│   ├── kb/                      # BenefitsKB protocol, ingestion, retrieval
│   ├── events/                  # EventLog (append-only), event schemas
│   ├── agents/
│   │   ├── orchestrator.py
│   │   ├── claim_story.py
│   │   ├── benefits_qa.py
│   │   ├── roi_gatekeeper.py
│   │   └── sentinel.py
│   ├── metrics/                 # simulated AHT/FCR logging
│   └── ui/                      # streamlit app (chat + dashboard)
└── tests/
```

## 5. Data models (draft — refine during implementation)

- `Member`: id, name, dob, plan_id, relationships (list of member ids + relation type), roi_authorizations (list of {authorized_caller_id, scope, expires})
- `Claim`: id, member_id, cpt_codes, provider, dates, status, denial_codes, history (list of status transitions w/ timestamps)
- `DenialCode`: code, cause_category (missing_referral | incorrect_modifier | cpt_mismatch | eligibility_timing), plain_language_cause, required_action, est_resolution_days
- `SessionContext`: session_id, caller_identity, subject_member_id, roi_status (verified | missing | not_required), intent_history, agent_findings (dict keyed by agent), metrics (start_time, turns)
- `AgentEvent`: timestamp, session_id, agent, event_type, payload — event_types include: denial_explained, roi_gap_detected, coverage_question_answered, escalation_triggered
- `ClaimStory`: claim_id, timeline (list of {date, event, explanation}), required_actions, est_resolution, confidence

## 6. Implementation phases

### Phase 0 — Scaffold (do first, keep tiny)
- pyproject, settings, repo layout, empty protocols
- Mock data fixtures: ~10 members (include at least 2 spouse/adult-dependent pairs with and without ROI), ~15 claims covering all four denial cause categories, denial code table
- Smoke test: load fixtures, validate against Pydantic models

### Phase 1 — Vertical slice: Claim Story Agent
Highest demo value; do end-to-end before anything else.
- `ClaimsClient` mock → fetch claim by member
- Denial code mapping → structured `ClaimStory` (LLM generates the plain-language narrative from structured inputs; the code/cause/action mapping is deterministic from `denial_codes.json`, NOT hallucinated)
- Emit `denial_explained` event
- Minimal CLI to invoke it directly
- Checkpoint: raw denial JSON in → readable claim story out

### Phase 2 — Orchestrator + ROI Gatekeeper
- GADK root agent with intent classification (claim_inquiry | benefits_question | other)
- `SessionContext` creation and threading
- ROI Gatekeeper: caller vs. subject-member check → roi_status written to context → `roi_gap_detected` event when missing → response instructs self-service ROI submission path (mock)
- Downstream agents refuse/limit detail when roi_status == missing (this is the compliance story — make it visible in the demo)

### Phase 3 — Benefits Q&A Agent
- Ingest `benefits_docs/` into vector store (chunking: langchain-text-splitters is fine)
- Retrieval → grounded answer with source snippet references
- Cover: CPT lookup, prior-auth requirement, cost-sharing question
- Emit `coverage_question_answered` event

### Phase 4 — Sentinel + dashboard
- Sentinel consumes EventLog on interval (or on-write callback)
- Aggregations: denial spikes by cause category, ROI-gap frequency, repeat-session detection (same member, same claim, <N days)
- Streamlit dashboard tab: alert feed + metric tiles (simulated AHT/FCR before vs. after)

### Phase 5 — Demo hardening
- One scripted golden-path scenario touching all four agents: spouse calls about denied claim → ROI check flags gap → ROI resolved (mock) → claim story delivered → follow-up coverage question → Sentinel dashboard shows the denial-spike alert
- Seed data so the golden path is deterministic; record fallback screenshots/video
- README with run instructions + architecture diagram

## 7. Demo script (target)

1. Show dashboard baseline (Sentinel quiet).
2. Spouse calls about member's denied claim → Gatekeeper detects no ROI → proactive self-service path shown.
3. ROI resolved → Claim Story renders the timeline: what happened, why, action, ETA.
4. Caller asks "is a follow-up visit covered?" → Benefits Q&A answers with sources, no human agent needed.
5. Cut to dashboard: denial spike alert + before/after AHT/FCR tiles.

## 8. Guardrails & constraints

- No real PHI anywhere — all data synthetic.
- LLM never invents denial causes, coverage rules, or resolution times; those come from structured fixtures/RAG. LLM's job is narration and intent handling only. State this in the pitch (accuracy/trust concern).
- Every agent output that reaches a member includes what it was grounded on (claim id, doc snippet).
- Keep GADK usage idiomatic — check current ADK docs for agent/sub-agent/tool patterns before writing orchestration code; don't guess APIs.

## 9. Open questions (resolve before/while implementing)

1. GADK specifics: current package name, orchestration pattern (sub_agents vs. agent-as-tool), session/state primitives — verify against live docs.
2. Demo UI choice: Streamlit chat vs. CLI chat (dashboard is Streamlit either way).
3. Vector store for hackathon: chromadb vs. FAISS vs. just pgvector-in-docker (team familiarity favors pgvector, speed favors in-memory).
4. Team split: which phases parallelize? (Phase 1 and Phase 3 are independent after Phase 0.)
5. Metrics simulation approach: hardcoded before-baseline vs. computed from a scripted "manual process" run.

### Things to consider:

1. Your architecture is mostly reactive, but your pitch says "proactive prevention." Close that gap. The problem statement's headline is "reactive explanation → proactive prevention," and the creativity rubric explicitly rewards "denial prevention" and "compliance risk prediction." But your four agents are Claim Story (explains an existing denial), Benefits Q&A (answers questions), ROI Gatekeeper (checks a caller), and Sentinel (aggregates spikes after they happen). None of them predicts an individual denial before it becomes final. That's the single most defensible "proactive" feature available to you, and it's also the one Round 2 item you're currently missing — risk scoring. Round 2 lists the AI methods it wants to see: RAG (you have it), classification (intent — you have it), summarization (claim story — you have it), risk scoring (missing), agent routing (you have it), confidence thresholds (weak, see below), structured outputs (you have it). A small Denial-Risk agent that scores pending/adjudicated-but-not-final claims for denial likelihood — even rule-based over your denial_codes.json features to start, framed as "classifier in production" — fills the risk-scoring hole and makes the proactive story true instead of aspirational. If you don't add it, at least reframe the pitch honestly around "proactive transparency + self-service" rather than "prevention," because a sharp judge will notice the mismatch.
2. Metrics are your Round 2 make-or-break, and open question #5 shows you know it's soft. "Hardcoded before-baseline" will read as hand-waving to judges scoring "meaningful metrics that connect to the value of the solution." You don't need real data, but you need a defensible model: state an assumption set (baseline AHT in minutes, probability a preventable denial generates a repeat call, cost of one 30–60 day reprocessing cycle), then compute the delta your system produces per interaction and aggregate it. "Each prevented denial removes ~N calls and one reprocessing cycle → AHT −X%, FCR +Y%" with a visible assumptions box beats any hardcoded number. Log per-interaction so the before/after panel is computed from the golden-path run, not typed in.
3. Make confidence thresholds real, not a Pydantic field. Right now ClaimStory.confidence is a number with no described mechanism. Round 2 names "confidence thresholds" as a wanted method, and it's nearly free to make it real: if a denial code isn't in your fixture table, or RAG retrieval score is below a cutoff, the agent declines and routes to a human instead of guessing. Show that handoff happening once in the demo — it's a trust story and it hits the rubric item simultaneously.
4. On GADK specifics (your open question #1) — I checked current docs. First, naming: it's just "Agent Development Kit (ADK)"; the package is google-adk, imports are from google.adk.agents import LlmAgent with Runner and InMemorySessionService. The core classes are Agent/LlmAgent (defines instructions, tools, behavior) and workflow agents that orchestrate. The more important design point: ADK gives you two very different delegation mechanisms, and your plan implicitly assumes one that fights your own design. Medium

sub_agents (description-driven transfer): when the root agent hands off to a sub-agent, responsibility for answering is completely transferred and the root is effectively out of the loop. That breaks your "orchestrator owns SessionContext and runs ROI Gatekeeper first, always, then routes, then maybe comes back" model. Google Cloud
AgentTool (agent-as-tool): a sub-agent is a permanent org-chart employee, whereas an AgentTool is like an external consultant you call for specific expertise — the orchestrator stays in control. This matches your design far better. Google Cloud
Workflow agents: a SequentialAgent runs its sub_agents one after another in order, which is the clean idiomatic way to encode "ROI Gatekeeper → router" as a guaranteed-first step. Google

So: implement the "ROI-first, orchestrator-retains-control" flow as a SequentialAgent (ROI gate → routing) and/or expose the specialists as AgentTools, not as description-transfer sub_agents. Second: ADK already has shared session state — a shared whiteboard where an agent writes results other agents read. Your SessionContext is reinventing this; back it with ADK's native session state (serialize your Pydantic model into tool_context.state) so you're idiomatic rather than threading a custom object around and confusing the framework. One caveat — ADK 2.0 is current and introduced graph-based workflow changes, so pin your version and skim the 2.0 migration notes before scaffolding. Google CloudAdk
5. Smaller notes. (a) "ROI Gatekeeper runs first, always" adds friction when the caller is asking about their own plan — there's no subject-member to gate. Make it conditional: gate only when subject_member_id != caller_identity. (b) Scope: five phases, four agents, RAG, Sentinel, and a dashboard is a lot; Sentinel's spike-detection over synthetic data is your least convincing and most cuttable piece — if you're time-boxed, that compute is better spent on the Denial-Risk agent from point 1, which serves the same "use case 4 / compliance risk" box more impressively. (c) Demo reliability: stub or cache the LLM responses for the golden path so a live API hiccup can't sink the demo — your fallback-video instinct is right, but a cached golden path means you rarely need it. (d) Cheap proactive-UX win: render the actual SMS/portal message the member would receive before calling ("Your MRI claim needs a referral — tap to request"). It makes "proactive, minimal friction" visible for almost no code and directly serves the UX rubric.
Quick hits on your other open questions: UI — CLI chat + Streamlit dashboard is the more demo-reliable choice (fewer moving parts than a Streamlit chat widget). Vector store — go in-memory (Chroma or FAISS) behind your BenefitsKB protocol; pgvector-in-docker is a reliability liability on demo day and your protocol already makes it a later swap, so team familiarity shouldn't win here. Parallelization — Phase 1 (Claim Story) and Phase 3 (Benefits Q&A) are cleanly independent after Phase 0, so split there; whoever takes the Denial-Risk agent can also start right after Phase 0 since it only needs the claims fixtures.
Want me to draft the ADK orchestrator skeleton (SequentialAgent gate + AgentTool specialists, session-state-backed) in Python, or sketch the revised architecture with the Denial-Risk agent added as a diagram?

