# Benefits Q&A Agent

Answers coverage, prior-authorization, and cost questions in plain language,
grounded in `datasets/coverage_rules.csv`. **No coverage fact is ever produced by
the model.**

## Run it

```bash
cd src/backend
uv sync
uv run pytest                      # 47 tests, no network, <1s
uv run python -m benefits.dev_cli --demo
uv run python -m benefits.dev_cli --member MBR00183 --json "colonoscopy"
```

The CLI and the whole deterministic core run with **no API key and no network**.
Only `benefits.agent` needs Gemini, and that runs in the GADK environment
(`.env.example` lists the variables it expects).

## The design in one line

Coverage is a dict lookup over a total 20×4 grid, so the LLM is a *presentation*
layer, not a reasoning layer. `answer.py` produces the complete four-part answer
— covered, prior auth, cost, next step — before any model is involved. The agent
re-narrates and translates it; it adds no facts.

Consequence worth knowing: **the LLM is the most cuttable component here, not the
least.** If Gemini is down on demo day, `dev_cli.py` still gives correct,
grounded answers.

## For the orchestrator owner

Import the agent and wrap it as a tool — *not* as a description-transfer
`sub_agent`, which would hand off the turn and take you out of the loop:

```python
from google.adk.tools.agent_tool import AgentTool
from benefits import benefits_agent

AgentTool(agent=benefits_agent)
```

Everything at the seam is a constant in `contract.py` (which imports nothing, so
it's safe to import from anywhere):

| Session-state key | Direction | Notes |
|---|---|---|
| `subject_member_id` | read | required; the tools ignore any member the model names |
| `roi_status` | read | see below |
| `caller_name` | read | ROI is per `(member_id, caller_name)` |
| `session_id` | read | stamped onto events |
| `agent_findings["benefits_qa"]` | write | the full structured answer |

**`roi_status` fails closed.** Only `verified` and `not_required` unlock
member-specific detail. Anything else — including **`expired`**, which is 43 rows
in `roi_authorizations.csv` — gets the ROI self-service refusal. Please don't
model this as a two-state verified/missing flag; expired auth would read as
verified.

## For the UI

`BenefitsAnswer.model_dump_json()` is the card. Every factual field is assembled
from the CSV, so it never passes through the model:

```json
{
  "answer_text": "...",
  "resolution": "resolved",
  "covered": true,
  "prior_auth_required": true,
  "cost": {"copay": 0, "cost_share_pct": 20, "basis": "coinsurance_only",
           "estimate_text": "No copay. You pay 20% of the allowed amount.",
           "dollar_total": null,
           "dollar_total_reason": "The allowed amount is not known until..."},
  "next_step": "...",
  "providers": [{"name": "...", "specialty": "...", "city": "...", "phone": "...", "is_pcp": true}],
  "grounded_on": ["RULE0070"],
  "plan_type": "MAPD",
  "cpt_code": "45378",
  "language": "Spanish",
  "choices": []
}
```

Two fields need real UI treatment:

- **`resolution: "ambiguous"`** → render `choices` as buttons. This is a normal
  path, not an error (see below).
- **`cost.dollar_total` is always `null`** by design — render `estimate_text`, and
  use `dollar_total_reason` as the tooltip. Never sum copay and coinsurance.

## Why some of this looks the way it does

Each of these is forced by the data, and each is load-bearing:

- **Ambiguity is a correctness path, not a UX nicety.** For a DSNP member,
  "depression screening" means both 96127 (**covered**) and G0444 (**not
  covered**) — opposite answers from one phrase, and the polarity *inverts* on
  PPO. Picking one silently is a coin flip on telling a member a non-covered
  service is free. So we ask.
- **A not-covered service is never described as `$0`.** All 8 not-covered rows
  carry `copay=0, cost_share_pct=0`, so `cost.py` branches on `covered` before it
  reads a money field.
- **No dollar total, ever.** copay and coinsurance are both non-zero on 43 of 80
  rules, and the allowed amount doesn't exist until adjudication.
- **No distances.** `lat/lon` disagree with `city/state` and the median nearest
  eligible provider is 217 miles away, so mileage would be false precision.
- **No fuzzy matching.** Over 20 fixed codes there's no ground truth to tune a
  threshold against — difflib matches "colonoscopy" to "Total Knee Arthroplasty"
  at any cutoff loose enough to catch real paraphrases. `aliases.py` is a hand
  map, which also lets ambiguity be *declared* rather than discovered.
- **`claims.csv` is never read for coverage.** 50/880 claims disagree with
  `coverage_rules` on prior-auth and 99 exist for services the plan doesn't
  cover; mixing them would let the agent contradict itself mid-session.

## Emitted events

Appended to `benefits.events.EVENT_LOG` (fire-and-forget, never in the request
path):

- `coverage_question_answered` — `{session_id, member_id, cpt_code,
  matched_rule_id, plan_type, match_type, answered_in_language}`
- `network_gap_detected` — when an in-network specialty has **nobody accepting new
  patients** (true today for Gastroenterology and Oncology). That's a
  network-adequacy compliance finding for Sentinel.

## Golden path

`MBR00183` — Natalie Chang, MAPD, Spanish. Denied colonoscopy claim `CLM000804`
→ `RULE0070`: covered, prior auth required, 20% coinsurance, $0 copay,
in-network required. Gastroenterology has no providers accepting new patients, so
it falls back to her PCP, **Dr. Jason Perry** — who is in-network and accepting,
and whose referral is the required first step for a colonoscopy anyway.
