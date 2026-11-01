# Phase-0 Business Strategy Memo — AI Phone-Ordering Assistant (Germany)

**Scope:** NEXUS Phase 0 discovery, business perspective. Design-only; no vendor commitments, no implementation, no paid services.
**Primary input:** `brief/restaurant-idea.md`
**Author role:** Business Strategist (subagent)
**Subagent call id:** aa2afa5b6caff9e52
**Date:** 2026-11-01

Conventions: `Fact from brief:`, `Assumption:`, `Open question:`, `Recommendation:` as in the product-discovery memo.

---

## 1. Market

**Fact from brief:** AI phone assistant takes voice orders, matches callers to CRM by phone, pushes confirmed orders to kitchen, dispatches couriers with routing, feeds dashboard. Target market: Germany.

**Target customer archetypes (hypotheses, priority order):**
- **A — Independent single-location delivery restaurant (SMB).** Pizza, döner, sushi, Asian, Italian; owner-operator; 1–3 phone lines; heavy phone orders; basic POS, no call automation. `Assumption:` Most pain-rich, under-served; natural first wedge.
- **B — Small local chain (2–8 locations).** Central branding, decentral ops; may have call center. Higher WTP, longer cycle. `Assumption:` Later wave.
- **C — Ghost/cloud kitchen.** Platform-native; low phone volume; smaller wedge. `Assumption:` Lower initial fit.
- **D — Full-service dine-in.** Phone used for reservations; out of brief scope.

`Open question:` Delivery-first vs. include reservation-heavy dine-in? Brief implies delivery.
`Open question:` Regional focus (one city/state) vs. national from day one?
`Assumption:` Primary voice language: German; plausible secondary: Turkish, Arabic, Italian, English.
`Open question:` Dialect robustness (Bairisch, Schwäbisch, Kölsch, Berlinerisch) priority for v1?

---

## 2. Competitive Landscape (qualitative)

- **Status quo — human staff.** Zero software cost; weak during rush, mis-heard orders, staff cost, no CRM memory, limited after-hours.
- **POS/ordering-system add-ons.** `Assumption:` Some German POS/online-ordering vendors offer caller-ID popup or missed-call callback; LLM-grade dialog not standard. To be verified.
- **Third-party delivery marketplaces (Lieferando/Just Eat Takeaway, Uber Eats, Wolt).** Shift orders off phone; high commission; loss of direct relationship. Our product is complementary.
- **Generic AI voice-agent vendors.** Growing category; mostly English-first, not integrated with kitchen/courier. `Assumption:` Few are German-first and restaurant-vertical.
- **Call-forwarding / outsourced call centers.** Operational, cost-variable, language-constrained.
- **DIY no-code bots (IVR/DTMF).** Cheap, poor UX, cannot handle free-form.

**Differentiation hypotheses to test:**
1. German-first voice UX tuned to restaurant ordering.
2. End-to-end flow (not just voicebot — kitchen + courier + dashboard).
3. CRM-by-phone reduces friction, raises AOV.
4. Human-in-the-loop confirmation lowers trust barrier.

`Open question:` Which differentiators are load-bearing for PO?

---

## 3. Value Proposition Hypotheses (falsifiable)

- **H1 Capture.** Assistant captures orders lost to unanswered peak calls. Confirm: answered-rate up, abandoned-rate down. Deny: no change after 4 weeks.
- **H2 Labor relief.** Staff phone time drops per shift. Confirm: tracked reduction, owner interviews. Deny: staff still double-check all AI orders.
- **H3 Order accuracy.** AI + staff confirmation ≤ errors vs. human. Confirm: complaints/refunds ≤ baseline. Deny: errors spike or confirm step bypassed.
- **H4 Repeat uplift.** CRM recognition raises reorder frequency within 90d. Confirm: matched cohort > unmatched. Deny: no cohort diff.
- **H5 Direct-channel defense.** Phone-order share stable or up vs. aggregator share. Confirm: direct share stable/up. Deny: continued decline.

`Open question:` Which of H1–H5 is north-star for PO?

---

## 4. Business Model Options

Pricing values deferred — all `Assumption:`.

- **A. Flat SaaS per location.** Easy to sell; underprices heavy users.
- **B. Per-call / per-minute.** Aligns to COGS; hard to budget; peak-day spike risk.
- **C. Hybrid base + usage overage.** Common SaaS pattern; usually best fit.
- **D. Revenue share on captured orders.** Strong alignment story; needs trusted attribution; complex invoicing; "another Lieferando" perception risk.
- **E. White-label / OEM to POS vendor.** Fast distribution via partner; margin compression; partner concentration risk.
- **F. One-time license + support.** Rare in SMB gastro.

`Recommendation:` Keep A, C, D on table for later quantitative modelling; defer E; de-prioritise B standalone and F.

---

## 5. Unit-Economics Drivers (qualitative)

**Variable (COGS):**
- Telephony inbound (DID + per-min) — DE PSTN termination.
- ASR (per audio minute) — German quality.
- LLM (per token) — prompt + dialog + extraction.
- TTS (per character/second).
- CRM/database per call.
- PSTN outbound (SMS/callback) if used.

