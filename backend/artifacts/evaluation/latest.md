# Claim Assist evaluation report

- Corpus: `2026-07-17-v1`
- Mode: `offline_deterministic`
- Result: **8/8 passed (100.0%)**
- Threshold: 100.0% — met
- Latency: p50 0.021 ms; p95 3.448 ms
- Live ADK evaluation: skipped; opt in with --live

| Category | Passed | Total | Pass rate |
|---|---:|---:|---:|
| grounding | 3 | 3 | 100.0% |
| roi | 1 | 1 | 100.0% |
| routing_contract | 3 | 3 | 100.0% |
| safety | 1 | 1 | 100.0% |

| Case | Category | Result | Latency (ms) |
|---|---|---|---:|
| claim-story-grounding | grounding | pass | 4.901 |
| readiness-reviewed-rule | grounding | pass | 0.028 |
| readiness-clear-control | grounding | pass | 0.013 |
| roi-self-service | roi | pass | 0.300 |
| roi-fail-closed | safety | pass | 0.750 |
| route-claim-story | routing_contract | pass | 0.001 |
| route-readiness | routing_contract | pass | 0.001 |
| route-benefits | routing_contract | pass | 0.001 |

Offline routing cases validate the declared deterministic routing contract, not live-model routing accuracy. Network latency is never used as an offline threshold.
