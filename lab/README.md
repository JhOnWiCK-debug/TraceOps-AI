# TraceOps AI — Incident Investigation & Root-Cause Copilot

TraceOps AI is an evidence-grounded incident investigation system that analyzes operational evidence, retrieves relevant signals, ranks possible root causes, and produces a traceable investigation result.

## Problem

During production incidents, failures can propagate across multiple services. An engineer may see errors in several services without immediately knowing which failure is the actual root cause.

TraceOps AI models this problem as **root-cause hypothesis ranking under uncertainty**.

## Current Incident Lab

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

The system has ground-truth incident metadata so its investigation results can be evaluated objectively.

## Pipeline

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

Operational events are normalized into a common evidence structure containing information such as:

* incident ID
* run ID
* timestamp
* service
* source type
* event type
* message
* severity
* source path

Retrieval supports:

* keyword/BM25-style search
* metadata filtering
* combined retrieval

The evaluation uses category-level matching rather than counting repeated log lines as separate independent signals.

## Root-Cause Reasoning

The MVP uses a deterministic evidence-based reasoning engine.

It evaluates competing hypotheses such as:

1. Redis connection failure
2. Payment Service failure
3. Checkout Service failure

The ranking considers evidence such as:

* direct root-cause signals
* downstream failure evidence
* temporal consistency
* dependency relationships
* contradictory evidence

Scores are normalized and converted into a deterministic confidence level.

The system can also abstain when the available evidence is insufficient or competing hypotheses are too close.

## Investigation Output

The final result contains:

* ranked hypotheses
* root cause
* confidence
* supporting evidence
* contradictory evidence
* affected services
* causal timeline
* recommended action
* evidence citations

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

The current controlled incident produced:

| Metric                     |    Result |
| -------------------------- | --------: |
| Root-cause Top-1 Accuracy  |       1.0 |
| Root-cause Top-3 Recall    |       1.0 |
| Affected-service Precision |       1.0 |
| Affected-service Recall    |       1.0 |
| Evidence Citation Validity |       1.0 |
| Tests                      | 16 passed |

The retrieval layer is also evaluated using category recall and temporal-chain validity.

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

## Running the Lab

Start the controlled environment:

```bash
python lab/scripts/start_lab.py
```

Generate traffic:

```bash
python lab/scripts/generate_requests.py --count 2 --interval 0.1
```

Inject the Redis failure:

```bash
python lab/scripts/fault_injector.py --action fail
```

Generate requests during the incident:

```bash
python lab/scripts/generate_requests.py --count 4 --interval 0.1
```

Recover:

```bash
python lab/scripts/fault_injector.py --action recover
```

Stop the lab:

```bash
python lab/scripts/stop_lab.py
```

Run the investigation demo:

```bash
python lab/retrieval/demo.py
```

Run the test suite:

```bash
python -m pytest lab/tests -q
```

## Design Principles

* Evidence before conclusions
* Deterministic and reproducible evaluation
* Run-level data isolation
* Explicit competing hypotheses
* Traceable evidence citations
* Abstention when evidence is insufficient

## Current Scope

This is an MVP built around one controlled incident scenario. The architecture is intentionally kept small so that retrieval and reasoning behavior can be measured against known ground truth.

Future work could include additional incident types, richer operational signals, production telemetry integrations, and an optional natural-language explanation layer.

## Technologies

* Python
* SQLite
* Pytest
* REST-style service simulation
* Deterministic evidence retrieval
* Rule-based root-cause reasoning
