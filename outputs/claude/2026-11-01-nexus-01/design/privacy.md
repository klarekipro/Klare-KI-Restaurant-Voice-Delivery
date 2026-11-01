# Phase-1 Privacy & Data Design — AI Phone-Ordering Assistant (Germany)

Role: Privacy Engineer (design-only subagent).
Subagent call id: a35e24308d8439601
Scope: NEXUS Phase 1 design slice. No implementation, no live data, no vendor commitment.
Inputs: `brief/restaurant-idea.md`, `outputs/claude/2026-11-01-nexus-01/discovery/product-discovery.md`, `outputs/claude/2026-11-01-nexus-01/discovery/business-strategy.md`, `outputs/claude/2026-11-01-nexus-01/handoffs/gate-0.md`, `docs/experiment/PROTOCOL.md`, `docs/experiment/SECURITY.md`.
Date: 2026-11-01.

Legal disclaimer: Engineering design analysis, not legal advice. Every lawful-basis selection, retention duration, consent-script wording, and transfer safeguard tagged `Needs legal review:` must be reviewed by qualified German/EU counsel or a DPO before any pilot handling real callers. Absence of a tag does not imply legal sign-off.

Tags: `Fact from brief:`, `Assumption:`, `Open question:`, `Needs legal review:`, `Recommendation:`.

Gate-0 assumptions relied on (no disagreement at this stage): German primary; v1 single-tenant, single-location, delivery-only; AI must disclose itself; call audio not retained by default; structured order transcript retained; CRM reuse requires verbal name verification before reciting stored address.

---

## 1. Data map

Legend: ID = identifier; CT = contact; SC = special-category (Art.9); BH = behavioural; AG = aggregate/derived.

