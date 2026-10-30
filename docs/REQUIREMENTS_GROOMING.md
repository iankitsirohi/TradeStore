# Trade Store - Requirements Grooming for Production Readiness

## 1. Purpose and status

This document records questions and requirements that were not defined in the original assignment. It is intended to guide stakeholder requirements grooming before the Trade Store is considered for a live environment.

The current implementation was built against the original assignment: a Python REST API with SQL persistence, trade-version and maturity-date validation, expiry handling, automated tests, CI vulnerability scanning, and optional PlantUML diagrams. It is an assignment-scope implementation, not a production-readiness assessment or a claim that the requirements below have been implemented.

No requirements-grooming phase has yet been completed. The questions below need decisions from the relevant business, operations, data, security, and engineering stakeholders. Until then, production behavior and service levels remain assumptions.

## 2. Original assignment scope

The original assignment specifies:

- A Python REST API using SQL or NoSQL persistence.
- Unit tests developed using a TDD approach.
- A deployment pipeline, preferably GitHub Actions or Jenkins, with automated regression tests and an open-source vulnerability scan. The build must fail on critical or blocker vulnerabilities.
- PlantUML design diagrams, if feasible.
- A trade store that receives trades and organizes them in a specific sequence.
- Rejection of lower trade versions, replacement for the same version, and rejection of trades with a maturity date earlier than today.
- Automatic expiry when a trade's maturity date is surpassed.
- Upload of the produced code to a public GitHub account.

The assignment does not define the production integration, business-calendar, audit, security, scale, availability, retention, recovery, or downstream-event contracts. The current REST interface and SQLite implementation are choices made to satisfy the assignment, not stakeholder-approved production decisions.

## 3. Business-rule questions requiring decisions

### 3.1 Trade ordering and version semantics

- What does "specific sequence" mean: arrival order, ascending version, creation/business timestamp, or another ordering?
- Is sequence global or maintained independently for each `trade_id`?
- Are version numbers required to be contiguous? If version 3 arrives before version 2, should version 2 be rejected, held for later, or accepted as historical data?
- Is a higher version always a valid update, or must it satisfy additional transition rules?
- When a same-version trade is received, is it a retry, a correction, or a conflict? Should it overwrite, be treated as an idempotent no-op, or create a separately auditable revision?
- Which record is authoritative when two sources submit different payloads for the same trade and version?

### 3.2 Historical loads and sample-data contradiction

The sample includes T3 with a maturity date in 2014 and `expired = Y`, while the rule says a trade with a maturity date before today must be rejected. This leaves unclear whether the sample represents a historical import, an already-stored record, or an exception to the live-ingestion rule.

- Is there a separate backfill/import path that accepts historical and already-expired trades?
- If so, who may use it, how is it authorized, and how are imported records distinguished from live submissions?
- Should an already-matured imported trade be accepted with `expired = true`, or should the normal expiry process mark it later?
- Does `created_date` mean the date the trade was created in the source system, booked, or received by this store? The sample includes a historical created date for T2 v1.

### 3.3 Rejections, retries, and recovery

- Should rejected submissions be discarded, returned only to the caller, or persisted for operational investigation and replay?
- If retained, should the system store the original payload, source, receipt time, rejection code, and correlation/idempotency key? What are the access and retention rules?
- Who owns correction and replay of rejected trades, and what safeguards prevent a replay from applying twice?
- How should transient storage or downstream failures be reported so senders can distinguish retryable failures from permanent business rejections?
- Is a client-supplied idempotency key required? What should happen if the same key is reused with a different payload?

### 3.4 Maturity, expiry, and post-expiry changes

- Which timezone defines "today": UTC, the server's timezone, a market location, or a trade-specific timezone?
- Does a date-only maturity expire at the start or end of that day? Are market holidays, weekends, cut-off times, or business-day calendars relevant?
- Is expiry evaluated per version or only for the latest version of a trade?
- Can an expired trade receive a new version, and can a correction reactivate it? What is the permitted transition policy?
- Is expiry a persisted state transition that emits an event, or a value derived at read time? How quickly must the state become visible?

## 4. Data, audit, and integration requirements

### 4.1 Trade contract and reference data

- What is the canonical trade schema, including required business attributes such as product, notional, currency, price, booking entity, and counterparty?
- How are schema changes versioned and kept compatible with existing senders and consumers?
- Are counterparty and portfolio identifiers validated against reference/master data? Which system owns that data, and how are missing, inactive, or changed identifiers handled?
- What data classification, masking, encryption, and access rules apply to trade fields and rejected payloads?

### 4.2 Audit, lineage, and retention

- Which sender, user, source channel, and correlation identifiers must be recorded for each submission?
- Must the system retain the full sequence of accepted submissions and corrections, including previous same-version payloads, or only the latest state?
- What are the legal, regulatory, and business retention periods for accepted, expired, and rejected records?
- Are archival, legal hold, deletion, or data-subject workflows required?
- Who can view, export, correct, or replay trade data, and how are those actions audited?

The current storage key `(trade_id, version)` retains distinct versions, but replacement of an existing key overwrites that record. It is not a complete submission audit history.

### 4.3 Downstream consumers and events

