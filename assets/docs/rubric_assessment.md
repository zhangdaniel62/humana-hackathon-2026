# Claim Assist rubric assessment

This is a candid repository-based assessment against the supplied Humana
Military hackathon rubric. It is not a prediction from the organizers. The
point estimates below assume a clear seven-minute presentation and a working
deterministic fallback. Actual advancement depends on the field, judge
weighting, cut line, presentation execution, and whether live integrations work
in the judging environment.

## How to read the assessment

- **Current** means the code and presentation assets present in this checkout.
- **P2-complete** means Feature 12 and every item in Section 11 of
  `assets/docs/overall_plan.md` are implemented, reviewed, tested, stable, and
  demonstrated. Merely adding those features without evidence or reliability
  does not earn the projected score.
- Repository evidence is separated from assumptions. Synthetic operations data
  demonstrates calculation and presentation paths; it is not evidence that
  Humana outcomes improved.
- Round 1 is the relevant rubric for the advancement decision. Round 2 scores
  are included to show how competitive the solution would be after advancing.

## Executive assessment

| Scenario | Round 1 point estimate | Plausible judged range | Round 2 readiness estimate | Plausible judged range |
|---|---:|---:|---:|---:|
| Current | **15/20** | **14–17** | **14/20** | **13–15** |
| All P2 implemented well | **18/20** | **17–19** | **17/20** | **16–18** |

The current entry is technically strong enough to be a credible Round 2
candidate, but its largest judging risk is that much of the product experience
is still exposed through backend-oriented fallback pages and APIs. Completing
P2 would primarily improve judge-visible usability, breadth, and polish. It
would not by itself prove real operational impact.

## Round 1 scoring

### Current repository

| Category | Score | Confidence | Evidence and rationale |
|---|---:|---|---|
| Problem Understanding | **4/5** | High | The plan maps members, representatives, providers, supervisors, and operations users to concrete pain points. The implementation directly addresses claim explanation, benefits, ROI gaps, readiness, repeat contacts, AHT, FCR, and corrective interventions. Metric definitions explicitly distinguish mature seven-day cohorts and avoid claiming that an intervention prevented a denial. A 5 would require an even tighter presentation of root-cause prioritization and credible outcome validation, not only synthetic trends. |
| Technical Ambition / Difficulty | **4/5** | High | The repository combines Google ADK, a live chat/voice WebSocket, deterministic grounded tools, BigQuery/CSV adapters, shared session context, ROI controls, structured summaries, role-based authentication, async Sentinel events, and persisted SQLite analytics. The active caller path is primarily one ADK root `LlmAgent` invoking specialist tools; specialist agent modules exist, but the live workflow is not yet exceptional multi-agent orchestration. Local SQLite and in-memory runtime state also cap the score below 5. |
| Creativity and Innovation | **4/5** | Medium | Proactive claim readiness, ROI pre-screening, grounded notification previews, corrective-intervention events, and operational risk monitoring go beyond a generic chatbot. The workflow is inventive and proactive, but several headline capabilities closely follow the challenge prompt, and there is no validated predictive model or demonstrated final-adjudication prevention loop. |
| Presentation and Collaboration | **3/5** | Low | There is a timed presentation plan, fixed-ID golden path, deterministic fallback, saved dashboard artifact, static voice demo, operations page, and a detailed frontend handoff. However, the role-specific product frontend is pending, the current operations page does not render the new trend dashboard, and presentation owners are placeholders. Collaboration quality cannot be established from repository evidence alone. |

**Current Round 1 point estimate: 15/20. Plausible judged range: 14–17.**

### If all P2 work is implemented well

| Category | Score | Confidence | Why it moves |
|---|---:|---|---|
| Problem Understanding | **5/5** | Medium | Reviewed referral, modifier, and diagnosis/CPT rules plus population scanning and risk-factor aggregation would show deeper command of denial root causes and operational workflows. The score still depends on explaining which signals are reviewed rules versus assumptions. |
| Technical Ambition / Difficulty | **5/5** | Medium | Population-wide scanning, meaningful aggregation, additional validated readiness logic, role-specific experiences, advanced filters, and live push would form a broad and difficult end-to-end system. This projection assumes the added scope remains modular, tested, and stable. |
| Creativity and Innovation | **4/5** | Medium | The complete system would be substantially more proactive and workflow-aware, but most P2 additions deepen capabilities already named in the prompt. A 5 would be possible only if the team demonstrates a clearly differentiated proactive workflow and explains why it is more than a collection of features. |
| Presentation and Collaboration | **4/5** | Low | A responsive, accessible login/customer/rep/manager experience would make the story far easier to follow and demonstrate. A 5 cannot be projected from implementation alone; it requires excellent rehearsal, seamless role handoffs, explicit tradeoffs, and visible team collaboration. |

**P2-complete Round 1 point estimate: 18/20. Plausible judged range: 17–19.**

## Round 2 scoring

### Current repository

