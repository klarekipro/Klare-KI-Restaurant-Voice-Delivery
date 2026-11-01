# Phase 0 — Product Discovery: AI Phone Assistant for Restaurant (Germany)

Author role: Product Manager (design-only, Phase 0)
Source of truth: `brief/restaurant-idea.md`
Scope boundary: `docs/experiment/PROTOCOL.md` (NEXUS Phase 0 & 1 only; no implementation, no production, no paid services, no invented user research)
Subagent call id: a4d4b37fe8b3f76ff
Date: 2026-11-01

Document conventions:
- `Fact from brief:` quotes/references the brief by line number.
- `Assumption:` an inference by this role, not stated in the brief.
- `Open question:` unresolved; requires Product Owner input.
- `Recommendation:` suggested direction, not an approval.

No user interviews, surveys, analytics, competitive studies or market data were performed. Any such statements elsewhere would be fabricated and must not be introduced here.

---

## 1. Problem

`Fact from brief:` (line 3) "AI-телефонный ассистент для ресторана принимает заказы, фиксирует состав заказа, контактные данные, телефон и адрес клиента."
`Fact from brief:` (line 3) "Существующие клиенты находятся в базе по номеру телефона; их данные предлагаются для подтверждения. Новые клиенты добавляются в CRM."
`Fact from brief:` (line 5) "Сотрудник ресторана проверяет и подтверждает заказ. После подтверждения заказ отправляется на кухню."
`Fact from brief:` (lines 7–9) kitchen marks ready, courier is assigned, courier closes order after delivery.
`Fact from brief:` (line 11) a main dashboard shows cooked/delivered counts per courier, totals, day summary.
`Fact from brief:` (line 13) initial market is Germany.

Problem statement (synthesized, no new facts introduced):
A restaurant in Germany needs an end-to-end flow that lets an AI voice assistant answer phone orders, reuse known-customer data via phone-number lookup, and hand off a confirmed order through a staff review step to kitchen preparation, courier dispatch with navigation, and finally delivery closure — with a dashboard summarizing daily operational KPIs.

Business outcome the solution must enable (synthesized from brief verbs: "принимает", "фиксирует", "проверяет и подтверждает", "отмечает готовность", "назначается", "закрывает", "показывает"):
- Capture inbound phone demand without requiring a human to answer every call.
- Reduce order-taking error by reusing CRM data for repeat callers.
- Provide a reliable chain of custody for each order from call to delivery closure.
- Give the owner/manager visibility of daily throughput and courier performance.

`Assumption:` The implicit business value is labor relief on the phone, higher order capture rate during peaks, and faster/cleaner handoff to kitchen and couriers. The brief does not quantify any of these.
`Open question:` What is the single most important outcome for the owner (call capture rate? labor cost? ticket accuracy? average delivery time?)? Priority among these shapes requirements.

---

## 2. Stakeholders

Derived strictly from the brief, with roles added only where the brief implies them.

| Stakeholder | Evidence | Role in flow |
|---|---|---|
| Caller / customer (new) | Line 3: "Новые клиенты добавляются в CRM." | Places order by phone; provides name, phone, address. |
| Caller / customer (repeat) | Line 3: "Существующие клиенты находятся в базе по номеру телефона; их данные предлагаются для подтверждения." | Places order; confirms stored data. |
| Restaurant staff member (order confirmer) | Line 5: "Сотрудник ресторана проверяет и подтверждает заказ." | Reviews and confirms AI-captured order before kitchen dispatch. |
| Kitchen | Line 7: "Кухня отмечает готовность заказа." | Prepares order; marks ready. |
| Courier | Lines 7–9: assigned, uses navigator, closes order after delivery. | Picks up and delivers; closes order. |
| Owner / manager | Line 11: dashboard with counts, sums, day totals. | Monitors operational KPIs. |

`Assumption:` "Сотрудник ресторана" may be a shift lead, host, or phone operator role; the brief does not name it. A single person could play multiple roles (e.g., owner + confirmer) in a small restaurant.
`Open question:` Who exactly plays the confirmer role (dedicated operator vs. shift lead vs. owner)? Does the restaurant have one or many simultaneous confirmers?
`Open question:` Is the kitchen interaction via a shared display, individual device, or printer? Brief is silent.
`Open question:` Are couriers employees or external (platform)? Device ownership and auth model differ.

---

## 3. Jobs-to-be-Done (JTBD) and primary success criteria