| # | Data element | Category | Source | Where stored (proposed) | Retention (proposed, see §4) | Who sees (role) | Lawful basis candidate (Art.6) | Cross-border concern (Art.44–49) | Minimization notes |
|---|---|---|---|---|---|---|---|---|---|
| D1 | Caller phone number (CLI/ANI) | ID / CT | Telephony signalling | Telephony provider logs; order service DB; CRM | CRM: see D4; call-log metadata short | AI runtime, confirmer, owner (CRM) | (b) contract; (f) for CRM lookup — `Needs legal review:` | Likely if STT/LLM/telephony outside EU | Not needed for AI reasoning beyond lookup key |
| D2 | Caller spoken name | CT | Caller speech | STT transient; order record; CRM | CRM: see D4; order: see D6 | AI runtime, confirmer, courier, owner | (b) contract | Processor region dependent | Store normalized once; do not duplicate across tables |
| D3 | Delivery address | CT | Caller speech or CRM | Order record; CRM; courier app | Order: see D6; CRM: see D4 | AI runtime, confirmer, assigned courier, owner | (b) contract | Processor region dependent | Mask apartment-level notes in dashboard |
| D4 | CRM customer record | ID / CT / BH | System-generated from D1–D3 | CRM DB | `Assumption:` 24 months inactivity → delete; `Needs legal review:` | Confirmer, owner | (f) + (b) if active contract; `Needs legal review:` | Keep EU-resident | No marketing fields in v1 |
| D5 | Order line items + modifiers | BH | Caller speech, menu catalog | Order record | See D6 | AI, confirmer, kitchen, courier, owner | (b) contract | Processor region dependent | Pseudonymise for analytics |
| D6 | Order total | BH | Pricing calc | Order record; accounting export | `Needs legal review:` HGB §257 / AO §147 `Candidate (verify):` cited for 10-year retention of commercial/tax records; must be confirmed with counsel | Confirmer, owner, accounting | `Needs legal review:` (c) legal obligation (archive) + (b) operational | EU-only recommended | Separate operational store from accounting archive |
| D7 | Call-audio stream (live) | SC-risk / BH | Telephony media | In-memory at telephony/STT boundary only; not persisted by default | Transient only | AI runtime (ephemeral) | (b) contract; (a) consent if persisted — `Needs legal review:` | High: STT typically non-EU — `Needs legal review:` | Prefer streaming STT without storage |
| D8 | Call-audio recording (optional) | SC-risk / BH | Telephony recorder | Only if feature enabled | `Assumption:` not retained in v1 per Gate-0; if enabled: ≤30 d; `Needs legal review:` | Owner (dispute); support (narrow) | `Needs legal review:` likely (a) consent + §201 StGB; TKG implications | High | Default OFF |
| D9 | Derived call transcript | BH (contains CT fragments) | STT + LLM extraction | Order service DB; separate transcript store (optional) | `Assumption:` structured order with D5–D6; raw dialog 7–30 d; `Needs legal review:` | AI, confirmer; support (break-glass) | (b) for structured order; (f) for raw with LIA | Processor region dependent | Redact non-order PII in raw transcript |
| D10 | Order state transitions | BH | System-generated | Order service event log | `Assumption:` 90 d operational; aggregates longer | Confirmer, kitchen, courier, owner | (f) legitimate interest with LIA | EU-only recommended | Timestamps + state only; no caller content |
| D11 | Courier identity | ID | Staff onboarding | IAM / user directory | Employment + lawful follow-on | Owner, admin | (b) employment; (f) — `Needs legal review:` BDSG §26 | EU-only | Separate staff IAM from customer CRM |
| D12 | Courier location / route | BH / ID sensitive | Courier device | `Assumption:` not stored centrally beyond closure in v1 | `Needs legal review:` works-council co-determination | Owner (aggregate), dispatcher | (f) strong LIA; (a) weak for employees | High if non-EU vendor | Prefer nav deep-link only |
| D13 | Staff identity | ID | Staff onboarding | IAM | Employment duration | Admin | (b) employment; (f) operational | EU-only | Role-based where feasible |
| D14 | Staff authentication events | BH | System | Auth logs | `Assumption:` 90–180 d; `Needs legal review:` | Admin, security | (f) security + (c) if required | EU-only | No plaintext credentials |
| D15 | Dashboard aggregates | AG (derivable to person via courier) | Derived | Analytics store | `Assumption:` daily snapshots 24 months | Owner | (f) legitimate interest | EU-only | Avoid caller identifiers in dashboard |
| D16 | Payment reference | ID | External PSP / staff | Order record | `Needs legal review:` tax retention | Owner, accounting | (b) + (c) | PSP-dependent | Store token/reference, not PAN |
| D17 | Troubleshooting access events | BH | System | Audit log | `Assumption:` 12 months; `Needs legal review:` | Admin, DPO | (f) accountability | EU-only | Reason code required for break-glass |
| D18 | Consent/disclosure acknowledgement | BH | System | Order record | Lifetime of related order record | Confirmer, DPO on request | (f) accountability | EU-only | Timestamp + script version, not audio |
| D19 | DSR request records | CT | Caller / DSR channel | Separate DSR tracker | `Assumption:` 3 years; `Needs legal review:` | DPO, owner | (c) legal obligation + (f) accountability | EU-only | Separate from CRM |
| D20 | Backup copies | mirrors source | System | Backup store | `Assumption:` encrypted; rolling 30 d; `Needs legal review:` | Admin (restore only) | mirrors source | EU-only | Document deletion-from-backup policy |

`Open question:` Central kitchen-display vs. per-station paper ticket? Affects D5 recipients and ephemerality.
`Open question:` Is courier location telemetry (D12) actually required for v1 or is a one-way deep-link to a nav app sufficient?
`Recommendation:` v1 prefer nav deep-link to avoid becoming controller of continuous location data.

---

## 2. Lawful basis analysis per processing purpose

