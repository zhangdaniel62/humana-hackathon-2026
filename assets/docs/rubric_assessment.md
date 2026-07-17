# Claim Assist rubric assessment

This is a candid repository-based assessment against the supplied Humana
Military hackathon rubric. It is not a prediction from the organizers. The
point estimates below assume a clear seven-minute presentation and a working
deterministic fallback. Actual advancement depends on the field, judge
weighting, cut line, presentation execution, and whether live integrations work
in the judging environment.

## How to read the assessment

- **Current** means the code and presentation assets present in this checkout.
- **Rating-5 gates complete** means Features 12–16 in
  `assets/docs/overall_plan.md` are implemented, reviewed, tested, stable, and
  demonstrated with their required evidence. Merely adding breadth without
  evidence or reliability does not earn the projected score.
- Repository evidence is separated from assumptions. Synthetic operations data
  demonstrates calculation and presentation paths; it is not evidence that
  Humana outcomes improved.
- Round 1 is the relevant rubric for the advancement decision. Round 2 scores
  are included to show how competitive the solution would be after advancing.

## Executive assessment

| Scenario | Round 1 point estimate | Plausible judged range | Round 2 readiness estimate | Plausible judged range |
|---|---:|---:|---:|---:|
| Current | **15/20** | **14–17** | **14/20** | **13–15** |
| Rating-5 gates implemented well | **19/20** | **18–20** | **18/20** | **17–19** |

The current entry is technically strong enough to be a credible Round 2
candidate, but its largest judging risk is that much of the product experience
is still exposed through backend-oriented fallback pages and APIs. Completing
the rating-5 gates would improve judge-visible usability, evaluated AI quality,
multi-agent execution, proactive workflow depth, and runtime credibility. They
would not by themselves prove real operational impact.

## Round 1 scoring

### Current repository

| Category | Score | Confidence | Evidence and rationale |
|---|---:|---|---|
| Problem Understanding | **4/5** | High | The plan maps members, representatives, providers, supervisors, and operations users to concrete pain points. The implementation directly addresses claim explanation, benefits, ROI gaps, readiness, repeat contacts, AHT, FCR, and corrective interventions. Metric definitions explicitly distinguish mature seven-day cohorts and avoid claiming that an intervention prevented a denial. A 5 would require an even tighter presentation of root-cause prioritization and credible outcome validation, not only synthetic trends. |
| Technical Ambition / Difficulty | **4/5** | High | The repository combines Google ADK, a live chat/voice WebSocket, deterministic grounded tools, BigQuery/CSV adapters, shared session context, ROI controls, structured summaries, role-based authentication, async Sentinel events, and persisted SQLite analytics. The active caller path is primarily one ADK root `LlmAgent` invoking specialist tools; specialist agent modules exist, but the live workflow is not yet exceptional multi-agent orchestration. Local SQLite and in-memory runtime state also cap the score below 5. |
| Creativity and Innovation | **4/5** | Medium | Proactive claim readiness, ROI pre-screening, grounded notification previews, corrective-intervention events, and operational risk monitoring go beyond a generic chatbot. The workflow is inventive and proactive, but several headline capabilities closely follow the challenge prompt, and there is no validated predictive model or demonstrated final-adjudication prevention loop. |
| Presentation and Collaboration | **3/5** | Low | There is a timed presentation plan, fixed-ID golden path, deterministic fallback, saved dashboard artifact, static voice demo, operations page, and a detailed frontend handoff. However, the role-specific product frontend is pending, the current operations page does not render the new trend dashboard, and presentation owners are placeholders. Collaboration quality cannot be established from repository evidence alone. |

**Current Round 1 point estimate: 15/20. Plausible judged range: 14–17.**

### If all rating-5 gates are implemented well

