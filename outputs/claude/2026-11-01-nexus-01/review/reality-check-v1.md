# Reality-check round 1

Reviewer: reality-checker subagent (did not author any document in the package)
Subagent call id: afe5e4756b6c67dfd
Date: 2026-11-01

## 1. Summary verdict

**NEEDS WORK.** The package is unusually disciplined for Phase 0/1: brief traceability is explicit, provenance tags are used throughout, prompt-injection resistance is demonstrated (architecture Governance notice and gate-1 verdict), the call-audio-retention default and name-verification rule are consistent across voice/UX/privacy/architecture, and no document claims PO approval, production readiness, implementation or paid vendor commitment. Several defects warrant correction before PO review:

- F-01 (Major) coordinator silently closes OQ-D2 (call-recording retention) into a Gate-0 assumption and propagates it as settled.
- F-02 (Major) privacy document cites DE/EU statutes (HGB §257/AO §147, §201 StGB, BDSG §26, BetrVG §87(1) Nr.6, Art.6/9/17/22/33/34, TKG, TTDSG, LMIV/EU 1169/2011) without `Needs legal review:` on each citation.
- F-03 (Major) architecture §6.10 presents FR-15 metric definitions as authoritative while gate-1 flags them as still open — contradiction.
- F-10 (Major) courier PII visibility (phone/full-name/items) differs across architecture §8.5, privacy §9 R-D, and UX §5.3.
- F-04/05/06/07/08/09/11/12 (Minor) and F-13/14/15/16 (Nit) see §2.

## 2. Findings (headlines)
- F-01 Major — OQ-D2 silent closure (`handoffs/gate-0.md` §Assumptions carried forward; `discovery/product-discovery.md` §4.2 line 135 and OQ-D2 lines 231–234).
- F-02 Major — unflagged legal citations (`design/privacy.md` §§2–9).
- F-03 Major — FR-15 metric-definition contradiction (`design/architecture.md` §6.10 vs `handoffs/gate-1.md` line 37).
- F-04 Minor — self-reported call ids with no coordinator-side `run-log.md` corroboration.
- F-05 Minor — voice §9 OQ-PR-2 presupposes structured-transcript retention.
- F-06 Minor — business-strategy §7 asserts EU AI Act transparency obligation without flag.
- F-07 Minor — biometric-prohibition contractual term not lifted into architecture §8.5.
- F-08 Minor — privacy §6 "joint-controller analysis" for PSP not flagged `Needs legal review:`.
- F-09 Minor — UX §5.1 adds a VAT UI bullet not supported by brief/discovery.
- F-10 Major — courier PII visibility mismatch architecture §8.5 vs privacy R-D vs UX §5.3.
- F-11 Minor — privacy §1 D6 missing inline `Needs legal review:` on accounting bucket.
- F-12 Minor — voice latency p50/p95 carried into architecture §7.1 without `Assumption:` tag.
- F-13 Nit — convention tag sets differ across documents.
- F-14 Nit — Mermaid node name mismatch `Kitchen2` in architecture §2.1.
- F-15 Nit — Lieferando / Uber Eats / Wolt named without `Candidate (verify):` or `Assumption:`.
- F-16 Nit — voice §3.3 example PLZ unflagged (`Example:`).

## 3. Cross-document consistency (summary)
- Call-audio default `false` — OK.
- Verbal name verification before address recital — OK.
- EU AI Act disclosure legally flagged — PARTIAL (business-strategy §7 missing flag; F-06).
- FR-15 definitions coherent — MISMATCH (F-03).
- State model UX §4 ↔ architecture §4 — OK.
- Courier PII visibility — MISMATCH (F-10).
- Call id governance — UNABLE TO VERIFY (F-04).
- Prompt-injection resistance — OK.
- Transcript retention consistent — MISMATCH (F-05).
- Latency targets consistent — PARTIAL (F-12).

## 4. Traceability sampling — all six sampled FRs (FR-1, FR-5, FR-7, FR-13, FR-15, FR-19) traceable; FR-15 carries the F-03 consistency flag.

## 5. Open-question handling — all Phase-0 OQs preserved except OQ-D2 (F-01) and borderline OQ-D4 (single-attribute sufficiency presupposed, residual OQ about threshold retained — acceptable).

## 6. Scope-boundary audit — no implementation, production, VPS, MCP, vendor commitment, PO-approval claims, secrets, or real-customer data found. Boundary respected.

## 7. Recommendations before PO review
Must-fix: F-01, F-02, F-03, F-10.
Should-fix: F-04 (run-log), F-05, F-06, F-07, F-08, F-11, F-12, add tag precedence/convention.
Nice-to-have: F-09, F-13, F-14, F-15, F-16.

Codex independent review: not visible in inputs — status PENDING per PROTOCOL §Независимая проверка.