| # | Purpose | Data in scope | Candidate basis | Rationale | Status |
|---|---|---|---|---|---|
| P1 | Order-taking + fulfilment | D1–D6, D7 transient, D9 structured, D10 | Art.6(1)(b) performance of (pre-)contract | Data necessary to perform the order | `Recommendation:` primary basis; `Needs legal review:` confirm pre-contract framing |
| P2 | CRM retention of repeat callers | D1, D2, D3, D4 | Art.6(1)(f) with LIA; or (a) consent | Convenience not strictly necessary; must pass LIA; opt-out feasible | `Needs legal review:` LIA vs. consent; profiling implications |
| P3 | AI processing of call audio/transcript | D7, D9 | Art.6(1)(b) for order-taking; separate basis for secondary analytics | Instrumental to contract; training reuse NOT covered | `Needs legal review:` prohibit vendor training on content unless separate consent |
| P4 | Call recording (D8) | D8 | Art.6(1)(a) consent + §201 StGB considerations | DE law treats recording of spoken word restrictively | `Needs legal review:` default OFF; explicit script required if enabled |
| P5 | Courier assignment and routing | D3, D5 subset, D11, D12 if any | (b) for customer side; (f)+BDSG §26 for staff | Need-to-know scoping | `Needs legal review:` works-council |
| P6 | Owner dashboard analytics | D15; derived from D5,D6,D10,D11 | Art.6(1)(f) | Per-courier KPIs touch employee monitoring thresholds | `Needs legal review:` BDSG §26, BetrVG §87(1) Nr.6 |
| P7 | Support / troubleshooting access | D9, D17 | Art.6(1)(f) with LIA + break-glass | Fixing errors / disputes | `Recommendation:` reason-code gated; `Needs legal review:` scope |

`Open question:` Marketing use of CRM — explicitly excluded for v1 unless PO states otherwise (UWG §7 implications).

---

## 3. Consent / disclosure design for Germany

Anchors invoked as inputs — ALL `Candidate (verify):` identifiers for counsel, not legal conclusions by this role, and ALL `Needs legal review:`: DSGVO Art.13; EU AI Act transparency (`Candidate (verify):` Art.52); §201 StGB (Vertraulichkeit des Wortes); TKG — telecoms secrecy; BDSG §26 for employees.

### 3.1 Principles at call opening
- Disclose AI nature in first utterance before any order content.
- Keep disclosure short; put long-form notice on durable medium (website Datenschutzerklärung, menu insert, optional SMS link).
- Call-recording OFF in v1; disclosure must not claim or imply recording.
- Provide handover path ("Mitarbeiter sprechen") at any time.
- Capture D18 (acknowledgement) without storing audio: timestamp + script-version id + continued-call marker.

### 3.2 Proposed verbal opening (DE, short form) — `Needs legal review:`

"Guten Tag, hier ist der automatische Bestell-Assistent von [Restaurant]. Sie sprechen mit einer KI. Dieses Gespräch wird nicht aufgezeichnet. Ich speichere nur die Angaben, die für Ihre Bestellung notwendig sind. Weitere Informationen zum Datenschutz finden Sie unter [URL]. Möchten Sie bestellen, oder soll ich Sie mit einem Mitarbeiter verbinden?"

`Needs legal review:` whether AI-Act wording suffices; whether Art.13 can be split into short verbal + durable long-form (layered notice); whether "not recorded" is accurate end-to-end; whether CRM reuse requires separate statement before any recital.

### 3.3 CRM-reuse mini-script (before reciting stored address) — `Needs legal review:`

"Darf ich fragen, mit wem ich spreche? … Danke, [Name]. Soll ich die bei uns gespeicherte Lieferadresse verwenden, oder möchten Sie eine andere Adresse angeben?"

Rule: do NOT recite stored address until spoken name matches stored name within defined similarity threshold; otherwise fall back to "please tell me the delivery address".

`Open question:` Threshold for name match (exact vs. fuzzy)? False positive here is the key control for R-B.
`Recommendation:` Caller-supplied address every N-th call or on any confidence drop; log decision (D18).

### 3.4 Opt-out / withdrawal
- Caller can say "Mitarbeiter" / "Mensch" / "Datenschutz" to trigger handover + verbal pointer to DSR channel.
- Withdrawal of CRM consent (if basis is (a)) must be exercisable by phone; current order basis is (b) and continues.

---

## 4. Retention schedule (proposed)

All values `Assumption:` unless flagged.