| Category | Score | Confidence | Why it moves |
|---|---:|---|---|
| Problem Understanding | **5/5** | Medium | The versioned evaluation corpus, explicit root-cause cases, reviewed readiness evidence, quality/safety thresholds, and closed-loop queue would tie workflow constraints directly to measurable outcomes. The score still depends on clearly separating synthetic evidence from real impact. |
| Technical Ambition / Difficulty | **5/5** | Medium | Explicit ADK specialist delegation, typed handoffs, evaluated routing, trace evidence, durable adapters, restart-safe scanning, and complete role-specific experiences would form a difficult, defensible end-to-end system. This assumes the scope remains modular and stable. |
| Creativity and Innovation | **5/5** | Medium | Population scanning that creates prioritized, evidence-backed rep work items and traces them through grounded intervention would demonstrate a differentiated proactive loop beyond a standard chatbot. |
| Presentation and Collaboration | **4/5** | Low | A responsive role-specific product, evaluation results, agent traces, and one coherent prevention workflow would make the story far easier to demonstrate. A 5 cannot be projected from implementation alone; it requires excellent rehearsal, seamless role handoffs, explicit tradeoffs, and visible team collaboration. |

**Rating-5-gates Round 1 point estimate: 19/20. Plausible judged range: 18–20.**

## Round 2 scoring

### Current repository

| Category | Score | Confidence | Evidence and rationale |
|---|---:|---|---|
| Solution Impact and Effectiveness | **3/5** | High | The system addresses all four target metric areas and demonstrates transparent calculations using labeled synthetic data. It shows credible potential, not measured improvement in real workflow conditions. There is no linked final adjudication outcome and therefore no demonstrated preventable-denial reduction. |
| Initial AI Approach | **4/5** | High | The approach is grounded and responsible: deterministic domain services, typed outputs, exact-record lookup, ambiguity handling, ROI fail-closed behavior, claim-ID confirmation, safe escalation, and LLM narration through ADK. A 5 would benefit from explicit quality evaluation, retrieval/routing evaluation, calibrated confidence evidence, and stronger demonstrated multi-agent execution. |
| User Experience | **3/5** | High | Plain-language agent instructions, transcripts, safe next steps, structured summaries, a legacy Voice validation page, and an operations view support the primary workflow. The missing first-class role-specific Chat/Voice frontend, help queue, manager trend charts, and polished state handling prevent a 4. |
| Feasibility / Reusability / Scalability | **4/5** | High | The code has modular services, Pydantic contracts, repository adapters, fallback data sources, server-side RBAC, deterministic seeds, and a passing automated suite. The current SQLite auth/analytics database, in-memory sessions/events, local credentials, and missing production integrations are appropriate hackathon boundaries but not enterprise-ready scale. |

**Current Round 2 readiness estimate: 14/20. Plausible judged range: 13–15.**

### If all rating-5 gates are implemented well

| Category | Score | Confidence | Why it moves |
|---|---:|---|---|
| Solution Impact and Effectiveness | **4/5** | Medium | Population scanning and the closed-loop queue would increase actionable workflow coverage, while the frontend would make it operationally usable. It remains a 4 until real or controlled outcome evidence demonstrates improvement. |
| Initial AI Approach | **5/5** | Medium | Versioned evaluation, explicit specialist delegation, typed handoffs, grounded deterministic services, safety thresholds, and trace evidence would combine multiple appropriate methods with auditable controls. |
| User Experience | **5/5** | Medium | Distinct customer, rep, and manager surfaces; a help queue; structured result cards; accessible responsive polish; live updates; and complete error/loading states could create an intuitive cross-stakeholder experience. This assumes user flows are coherent and tested, not merely present. |
| Feasibility / Reusability / Scalability | **4/5** | High | Repository protocols, local durable adapters, restart-safe jobs, replay, health checks, and containerized startup improve reuse and credibility, but enterprise identity, managed distributed infrastructure, production integrations, and real outcome evaluation remain future work. |

**Rating-5-gates Round 2 readiness estimate: 18/20. Plausible judged range: 17–19.**

## Strongest repository evidence

1. The complete backend suite currently passes: **152 tests, 3 skipped, and
   216 subtests** in the local checkout.
2. The fixed synthetic golden path exercises ROI, denied Claim Story, Benefits,
   Claim Readiness, a visibly unsent notification preview, intervention
   recording, session summary, Sentinel events, and metrics without depending
   on Vertex AI or BigQuery.
3. The active ADK orchestrator reuses session context and calls grounded domain
   tools with explicit no-invention, ambiguity, escalation, and ROI rules.
