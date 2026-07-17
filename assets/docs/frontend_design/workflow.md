# Workflow

How each persona moves through the product. The three journeys connect at
one hinge point — the handoff from AI to rep — and all three feed the same
underlying session data.

## Member

| Stage | What happens |
|---|---|
| Initiates contact | Starts a session by voice or text, immediately — no queue wait. |
| AI gathers context | AI doesn't have everything up front. It asks for what it's missing and routes the question internally to the right specialist (claim lookup, benefits, ROI check) as the conversation goes. |
| **Resolved** | Once grounded, the AI has a confident answer. Member gets it in plain language. Session ends. |
| **ROI gap** | AI detects the caller isn't authorized for the member in question. Explains the requirement, discloses nothing restricted, offers the authorization next step. |
| **Escalation needed** | AI can't ground a confident answer (low confidence, ambiguous, out of scope). Member is told they're being connected to a rep; the session carries over, not restarted. |

## Rep

| Stage | What happens |
|---|---|
| Watching the queue | Idle until the AI hands off a session. Queue order is first in, first served — not ranked by urgency. |
| Pickup | Claims a handed-off session. This opens automatically as its own tab; a rep can hold more than one concurrent interaction and switch between them. |
| Inherits context | Sees what the member asked, what the AI already found, and why it escalated — not a cold call. |
| Resolves | Works the conversation directly with the member, in whatever medium they used. The tab closes automatically when the member leaves — the interaction then stays in the queue as a completed entry, not a separate history page. |

## Manager

| Stage | What happens |
|---|---|
| Passive monitoring | Dashboard tracks the four numbers that define success as sessions complete: Average Handle Time, First Call Resolution, repeat contact rate, and preventable denials reaching final rejection. |
| Notices a signal | One of those metrics moves the wrong way, or a specific claim is flagged as at risk of a preventable denial. |
| Drills in | Inspects the evidence behind the flag: which claims, which pattern, how often. |
| Acts | The tool surfaces the signal; follow-up (process fix, outreach) happens outside it. Visibility is the value, not in-app resolution. |