| Bucket | Data | Duration | Rationale | Flag |
|---|---|---|---|---|
| Transient | D7 audio stream, STT buffers | Discard end-of-call; in-memory only | Avoid becoming controller of audio | `Assumption:` |
| Short | D9 raw transcript (if kept), D17 access events | 7–30 days | Dispute window; limit exposure | `Assumption:` |
| Short-medium | D10 state transitions, D14 auth events | 90–180 days | Operational analytics + incidents | `Assumption:` |
| Medium | D15 dashboard aggregates, D19 DSR records | 24–36 months | Reporting; accountability | `Assumption:` |
| CRM | D1–D4 CRM | 24 months inactivity → delete, or on withdrawal if (a) | Minimisation vs. reuse interest | `Needs legal review:` |
| Accounting | D6, D16, invoices | `Candidate (verify):` ~10 years under HGB §257 / AO §147 depending on document type | Tax/commercial record-keeping | `Needs legal review:` — do not hard-code without counsel |
| Employment | D11, D13 | Employment + statutory follow-on | BDSG §26 and employment law | `Needs legal review:` |
| Backups | D20 | Rolling encrypted window (e.g., 30 days) + documented erasure interaction | Right-to-erasure interaction | `Needs legal review:` |
| Call recording | D8 | Default n/a; if ON ≤30 d + explicit consent | Minimisation; §201 StGB caution | `Needs legal review:` |

`Recommendation:` Split operational order copy (short cycle) from accounting archive copy (append-only, long retention).

`Open question:` Is a B2C invoice generated per phone order? Different retention duty if receipt only — `Needs legal review:`.

---

## 5. Deletion / rectification / access DSR flows (Art.15–21)

### 5.1 Rights mapping

| Right | Caller ask | Where data lives | Blockers | Who authorises |
|---|---|---|---|---|
| Art.15 Access | "What do you have on me?" | CRM (D4), order history (D5,D6,D10), transcripts (D9), DSR tracker (D19) | Identity verification | DPO / owner |
| Art.16 Rectification | "My address is wrong" | CRM, open orders | None material | Confirmer + DPO notified |
| Art.17 Erasure | "Delete me" | CRM, transcripts, dashboards | Open order; accounting (D6, D16) | DPO + owner |
| Art.18 Restriction | "Stop processing" | CRM flag; suppress reuse | Must not break ongoing order | DPO |
| Art.20 Portability | "Export my data" | CRM + order history | Only (a)/(b)-based data | DPO |
| Art.21 Objection | "Stop CRM reuse" | CRM | Current order on (b) continues | DPO |

### 5.2 Flow
1. Intake: email + phone + optional web form; logged in D19.
2. Identity verification: phone + knowledge check — `Needs legal review:`.
3. Scope determination across CRM, order service, transcripts, DSR tracker, backups.
4. Action: soft-delete + tombstone + hard-delete-after-grace; accounting archive kept with legal-hold flag; backup-cycle materialisation scheduled.
5. Response within statutory deadline; content and timestamp in D19.
6. Objection to P2 reuse: set "do-not-prefill" flag; AI treats caller as new on every call.

`Recommendation:` Soft-delete + tombstone + hard-delete-after-grace, not instant irreversible delete; but hard delete must actually happen; perpetual tombstone is not Art.17-compliant.
`Needs legal review:` Backup-and-deletion defensibility.

---

## 6. Processor / sub-processor map

| Category | Role | Data touched | DPA (Art.28) | Hosting preference | Transfer concern |
|---|---|---|---|---|---|
| Telephony / PSTN termination | Processor | D1, D7, D8 | Yes | DE/EU | Signalling may transit non-EU — `Needs legal review:` |
| STT | Processor | D7 → D9 | Yes | EU strongly preferred; `Needs legal review:` if US | Training-on-content must be contractually forbidden |
| LLM | Processor | D9 text, D5 | Yes | EU preferred; `Needs legal review:` if US | SCCs + TIA if non-EU; prohibit training reuse |
| TTS | Processor | Prompt text (minimal PII) | Yes | EU preferred | Lower risk |
| Hosting (app, DB) | Processor | Most data | Yes | DE or EU-only | SCCs if non-EU |
| Logging / observability | Processor | Logs (PII-redacted) | Yes | EU preferred | Transcript fragments in logs risk — see §7 |
| SMS / notifications | Processor | D1, D2 | Yes | EU preferred | v1 may defer |
| Dashboard analytics | Processor or in-house | D15 | Yes if external | EU-only | Avoid US-based with embedded identifiers |
| Payment | Processor or indep. controller | D16 | `Needs legal review:` joint-controller vs. independent-controller analysis for PSP; scoping prompt, not conclusion | EU | PCI scope separate |
| Map / navigator | Not a processor if only deep-link | n/a | n/a | n/a | Keep deep-link to avoid becoming controller of location |