**Fixed:**
- App hosting (API, workers, dashboard).
- Observability, logging, backup.
- Support (scales with customers).
- Compliance overhead (DSGVO docs, DPAs, hosting-region constraints).
- Sales/onboarding labor per restaurant.

**Ratios to monitor (no targets):** cost per completed vs. non-completed call; gross margin per location/month; onboarding payback; escalation rate.

`Open question:` Which COGS component dominates at expected call lengths?

---

## 6. Go-to-Market Hypotheses

- **First-wedge segment:** Independent delivery-focused restaurants (pizza/döner/Asian) in one German metro, 1–2 locations, overloaded phone-order volume.
- **Channels to test:**
  1. Direct outbound to 20–50 restaurants in one city; founder-led.
  2. POS/online-ordering partner as module.
  3. DEHOGA for awareness.
  4. Referral from early reference restaurants.
- **Positioning:** "Takes every call, remembers every regular, keeps your kitchen flowing — without replacing your team." Against missed-call tax, not aggregators.
- **Pilot design:** 3–5 pilots, signed criteria tied to H1–H3, 6–12 weeks.

`Open question:` Target city / restaurants already identified?
`Open question:` POS-partner path vs. direct-sales preference?

---

## 7. Strategic Risks and Dependencies

- **Regulatory (DE, EU).** `Needs legal review:` on every statutory assertion in this bullet. All article/§ references are `Candidate (verify):` identifiers for counsel, not legal conclusions by this role.
  - `Needs legal review:` DSGVO (GDPR) applies to voice recordings, transcripts, address, phone as personal data; `Candidate (verify):` strict call-recording consent regime in Germany interacts with §201 StGB.
  - `Needs legal review:` TTDSG telecoms privacy possibly applies to call audio handling.
  - `Needs legal review:` EU AI Act transparency obligation reading when a natural person interacts with an AI system (`Candidate (verify):` Art.52). `Assumption:` not "high-risk" under current readings — to be reconfirmed by counsel.
  - `Needs legal review:` LMIV / EU 1169/2011 allergen-information duties if AI discusses menu content.
- **Cultural / adoption.** DE consumer distrust of phone AI; staff resistance. Mitigated partly by confirmation step.
- **Platform/vendor risk.** ASR/LLM/TTS/telephony pricing, outages, model deprecations, regional availability.
- **Data-residency / hosting.** EU-only or DE-only commonly required.
- **Incumbent pushback.** Lieferando/Uber Eats low immediate threat (we strengthen direct channel).
- **POS integration risk.** Closed POS APIs grow integration debt per customer.
- **Liability for wrong orders.** Allergens, address, totals.
- **Language quality risk.** Mediocre German/dialect / robotic TTS kills conversion.
- **Labor sentiment.** "Replace staff" framing risk; "help overloaded staff" safer.

---

## 8. Strategic Open Questions for Product Owner

1. Primary north-star hypothesis (H1–H5)?
2. Delivery-first only, or also reservations and takeaway without delivery?
3. Target region / candidate restaurants for pilot?
4. Non-German languages at launch — required?
5. Preferred commercial model direction (SaaS / hybrid / rev-share)?
6. POS-partner distribution appetite?
7. Hard data-residency constraints?
8. Call-recording retention acceptable, how long, or transcripts only?
9. Liability allocation in pilot contracts?
10. Budget envelope and timeline for pilot?

---

## 9. Falsifiable Business Hypotheses + Proposed Experiments

Design-only in Phase 0. Execution requires PO.

- **BH1 Pain severity:** Interview 10–15 owners. Confirm: ≥60% rank missed-calls top-3. Deny: <30%.
- **BH2 Willingness to try:** Pilot sign-ups from interviews. Confirm: ≥3 LOIs / 15. Deny: <2.
- **BH3 Replacement effect:** Pre/post over 4–8 weeks. Confirm: order count up, no staff-friction spike. Deny: no uplift / friction.
- **BH4 Trust floor:** A/B abandon-rate after AI disclosure. Confirm: delta within tolerance. Deny: material increase.
- **BH5 Willingness to pay:** Post-pilot conversion. Confirm: ≥50% convert at price covering variable+margin. Deny: <25%.
- **BH6 Differentiation:** Side-by-side demo vs. generic AI receptionist. Confirm: clear preference citing menu/CRM/kitchen integration. Deny: no distinction.

---

## 10. Handoffs

- To Product: reconcile OQs into prioritised scope; align H1–H5 with KPIs.
- To Software Architecture: translate §5 into cost-aware component inventory with vendor-category options and hosting-region constraints.
- To Voice: confirm feasibility of German-first voice UX, disclosure, dialect scope, barge-in from H3/BH4.
- To UX: staff-confirmation and courier flows that preserve H2/H3.
- To Privacy: DSGVO, TTDSG, EU AI Act transparency, call-recording consent, data lifecycle, residency options, LMIV allergen scoping.
- To Reality-Checker (after full packet): audit invented stats, un-flagged assumptions, scope creep, consistency.
- To PO: 10 strategic OQs gate the next decisions.

---
End of memo.