4. Server-side roles protect HTTP and WebSocket routes; passwords are Argon2
   hashes and only session-token hashes are persisted.
5. The SQLite operations projection uses separate contact rows and an observable
   seven-day cohort for FCR/repeat rate rather than manufacturing a dashboard
   percentage. The payload and assumptions are labeled synthetic.
6. Stable typed boundaries exist for session summaries, events, metrics,
   operations charts, data repositories, and frontend consumption.

## Main score blockers

1. **The judge-visible product is incomplete.** The planned login and separate
   customer, rep, and five-tab manager experiences are not implemented in this
   checkout.
2. **The synthetic dashboard proves arithmetic, not impact.** Baselines are
   assumptions, and intervention recording is not connected to later claim
   adjudication.
3. **The active orchestration is strong but not clearly a rating-5 multi-agent
   system.** The root ADK agent mainly invokes deterministic specialist tools;
   the presentation should describe that architecture precisely.
4. **Clinical/risk breadth is intentionally narrow.** Referral, modifier, and
   diagnosis/CPT rules are deferred until reviewed evidence exists.
5. **Production boundaries remain visible.** Authentication and analytics are
   local SQLite, while event/session state is in process; enterprise audit,
   integrations, and distributed durability are future work.
6. **Presentation and collaboration are unverified.** The plan still needs
   named owners, rehearsed transitions, a concise metric story, and a tested
   fallback decision tree.
7. **First-class Voice parity is incomplete.** Both roles can select Voice and
   receive transcripts, but the current backend suppresses spoken AI output for
   reps even though the product contract now requires complete Chat and Voice
   for both roles. A credentialed live-model run also remains
   environment-dependent.

## Highest-impact next actions

| Rank | Action | Likely rubric impact |
|---:|---|---|
| 1 | Implement and rehearse the role-specific frontend, especially the five-tab manager dashboard and rep help queue. | Largest improvement to Round 1 Presentation and Round 2 UX; also makes existing technical work visible. |
| 2 | Implement Feature 13's versioned evaluation corpus, grounding/ROI/refusal/routing thresholds, latency measurements, and saved reports. | Strongest path from AI Approach 4 toward 5 and makes reliability claims auditable. |
| 3 | Implement Feature 14's explicit ADK specialist delegation, typed handoffs, and authorized trace projection while preserving deterministic services. | Directly addresses the main Technical Ambition blocker. |
| 4 | Implement Feature 15's population scan and evidence-backed rep queue with deduplication, transparent prioritization, and intervention progression. | Creates the differentiated proactive loop needed for Creativity 5. |
| 5 | Implement Feature 16's durable repository adapters, replay/idempotency, health checks, and containerized startup. | Strengthens technical credibility, reuse, and feasibility. |
| 6 | Turn the expanded golden path into a tightly timed narrative showing one pain point, agent handoff, grounded action, evaluation result, and defensible metric consequence. | Converts the new code evidence into Problem Understanding and Presentation points. |
| 7 | Add referral, modifier, and diagnosis/CPT rules only with reviewed compatibility data and focused counterexample tests. | Deepens domain coverage; weak or invented rules would reduce validity. |

## Probability of advancing to Round 2

These are broad judgment ranges, not statistical forecasts:

- **Current: approximately 50–70%.** The backend depth and responsible controls
  are above a basic prototype, and a well-run fallback demo can score around
  15/20 in Round 1. The incomplete role-specific frontend and unknown team
  presentation quality create substantial downside. If the selection rate is
  unusually low or judges heavily reward visual polish, the true probability
  could be below this range.
- **Rating-5 gates implemented well: approximately 80–90%.** A stable,
  role-specific product plus evaluated specialist delegation, a closed-loop
  prevention queue, and durable runtime evidence would support a plausible
  18–20/20 Round 1 result. This range assumes the larger scope does not
  introduce demo failures or unsupported clinical claims.

The most efficient route to Round 2 is not to maximize feature count. It is to
complete Features 12–16, make their evidence unmistakably visible, and add P2
work only when the scoring gates and deterministic contingency remain stable.
