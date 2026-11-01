# Reality-check round 2 (narrow re-verification)

Reviewer: reality-checker subagent (did not author any document in the package)
Subagent call id: a549f80f3b6c9efcd
Date: 2026-11-01
Scope: verify fixes applied for round-1 findings; look for regressions.

## 1. Verification table

| F-ID | Severity | PASS/FAIL | Evidence |
|---|---|---|---|
| F-01 OQ-D2 preserved as `Pending PO:` | Major | PASS | `handoffs/gate-0.md` lines 44–50 explicitly reopen OQ-D2 and tag "**F-01 fix: no OQ-D2 silent closure**". |
| F-02 DE/EU legal citations flagged | Major | PASS | `business-strategy.md` §7 bullets 118–121 each carry `Needs legal review:` + `Candidate (verify):`. `privacy.md` D6, §3 anchors, §4 Accounting bucket now tagged. |
| F-03 §6.10 FR-15 definitions `Recommendation:` pending ADR-SA-6 | Major | PASS | `architecture.md` §6.10 demoted; four sub-OQs listed; "**F-03 reconciliation**" marker present. |
| F-10 Courier PII reconciled (phone hidden by default) | Major | PASS | Architecture §7.5, privacy §9 R-D, UX §5.3 — three documents consistently state phone NOT visible by default; revealed only on explicit "Anrufen" tap with audit event. |
| F-05 voice OQ-PR-2 no longer presupposes retention | Should-fix | PASS | voice-ai.md §9 OQ-PR-2 reworded. |
| F-07 Biometric-prohibition contractual term in §7.5 | Should-fix | PASS | architecture.md §7.5 "**F-07 reconciliation**" clause added. |
| F-08 PSP joint-controller flagged | Should-fix | PASS | privacy.md §6 Payment row flagged `Needs legal review:`. |
| F-11 Privacy D6 inline tagged | Should-fix | PASS | privacy.md D6 retention cell inline `Needs legal review:` + `Candidate (verify):`. |
| F-12 Architecture §7.1 latency `Assumption:` | Should-fix | PASS | §7.1 row rewritten with `Assumption:` tags, cross-ref to NFR-1 `unknown`. |
| F-04 Run-log + id-governance limitation acknowledged | Should-fix | PARTIAL PASS | run-log.md exists; ledger lists all seven call ids; limitation of self-reported ids explicitly acknowledged. No independent cryptographic proof is possible from coordinator side — treated as PASS per the brief's "acknowledges" criterion. |

## 2. Regressions introduced by fixes

- None material. F-10 reconciliation phrasing is consistent across three documents.
- Minor presentational note: UX §5.3 and architecture §7.5 embed cross-reference labels ("architecture §7.5 F-10 reconciliation", "**F-07 reconciliation**") inside design text — acceptable traceability aid, not a regression.
- No new unflagged legal citations were introduced; §7.5 biometric clause references ADR-P-02 and privacy §9 R-A rather than naming statutes.

## 3. Residual round-1 items (nice-to-have)

Explicitly deferred in `run-log.md`:
- F-09 UX VAT bullet — still present at ux.md §5.1; at least now carries `Assumption:` tag. Acceptable, open.
- F-13 convention tag superset / precedence — open.
- F-14 Mermaid node `Kitchen2` mismatch (architecture §2.1) — still present.
- F-15 Lieferando/Uber Eats/Wolt without `Candidate (verify):` — still unflagged.
- F-16 Voice §3.3 example PLZ — not re-verified.
- F-06 EU AI Act transparency flag — effectively closed by F-02 blanket flagging.

Codex independent review remains PENDING; no change visible in round-2 inputs.

## 4. Verdict

**PASS** for the round-2 scope.

Rationale: All four must-fix findings (F-01, F-02, F-03, F-10) are addressed with locatable evidence; all six should-fix findings verified (F-04, F-05, F-07, F-08, F-11, F-12) pass. F-10 reconciliation is consistent across three documents, which was the specific risk flagged in round 1. No new regressions. Residual nice-to-have items remain open but are not blocking for PO review. Run-log acknowledges F-04 as a known governance limitation rather than claiming independent proof.

Caveats: this review verified only the specified diff points; it did not re-audit the full package. Codex independent review remains PENDING. The package remains a design artefact — no PO approval, no implementation claim, no production readiness implied.
