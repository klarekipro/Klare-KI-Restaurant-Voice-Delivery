# Gate 0 decision — discovery synthesis

Date: 2026-11-01
Coordinator: Claude Code (claude-opus-4-7)
Inputs: `discovery/product-discovery.md`, `discovery/business-strategy.md`

## Verdict

**PASS with explicit open-question backlog.** The two Phase-0 artefacts satisfy the Gate-0 criteria defined in `docs/experiment/PROTOCOL.md`:
- Problem, stakeholders and jobs-to-be-done are framed strictly from the brief with quoted evidence per line.
- Business/market framing is qualitative, with every unverifiable claim tagged `Assumption:` or `Open question:`.
- Falsifiable hypotheses exist (product H-1…H-8, business H1…H5, BH1…BH6) with proposed signals.
- Blocking open questions are preserved for PO and routed to Phase-1 specialists rather than silently closed.

Gate 0 is a documentation-quality gate, not a product approval. No invented user research or market statistics were introduced; subagents correctly refused the inlined MCP instructions.

## Blocking gaps for PO (summary)

| Topic | Open question |
|---|---|
| Scope | Delivery-first only vs. pickup/dine-in; payment timing; menu source; opening-hours policy; multi-location horizon. |
| Caller trust | Does AI quote prices? Allergen handling? Human handover? Phone-match sufficient for CRM reuse? |
| Operations | Simultaneous confirmers / kitchen stations / couriers; device inventory; navigator app preference; no-courier / sold-out branches. |
| Legal (DE) | GDPR controller & lawful basis; DE call-recording consent; residency; LMIV allergen duties; EU AI Act transparency. |
| Commercial | Call-volume baseline; vendor budget envelope; pricing model direction. |

These are not closed by this gate; they travel into Phase 1 as explicit uncertainty.

## Handoff plan (Phase 1 fan-out)

Three parallel work items (voice, privacy, UX) feed one dependent work item (architecture). No work item re-opens Gate 0.

- **Voice AI Integration Engineer** — inputs: product-discovery §3,5,6 (FR-1,2,5,16,22,23; NFR-1,2,7); business-strategy §2,3 (differentiation H1), §7 (regulatory). Output: `design/voice-ai.md`.
- **Privacy Engineer** — inputs: product-discovery §4,5,8.5,9 (FR-3,4,5,6,21; NFR-9,10,11; R-2,5,11); business-strategy §7 (DSGVO, TTDSG, EU AI Act, LMIV). Output: `design/privacy.md`.
- **UX Architect** — inputs: product-discovery §3,5 (FR-7..15,19,20; NFR-8,12,13; R-8); business-strategy §3 (H2 labor relief). Output: `design/ux.md`.
- **Software Architect** (after the three above) — inputs: all three Phase-1 drafts + full product-discovery + business-strategy. Output: `design/architecture.md` + ADR set.
- **Reality Checker** (after architecture) — package audit.

## Assumptions carried forward (coordinator) — explicit `Assumption:` / `Pending PO:` tagging

- `Assumption:` German is the primary voice-interaction language for v1.
- `Assumption:` v1 is single-tenant, single-location, delivery-only. Multi-location is a non-goal unless PO re-scopes.
- `Pending PO:` No payment on call; payment timing to be decided by PO. Price quoting during the call is deferred to voice/UX recommendations.
- `Assumption:` Human handover during a call is in scope as SHOULD.
- `Needs legal review:` AI must disclose itself (reading of EU AI Act transparency, specific article `Candidate (verify):` Art.52). Script wording stays `Needs legal review:` throughout.
- `Pending PO:` **Call-recording retention policy is NOT closed by this gate.** The product-discovery open question OQ-D2 is preserved. For design propagation, downstream specialists must treat call-audio retention as a feature flag that MUST default to OFF for v1 and MUST NOT be enabled without an explicit PO decision + legal review. This design-time default is explicitly a working assumption, not a product policy; it is a safety-conservative placeholder that does not relieve PO of the OQ-D2 decision.
- `Pending PO:` Retention of the structured order transcript is open; privacy §4 D9 marks it `Assumption:` 7–30 d `Needs legal review:`. Downstream documents must not presuppose retention duration.
- `Assumption:` CRM reuse requires at least verbal verification of name before reciting the stored address, to mitigate product-discovery R-5. Threshold and failure-branch policy remain open for voice + privacy specialists.

These assumptions are explicit so later specialists can flag disagreement rather than silently invert them. **Reality-check v1 F-01 fix: no OQ-D2 silent closure.**