### 3.1 Caller (new)
JTBD: "When I call the restaurant, I want to place an order quickly and be understood, so I receive the food I expect at my address."
Primary success criteria (candidate):
- Order captured correctly on first attempt (no callback for clarification).
- Call ends with a clear confirmation of items, price, address, and ETA (ETA mention is an `Assumption:`; brief doesn't require ETA).

### 3.2 Caller (repeat)
JTBD: "When I call again, I want the restaurant to recognize me, so I don't have to repeat my address and phone."
Primary success criteria:
- Known-customer path triggers on phone-number match (line 3).
- Caller confirms (not re-dictates) stored details.

### 3.3 Restaurant staff / confirmer
JTBD: "When the AI has taken an order, I want to review it quickly and release it to the kitchen, so throughput is maintained without wrong orders reaching prep."
Primary success criteria:
- Review step surfaces the full order and customer data in one view.
- Confirm/edit/reject action is possible before kitchen dispatch (line 5).

### 3.4 Kitchen
JTBD: "When a confirmed order arrives, I want to see what to cook and mark it ready, so couriers know when to pick it up."
Primary success criteria:
- Order appears after confirmation (line 7 implies order flows to kitchen only after confirmation).
- "Ready" state is reachable in one action.

### 3.5 Courier
JTBD: "When an order is ready, I want it on my phone with the address and a one-tap route, so I can deliver efficiently and close it when done."
Primary success criteria:
- Assigned order shows delivery data and opens navigator (line 7).
- Courier can close order after delivery (line 9).

### 3.6 Owner / manager
JTBD: "At any point in the day, I want to see how many orders were cooked, delivered per courier, their value, and day totals, so I can run the business."
Primary success criteria:
- Dashboard shows the four signals named in line 11.

---

## 4. In-scope and out-of-scope capabilities (strict brief derivation)

### 4.1 In-scope

| # | `Fact from brief:` quote (line) | Interpretation |
|---|---|---|
| C1 | "AI-телефонный ассистент для ресторана принимает заказы" (3) | Inbound voice call handling by AI; order intake dialogue in natural language. |
| C2 | "фиксирует состав заказа, контактные данные, телефон и адрес клиента" (3) | Structured capture of items, name, phone, address during the call. |
| C3 | "Существующие клиенты находятся в базе по номеру телефона; их данные предлагаются для подтверждения." (3) | CRM lookup keyed by caller phone number; present stored data for confirmation. |
| C4 | "Новые клиенты добавляются в CRM." (3) | Create a CRM record for first-time callers. |
| C5 | "Сотрудник ресторана проверяет и подтверждает заказ." (5) | Human-in-the-loop confirmation UI/workflow. |
| C6 | "После подтверждения заказ отправляется на кухню." (5) | Confirmed orders routed to a kitchen view/queue. |
| C7 | "Кухня отмечает готовность заказа." (7) | Kitchen marks an order "ready". |
| C8 | "Готовый заказ назначается курьеру" (7) | Assignment of ready order to a courier. |
| C9 | "появляется на его телефоне с данными доставки" (7) | Mobile courier view with delivery details. |
| C10 | "возможностью открыть маршрут в навигаторе" (7) | Deep-link / handoff to a navigation app. |
| C11 | "После выполнения доставки курьер закрывает заказ." (9) | Courier-triggered closure action. |
| C12 | "Главный дашборд показывает количество приготовленных заказов, доставленных заказов каждого курьера, суммы заказов и итоги дня." (11) | Dashboard with: cooked count, delivered count per courier, order sums, day totals. |
| C13 | "Исходный рынок — Германия." (13) | Germany is the initial market (localization, legal, operational norms apply). |

### 4.2 Out-of-scope (not mentioned in brief)

- Payment collection on the call. `Open question:` phone / delivery / external link?
- Table reservations, in-restaurant pickup, dine-in.
- Menu management UI, pricing updates, specials/promos. `Open question:` menu source?
- Multi-location / franchise support.
- Multi-restaurant tenancy.
- Loyalty programs, marketing SMS/email, feedback collection.
- Dispatch optimization (multi-stop routing, courier scoring).
- Integration with third-party delivery platforms (Lieferando/Uber Eats etc.).
- Returns/refunds, complaints handling.
- Printed kitchen tickets, POS integration.
- Opening-hours logic, holiday handling, out-of-hours fallback. `Open question:` behavior outside opening hours or when all couriers busy?
- Caller authentication/anti-fraud for CRM reuse. `Open question:` phone-match sufficient?
- Call recording / transcript retention policy. (GDPR relevance — see §9.)

---

## 5. Functional requirement candidates

| ID | Requirement | Priority | Reasoning |
|---|---|---|---|
| FR-1 | AI voice agent answers inbound calls and conducts natural-language order dialogue. | MUST | Core premise, line 3. |
| FR-2 | Capture order line items (dish, quantity, modifiers) as structured data. | MUST | Line 3; modifiers `assumption`. |
| FR-3 | Capture caller name, phone, address. | MUST | Line 3. |
| FR-4 | CRM lookup by caller phone number (CLI/ANI) at call start. | MUST | Line 3. |
| FR-5 | For matched caller, present stored data for verbal confirmation and allow correction. | MUST | Line 3; correction path `assumption`. |
| FR-6 | For unmatched caller, create new CRM record. | MUST | Line 3. |
| FR-7 | Every AI-captured order presented to staff confirmer before kitchen. | MUST | Line 5. |
| FR-8 | Confirmer can approve/edit/reject order. Edit/reject `assumption`. | MUST approve, SHOULD edit/reject | Line 5. |
| FR-9 | On confirmation, order dispatched to kitchen view/queue. | MUST | Line 5. |
| FR-10 | Kitchen marks order "ready". | MUST | Line 7. |
| FR-11 | Ready order is assigned to a courier. | MUST | Line 7; `Open question:` manual/auto/hybrid. |
| FR-12 | Assigned order appears on courier mobile with delivery details. | MUST | Line 7. |
| FR-13 | Courier app has one-tap action to open route in external navigator. | MUST | Line 7; external navigator `assumption`. |
| FR-14 | Courier closes/completes order upon delivery. | MUST | Line 9. |
| FR-15 | Dashboard displays prepared count, delivered-per-courier, order sums, day totals. | MUST | Line 11. |
| FR-16 | Operate in German primarily. | MUST DE / COULD EN | Line 13; language set PO input. |
| FR-17 | Support concurrent inbound calls. `assumption`. | SHOULD | Depends on peak volume. |
| FR-18 | Handle out-of-hours calls. `assumption`. | SHOULD | Operationally necessary. |
| FR-19 | Surface order state (new → confirmed → in-kitchen → ready → assigned → delivered → closed) across views. | MUST | Implied lines 5–9. |
| FR-20 | Authenticate staff users with roles. `assumption`. | MUST | Prerequisite for multi-role system. |
| FR-21 | Log call/order events for traceability and dashboard aggregation. `assumption`. | SHOULD | Implied by FR-15. |
| FR-22 | Allow human handover during a call. `assumption`. | SHOULD | Standard voice-assistant practice. |
| FR-23 | Produce verbal order summary + confirmation at end of call. `assumption`. | SHOULD | Error reduction. |
| FR-24 | Record order total (sum). | MUST | Implied by line 11; requires menu prices. |

`Open question:` Does AI quote prices/totals during the call?
`Open question:` Must AI handle allergies/intolerances / dietary notes?
`Open question:` Does confirm step send anything back to caller (SMS/call-back)?

---

## 6. Non-functional requirement candidates

| ID | NFR | Target / Note |
|---|---|---|
| NFR-1 | Voice latency (end-of-speech → AI response) | `unknown — needs PO input`; conversational threshold typically sub-second. |
| NFR-2 | ASR accuracy on German (incl. accents) | `unknown — needs PO input`. |
| NFR-3 | Call concurrency | `unknown — needs PO input`. |
| NFR-4 | Order-to-kitchen latency post-confirm | `unknown — needs PO input`. |
| NFR-5 | System availability during opening hours | `unknown — needs PO input`. |
| NFR-6 | Business continuity if voice provider down | `unknown — needs PO input`; fallback needed. |
| NFR-7 | Localization | German primary; secondary `unknown`. |
| NFR-8 | Accessibility | `unknown — needs PO input`; WCAG AA desirable for staff UIs. |
| NFR-9 | Data residency and GDPR compliance | `unknown — needs PO input`; GDPR applies. |
| NFR-10 | Call recording retention + consent | `unknown — needs PO input`; German law. |
| NFR-11 | PII minimization in CRM | Only name/phone/address per brief. |
| NFR-12 | Mobile responsiveness for courier | Derived from line 7. |
| NFR-13 | Dashboard freshness | `unknown — needs PO input`; near-real-time implied. |
| NFR-14 | Observability / auditability | `unknown — needs PO input`; needed for disputes. |
| NFR-15 | Security of staff auth and sessions | `unknown — needs PO input`. |

---

## 7. Measurable hypotheses and success metrics

All targets below are `Assumption:` ranges.

| ID | Hypothesis | Metric | Target (`assumption`) |
|---|---|---|---|
| H-1 | AI handles majority of inbound orders without human. | % calls completed by AI | 60–85% |
| H-2 | Repeat callers complete faster via CRM reuse. | Mean call duration repeat vs new | repeat ≤ 60% of new |
| H-3 | First-attempt order accuracy high. | % confirmed without edits | ≥ 80% |
| H-4 | Kitchen receives orders quickly post-confirm. | p95 time confirmed→kitchen visible | ≤ 5 s |
| H-5 | Courier handoff with deep-link reduces start delay. | Time assigned→driving | ≤ 3 min |
| H-6 | Owner uses dashboard daily. | Owner sessions/day | ≥ 1 |
| H-7 | AI-call abandonment not worse than human. | AI call abandon rate | ≤ human baseline |
| H-8 | CRM match rate grows over time. | % calls matched | growing MoM |

`Open question:` Baselines for today's volume, missed calls, average ticket, delivery time?

---

## 8. Open questions for Product Owner

### 8.1 Scope
- OQ-S1: Delivery only, or also pickup / dine-in?
- OQ-S2: Payment on call, on delivery, or external link?
- OQ-S3: Menu source of truth?
- OQ-S4: Opening-hours / out-of-hours behavior?
- OQ-S5: Multi-location now or future?
- OQ-S6: Does AI quote prices and totals?
- OQ-S7: Confirmation sent back to caller (SMS/call-back/push)?
- OQ-S8: Human handover during call — required/optional/forbidden?
- OQ-S9: Allergies / special requests scope?
- OQ-S10: Courier assignment — manual/auto/hybrid?

### 8.2 Data
- OQ-D1: CRM fields beyond name/phone/address?
- OQ-D2: Call recording retention + purpose?
- OQ-D3: Order history retention?
- OQ-D4: Caller identity assurance for CRM reuse?
- OQ-D5: Menu/price model + update cadence?

### 8.3 Pricing / commercial
- OQ-P1: Expected call volume per day / peak hour?
- OQ-P2: Budget constraints for voice/ASR/LLM/telephony?
- OQ-P3: Pricing model shown to callers?

### 8.4 Operations
- OQ-O1: Simultaneous confirmers, kitchen stations, couriers count?
- OQ-O2: Device inventory (kitchen tablet, courier BYOD)?
- OQ-O3: Preferred navigator app (Google/Apple/Waze/HERE)?
- OQ-O4: Behavior if no courier available?
- OQ-O5: Behavior if kitchen rejects (sold out)?

### 8.5 Legal
- OQ-L1: GDPR controller and lawful basis for CRM?
- OQ-L2: Consent model for AI handling + recording (German law)?
- OQ-L3: Data residency (EU-only / DE-only)?
- OQ-L4: Impressum, DPA, TTDSG implications.
- OQ-L5: Allergen disclosure obligations (LMIV / EU 1169/2011)?

---

## 9. Risks

| ID | Risk | L | I | Mitigation |
|---|---|---|---|---|
| R-1 | ASR errors in German cause wrong orders. | H | H | Confirmer step; verbal summary (FR-23); handover (FR-22); evaluation on sample calls. |
| R-2 | GDPR non-compliance. | M | H | Legal review; consent script; retention policy; DPA with vendors. |
| R-3 | Caller distrusts AI → abandonment. | M | M | Transparent disclosure; easy handover; abandonment metrics. |
| R-4 | Peak-hour concurrency exceeds capacity. | M | H | Design for concurrency (FR-17); overflow strategy. |
| R-5 | CRM data reuse exposes address to wrong caller. | M | H | Verbal verification before disclosing stored data (OQ-D4). |
| R-6 | Menu/price drift between POS and assistant. | M | M | Single source of truth; sync strategy. |
| R-7 | Courier app dependency on third-party navigator. | L | M | Multi-navigator support; address fallback. |
| R-8 | Dashboard metrics miscomputed. | M | M | Clear state model (FR-19); documented metric definitions. |
| R-9 | Vendor outage. | M | H | Fallback voicemail/human; SLOs; vendor diversity. |
| R-10 | Scope creep to full POS. | H | M | Brief as scope anchor; out-of-scope list. |
| R-11 | Underestimating allergen/legal duties. | M | M | Legal input (OQ-L5); design-time decision. |
| R-12 | No baselines → cannot measure success. | H | M | Capture baselines with PO pre-pilot. |

---

## 10. Handoffs

1. Business Strategist — translate problem + hypotheses into business model notes, cost drivers, revenue framing.
2. Voice/Conversation Design — draft dialogue flows, confirmation scripts, handover, ASR/TTS NFR targets.
3. UX — design flows for confirmer, kitchen, courier, dashboard aligned with FR-19 state model.
4. Privacy / Legal — identify GDPR lawful basis, consent, retention, allergen stance; produce OQ list.
5. Software Architecture — options and ADRs for telephony, ASR/LLM/TTS, CRM, order service, clients, dashboard, auth, observability.
6. Reality-Checker — verify traceability brief → FR/NFR/risks; flag inventions.

Stop criterion met: Report delivered; no implementation; no claims of PO approval.