| Category | Score | Confidence | Evidence and rationale |
|---|---:|---|---|
| Solution Impact and Effectiveness | **3/5** | High | The system addresses all four target metric areas and demonstrates transparent calculations using labeled synthetic data. It shows credible potential, not measured improvement in real workflow conditions. There is no linked final adjudication outcome and therefore no demonstrated preventable-denial reduction. |
| Initial AI Approach | **4/5** | High | The approach is grounded and responsible: deterministic domain services, typed outputs, exact-record lookup, ambiguity handling, ROI fail-closed behavior, claim-ID confirmation, safe escalation, and LLM narration through ADK. A 5 would benefit from explicit quality evaluation, retrieval/routing evaluation, calibrated confidence evidence, and stronger demonstrated multi-agent execution. |
| User Experience | **3/5** | High | Plain-language agent instructions, transcripts, safe next steps, structured summaries, a legacy Voice validation page, and an operations view support the primary workflow. The missing first-class role-specific Chat/Voice frontend, help queue, manager trend charts, and polished state handling prevent a 4. |
| Feasibility / Reusability / Scalability | **4/5** | High | The code has modular services, Pydantic contracts, repository adapters, fallback data sources, server-side RBAC, deterministic seeds, and a passing automated suite. The current SQLite auth/analytics database, in-memory sessions/events, local credentials, and missing production integrations are appropriate hackathon boundaries but not enterprise-ready scale. |

**Current Round 2 readiness estimate: 14/20. Plausible judged range: 13–15.**

### If all P2 work is implemented well

| Category | Score | Confidence | Why it moves |
|---|---:|---|---|
| Solution Impact and Effectiveness | **4/5** | Medium | Population scanning and more complete reviewed risk rules would increase the number of actionable workflows, while the frontend would make them operationally usable. It remains a 4 until real or controlled outcome evidence demonstrates improvement. |
| Initial AI Approach | **4/5** | Medium | P2 broadens the governed rule set and routing surface, but it does not automatically add evaluation, calibration, or a validated predictive method. A 5 requires evidence that the combined methods are accurate and reliable, not just broader. |
| User Experience | **5/5** | Medium | Distinct customer, rep, and manager surfaces; a help queue; structured result cards; accessible responsive polish; live updates; and complete error/loading states could create an intuitive cross-stakeholder experience. This assumes user flows are coherent and tested, not merely present. |
| Feasibility / Reusability / Scalability | **4/5** | High | The additional work improves product completeness and reuse, but enterprise identity, durable distributed state/event storage, production integrations, audit controls, and outcome evaluation intentionally remain future work. |

**P2-complete Round 2 readiness estimate: 17/20. Plausible judged range: 16–18.**

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
| 2 | Turn the golden path into a tightly timed narrative that shows one pain point, one grounded action, and one defensible metric consequence at each step. Name owners and rehearse fallback transitions. | Improves Problem Understanding and Presentation without adding risky scope. |
| 3 | Add an explicit evaluation slide or artifact: fixed test cases, grounding/ROI pass rates, unsupported-answer refusals, readiness-rule precision on reviewed fixtures, and latency where measured. | Strongest path from AI Approach 4 toward 5 and makes reliability claims auditable. |
| 4 | Implement the population-wide pending-claim scan and provider/CPT/risk aggregation with deduplication and alert thresholds. | Raises Technical Ambition, Creativity, and expected Impact if the output is judge-visible. |
| 5 | Add referral, modifier, and diagnosis/CPT rules only with reviewed compatibility data and focused counterexample tests. | Deepens problem understanding and AI responsibility; weak or invented rules would reduce validity. |
| 6 | Add a clearly synthetic later-adjudication experiment only if its assumptions can be shown transparently; otherwise keep the current intervention-coverage language. | Could strengthen impact methodology, but must never be presented as observed denial prevention. |
| 7 | Enable and test spoken AI output for rep Voice, verify complete customer/rep Chat and Voice behavior with judge-environment credentials, then finish a clean README runbook. | Resolves the product-contract mismatch and reduces demo failure and credibility risk. |

## Probability of advancing to Round 2

These are broad judgment ranges, not statistical forecasts:

- **Current: approximately 50–70%.** The backend depth and responsible controls
  are above a basic prototype, and a well-run fallback demo can score around
  15/20 in Round 1. The incomplete role-specific frontend and unknown team
  presentation quality create substantial downside. If the selection rate is
  unusually low or judges heavily reward visual polish, the true probability
  could be below this range.
- **All P2 implemented well: approximately 70–85%.** A stable, polished,
  role-specific product plus population scanning and reviewed additional rules
  would remove the most visible gaps and support a plausible 17–19/20 Round 1
  result. This range assumes the larger scope does not introduce demo failures
  or unsupported clinical claims.

The most efficient route to Round 2 is not to maximize feature count. It is to
make the existing grounded workflow unmistakably visible, demonstrate that its
calculations and safety controls are real, and then add only the P2 work that
can be rehearsed reliably.
