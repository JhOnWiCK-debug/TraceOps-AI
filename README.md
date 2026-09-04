# TraceOps AI — Incident Investigation & Root-Cause Copilot

TraceOps AI is an evidence-grounded incident investigation system that analyzes operational evidence, retrieves relevant signals, ranks possible root causes, and produces a traceable investigation result.

## Problem

During production incidents, failures can propagate across multiple services. Engineers may see errors across several services without immediately knowing which failure is the actual root cause.

TraceOps AI treats incident investigation as **root-cause hypothesis ranking under uncertainty**.

## Incident Lab

The MVP uses a controlled service chain:

```text
Checkout Service → Payment Service → Redis
```

A deterministic Redis failure is injected during an incident.

Expected causal chain:

```text
Redis failure
     ↓
Payment failures
     ↓
Checkout failures
```

The incident has known ground truth, allowing the investigation pipeline to be evaluated objectively.

## System Pipeline

```text
Controlled Incident
        ↓
Operational Evidence
        ↓
Run-Scoped Evidence Ingestion
        ↓
Evidence Store
        ↓
Evidence Retrieval
        ↓
Category Evaluation
        ↓
Root-Cause Hypothesis Ranking
        ↓
Confidence + Citations + Recommended Action
```

## Evidence Retrieval

Operational events are normalized into a common evidence structure containing:

* Incident ID
* Run ID
* Timestamp
* Service
* Source type
* Event type
* Message
* Severity
* Source path

The retrieval layer supports:

* Keyword/BM25-style retrieval
* Metadata filtering
* Combined retrieval

Run-level isolation prevents evidence from previous executions from contaminating the current investigation.

## Root-Cause Reasoning

The MVP uses a deterministic evidence-based reasoning engine.

It evaluates competing hypotheses:

1. Redis connection failure
2. Payment Service failure
3. Checkout Service failure

The ranking considers:

* Direct root-cause evidence
* Downstream failure evidence
* Temporal consistency
* Dependency relationships
* Contradictory evidence

Scores are normalized and converted into a deterministic confidence level.

The system can abstain when evidence is insufficient or competing hypotheses are too close.

## Investigation Output

The system produces:

* Ranked hypotheses
* Root cause
* Confidence
* Supporting evidence
* Contradictory evidence
* Affected services
* Causal timeline
* Recommended action
* Evidence citations

Example:

```text
Root Cause: Redis connection failure
Confidence: High

Causal chain:
Redis → Payment Service → Checkout Service

Affected services:
Payment Service
Checkout Service

Recommended action:
Restore Redis connectivity and verify Payment/Checkout recovery.
```

## Evaluation

The current controlled incident achieved:

| Metric                     |    Result |
| -------------------------- | --------: |
| Root-cause Top-1 Accuracy  |       1.0 |
| Root-cause Top-3 Recall    |       1.0 |
| Affected-service Precision |       1.0 |
| Affected-service Recall    |       1.0 |
| Evidence Citation Validity |       1.0 |
| Tests                      | 16 passed |

The retrieval layer is additionally evaluated using category recall and temporal-chain validity.

## Project Structure

```text
lab/
├── services/
│   ├── checkout/
│   ├── payment/
│   └── redis/
│
├── scripts/
│   ├── start_lab.py
│   ├── generate_requests.py
│   ├── fault_injector.py
│   └── stop_lab.py
│
├── retrieval/
│   ├── ingestion.py
│   ├── store.py
│   ├── search.py
│   ├── evaluate.py
│   ├── reasoning.py
│   └── demo.py
│
├── data/
│   ├── incidents/
│   ├── evidence/
│   └── schemas/
│
└── tests/
```

## Running

Run the complete incident investigation demo with:

```bash
python lab/retrieval/demo.py
```

Run the test suite:

```bash
python -m pytest lab/tests -q
```

Expected result:

```text
16 passed
```

## Design Principles

* Evidence before conclusions
* Deterministic and reproducible evaluation
* Run-level data isolation
* Explicit competing hypotheses
* Traceable evidence citations
* Abstention when evidence is insufficient

## Current Scope

This is an MVP built around one controlled incident scenario. The system is intentionally kept small so that retrieval and reasoning behavior can be measured against known ground truth.

Future extensions could include additional incident types, richer operational signals, production telemetry integrations, and an optional natural-language explanation layer.

## Technologies

* Python
* SQLite
* Pytest
* REST-style service simulation
* Evidence retrieval
* Deterministic root-cause reasoning