- Which systems consume accepted, amended, rejected, and expired trade information?
- Are consumers served through API queries, files, a message queue/event stream, or a combination?
- What delivery guarantees are required (at-most-once, at-least-once, or effectively-once), and how do consumers deduplicate events?
- Must persistence and event publication be atomic? If so, should a transactional outbox or equivalent pattern be used?
- What event schema, compatibility, ordering, replay, and dead-letter policies are required?
- Is reconciliation required between the trade store and downstream systems? Which system is authoritative when records differ?

## 5. Ingestion and scale requirements

"Thousands of trades" and "any method of transmission" do not define a measurable load or integration contract.

- Which ingestion channels are in scope for the first release: REST, batch API, file transfer, message broker, or others?
- What are expected average and peak trades per second, burst duration, payload size, batch size, and daily volume?
- What are the required API and ingestion latency percentiles, and how quickly must a submitted trade be queryable?
- Must input order be preserved per trade across concurrent requests, batches, retries, and multiple channels?
- What backpressure, rate-limit, queue-depth, retry, timeout, and poison-message behavior is expected?
- Is pagination, filtering, bulk retrieval, or export required for operational and reporting use cases?
- What load, soak, concurrency, and failure-injection tests are required before launch, and what measurable thresholds must they meet?

## 6. Availability, deployment, and recovery

- What are the availability SLO/SLA and maintenance-window expectations?
- What are the recovery point objective (RPO) and recovery time objective (RTO)?
- Which environments and deployment targets are required (cloud, on-premises, containers, Kubernetes, or another platform)?
- Which database is appropriate for the agreed throughput, high availability, backups, replication, and multi-instance operation?
- What backup frequency, restore testing, disaster-recovery region/site, and failover procedures are required?
- How are database schema migrations versioned, reviewed, applied, and rolled back?
- Should expiry run in one coordinated scheduler/job rather than independently in each application worker? What is the required expiry processing delay?
- What are the deployment, rollback, secrets-management, image-signing, and artifact-retention requirements?

The assignment implementation uses SQLite and creates its schema at startup. Its expiry scheduler is process-local, and reads also trigger expiry updates. These are simple assignment choices; their suitability must be re-evaluated against production scale and deployment topology.

## 7. Security, privacy, and compliance

- Which authentication and authorization mechanisms are required for submit, query, import, replay, and administrative operations?
- How are service-to-service identities, user identities, and least-privilege roles managed?
- Is TLS required for all network traffic? What encryption-at-rest and key-management standards apply?
- What request-size limits, rate limits, input protections, network restrictions, and abuse controls are required?
- What security logging, audit access, incident response, vulnerability remediation, and penetration-testing processes apply?
- Which regulatory, privacy, data-residency, and records-management obligations apply?
- What is the required vulnerability policy: which severities block a build, how are exceptions approved, and how are scanners and dependency databases kept current?

The original assignment requires a vulnerability scan and a failing build for critical or blocker vulnerabilities. It does not define the scanner, severity mapping, exception process, or broader security controls. The current CI uses Trivy and gates on CRITICAL findings; Trivy does not define a separate "blocker" severity.

## 8. Observability and operational ownership

- Which metrics are required, including received, accepted, replaced, rejected-by-reason, expired, retried, and replayed trade counts?
- What logs, trace/correlation identifiers, dashboards, and alert thresholds are required?
- Who owns service support, incident response, business-rule changes, data corrections, and after-hours escalation?
- What operational views or APIs are required for rejected submissions, backlog, expiry lag, and reconciliation status?
- Should readiness checks verify database connectivity and required dependencies, separately from process liveness?
- What are the runbooks for a stuck expiry job, database outage, event-delivery backlog, failed deployment, and recovery/replay?

## 9. AI/ML scope

AI or machine learning is not required by the original assignment. Do not introduce it into deterministic acceptance, version, or expiry decisions without an explicit business requirement and governance approval.

If AI/ML is proposed for anomaly detection, data-quality assistance, or operational triage, clarify:

- The decision it is intended to improve and measurable success criteria.
- Whether model output is advisory or can affect processing; who reviews and approves actions.
- Data use, privacy, retention, model hosting, explainability, bias, monitoring, and audit requirements.
- Safe fallback behavior and a clear guarantee that model output cannot silently bypass deterministic trade rules.

## 10. Proposed grooming outputs and release gates

Before production design is finalized, record stakeholder-approved answers for:

1. Ordering, version gaps, same-version updates, and authority/conflict rules.
2. Historical import treatment and the T3 / past-maturity contradiction.
3. Timezone, maturity cut-off, expiry timing, and post-expiry changes.
4. Rejection persistence, retryability, idempotency, and operational replay.
5. Canonical trade schema, reference data ownership, audit, and retention.
6. Ingestion channels, traffic profile, latency, availability, RPO, and RTO.
7. Security, privacy, compliance, observability, and operational ownership.
8. Downstream contracts, event delivery, reconciliation, and consumer replay needs.
9. Acceptance criteria and measurable functional, load, resilience, and recovery tests.

Treat the current code as assignment-scope until these decisions are made. Production readiness should be assessed against the approved requirements, with corresponding architecture, implementation, security review, operational controls, and test evidence. Any unresolved item should have a named owner, an agreed assumption or mitigation, and a target decision date before go-live approval.