`Needs legal review:` For US-based cloud/AI vendors: EU-US DPF status; SCCs + TIA; supplementary measures.
`Recommendation:` v1 scope with "EU-region, EU-entity, EU-support" filter; non-EU as backup pending legal review.
`Open question:` Hard ban on US sub-processors by PO?

---

## 7. Technical and organisational measures (TOMs)

### 7.1 Encryption & key management
- TLS 1.2+ in transit; AES-256 at rest for CRM, order, transcript, backups.
- Managed KMS, per-env keys, dual control for prod, documented rotation.
- Call-audio streams: not written to disk at rest by default.

### 7.2 Access control (ties to FR-20)
- Roles: AI runtime, confirmer, kitchen, courier, owner/admin, DPO.
- Need-to-know: courier sees only assigned ticket subset; kitchen sees items only; confirmer sees order + CRM context required; owner dashboard sees aggregates + staff-level identifiers for operations.
- MFA for owner/admin and break-glass; strong auth for staff.
- Session timeouts; device binding for courier app `Recommendation:`.

### 7.3 Audit logging
- Separate append-only audit stream (D17) for: break-glass transcript access; CRM address-recital events (D18); DSR actions; admin/role changes.
- Audit log references by id, not content.
- `Needs legal review:` audit retention vs. BDSG §26 and co-determination.

### 7.4 PII redaction in logs/traces
- Mandatory redaction at log ingestion for phone, name, full address, total.
- Forbid free-form concatenation of transcript into log messages.
- Synthetic-PII canaries to detect redaction regressions.

### 7.5 Test-data strategy
- No real caller data in dev/staging ever.
- Synthetic datasets for dialog variants, address formats, dialects.
- Same TOMs for pre-prod; no wide-open staging.

### 7.6 Backup/retention alignment
- Backups follow §4 bucket; documented interaction with Art.17; see `Needs legal review:` in §5.2.
- Encrypted; restore operators only.

### 7.7 Incident response outline
- Triggers: transcript leak, CRM leak, AI misuse (social-engineering recital), vendor notification.
- Internal targets aligned to Art.33 72h duty; `Needs legal review:` which Landesdatenschutzbehörde applies.
- Caller notification (Art.34) criteria defined up front.
- Post-incident root-cause; retention of incident record; lessons into TOMs.

`Open question:` Does the restaurant have an incident-response contact or (external) DPO? Common for SMB.

---

## 8. DPIA scoping

### 8.1 Required?
High likelihood under Art.35(3) and typical supervisory criteria: systematic monitoring of callers; innovative LLM voice tech; voice can carry biometric characteristics (`Needs legal review:`).

`Recommendation:` Treat DPIA as required for v1 pre-pilot; if counsel later disagrees, artefact still serves Art.24/32 accountability.

### 8.2 Scope
- Purposes P1–P7.
- Data categories D1–D20.
- Vendors + transfers (§6).
- Risks §9.
- TOMs §7.
- Lawful bases §2 post-review.
- Consultation: DPO; `Needs legal review:` whether Art.36 consultation with authority is required.

### 8.3 DPIA open questions
- Does any vendor process voice as biometric identifier? If yes Art.9 applies.
- Does AI output ever decide with legal/similar effect (Art.22)? Confirmer must be meaningful, not rubber-stamp.
- Vulnerable callers (elderly unfamiliar with AI, minors)?

### 8.4 Evidence
- Art.30 register entries per P1–P7.
- DPAs with each processor.
- SCCs + TIA for any non-EU transfer.
- Script versions + D18 log.
- Audit logs (D17).
- Deletion-run reports.

---

## 9. Specific risks and mitigations

| ID | Risk | L | I | Mitigation |
|---|---|---|---|---|
| R-A | Voice biometrics inadvertently collected | M | H | Contract forbids biometric extraction/speaker-ID; audit vendor terms; prefer streaming STT without storage |
| R-B | Cross-caller CRM leakage (address recited to wrong caller) | M | H | Verbal name-match before recital; confidence threshold; caller-supplied fallback; D18 audit |
| R-C | Long transcripts in STT/LLM provider logs | M | H | DPA no-retention / no-training; EU vendors with zero-retention; minimise shipped utterances; vendor audits |
| R-D | Metadata leakage via courier app | M | M | Courier default view = first name + address + items (no phone surfaced). Phone revealed only on explicit "Anrufen" tap with audit event — reconciled with architecture §7.5 and UX §5.3; `Needs legal review:` for whether reason-code gating is required |
| R-E | Dashboard oversharing of PII; covert staff monitoring | M | H | Aggregate-only; staff KPIs flagged for BDSG §26; no caller identifiers in rows; drill-down requires reason code |
| R-F | §201 StGB exposure if recording accidentally enabled | L | H | Hard-default-OFF flag; architecture test persistence disabled; `Needs legal review:` script wording |
| R-G | Vendor training on caller content | M | H | DPA clause; attestations; "no training" default vendors |
| R-H | DSR non-responsiveness | M | M | DSR tracker + SLA workflow + owner-DPO escalation |
| R-I | Backup resurrection of deleted data | M | M | Policy per §5.2; rolling window; redaction/exclusion on restore |
| R-J | Confirmer becomes rubber-stamp → Art.22 | M | M | UX forces meaningful review; audit edit/reject rate; training |
| R-K | Caller claims never heard disclosure | L–M | M | D18 acknowledgement + script-version id |
| R-L | Pseudonymisation drift across stores | M | M | Single CRM id; references by id in order service, transcripts, DSR |

---

## 10. Open questions for Product Owner and recommended ADRs

### 10.1 Open questions (privacy-blocking)
- OQ-PR1 Call-recording OFF by default + consent-gated feature-flag — confirm?
- OQ-PR2 CRM reuse basis — legitimate interest (LIA) vs. consent?
- OQ-PR3 Marketing use of CRM — in or out of v1? (Design assumes OUT.)
- OQ-PR4 Courier location — deep-link only, or central tracking?
- OQ-PR5 Hosting region — EU-only vs. DE-only?
- OQ-PR6 US vendors with SCCs vs. EU-only shortlist for v1?
- OQ-PR7 Works-council / employee rep for P6 KPIs?
- OQ-PR8 External DPO engaged?
- OQ-PR9 DSR intake channel(s) + SLA?
- OQ-PR10 Raw-transcript retention vs. structured-order-only?

### 10.2 Recommended ADRs
- ADR-P-01 Hosting region for v1 (DE/EU/EU-with-US-sub-processors). Driver: Art.44–49.
- ADR-P-02 STT/LLM/TTS vendor family (EU-first vs US-with-SCCs). Driver: R-A, R-C, R-G.
- ADR-P-03 Call-audio handling (streaming only; recording feature-off). Driver: §201 StGB, R-F.
- ADR-P-04 Raw-transcript retention (N days with redaction vs. discard after extraction). Driver: §4, R-C.
- ADR-P-05 CRM lawful basis + opt-out (LI vs. consent). Driver: P2.
- ADR-P-06 Verbal verification threshold T before address recital. Driver: R-B.
- ADR-P-07 Courier location model (deep-link vs. tracking). Driver: R-D, BDSG §26.
- ADR-P-08 Dashboard metric model (aggregates + staff-KPI scope). Driver: R-E, BDSG §26 / BetrVG §87(1) Nr.6.
- ADR-P-09 Accounting archive separation (dual-store). Driver: §4, HGB §257 / AO §147 territory.
- ADR-P-10 Logging + redaction gateway. Driver: R-C.
- ADR-P-11 DSR workflow + backup erasure policy. Driver: §5, R-I.
- ADR-P-12 AI disclosure script + acknowledgement signal (layered notice; D18 no audio). Driver: §3, R-K.
- ADR-P-13 DPIA governance (owner + reviewer named). Driver: §8.

### 10.3 Suggested next handoff
Coordinator forwards to Software Architect (lift ADR-P-01..P-13), UX (align to §7.2 need-to-know + §9 R-D/R-E), Voice (finalise §3 scripts + name-match in R-B), Reality Checker after architecture.

`Recommendation:` Do not proceed to pilot — even friends-and-family — until OQ-PR1..PR10 are PO-answered and ADR-P-01..P-13 decided and legally reviewed.

End of memo.
