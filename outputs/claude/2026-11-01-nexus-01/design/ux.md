# Phase-1 UX Architecture — AI Phone-Ordering Assistant (Germany)

Author role: UX Architect (design-only, NEXUS Phase 1)
Subagent call id: a03466100e8d2e419
Scope: Design-only. No HTML/CSS/JS, no image embeds, no executable artefacts, no vendor commitments.
Inputs: `brief/restaurant-idea.md`, `outputs/claude/2026-11-01-nexus-01/discovery/product-discovery.md`, `outputs/claude/2026-11-01-nexus-01/discovery/business-strategy.md`, `outputs/claude/2026-11-01-nexus-01/handoffs/gate-0.md`.
Conventions: `Fact from brief:` / `Assumption:` / `Open question:` / `Recommendation:`.
Gate-0 assumptions acknowledged: v1 single-tenant, single-location, delivery-only; German primary; human handover SHOULD; verbal name verification before stored-address recital. No disagreements.

---

## 1. Roles & devices

| Role | Primary job | Device(s) `Assumption:` | Context |
|---|---|---|---|
| Caller / customer | Place order via voice. | Any phone (not our UI). | Out of UI scope; shaped by voice design. |
| Confirmer / shift lead | Review AI order; approve/edit/reject; optionally join call. | Laptop or tablet (10–13"); landscape; stationary at counter. | Act within seconds while another call may be live. |
| Kitchen | See confirmed orders, mark ready; reject item (sold-out). | Wall-mounted or counter tablet (10–13"); glove touch; humidity/noise. | Hands wet/greasy; glance-and-tap. |
| Courier | Receive assignment, open navigator, mark delivered. | Personal smartphone; portrait; outdoor daylight; one-handed; mount. | May be offline between buildings; gloves in winter. |
| Owner / manager | Monitor day KPIs; drill into courier performance. | Phone or desktop; occasional tablet. | Often remote. |

`Open question:` Dedicated confirmer station vs. rotated role? (OQ-O1).
`Open question:` Courier device ownership (company vs. BYOD).
`Open question:` Kitchen single shared vs. multi-station tablets.
`Open question:` Shared "expo" display between kitchen and pickup.
`Assumption:` A single person may hold multiple roles concurrently (owner + confirmer); UI must not block role-switching mid-shift.
`Recommendation:` Treat confirmer and owner as same identity class with different active views; kitchen and courier remain narrow task-only identities.

---

## 2. Information architecture

### 2.1 Confirmer / shift lead
| View | Primary job | Data | Nav |
|---|---|---|---|
| Incoming queue | Live list of calls in progress + pending confirmation. | `Call`, `Order (draft)`, `Customer`, AI confidence meta. | → Order review. |
| Order review | Approve / edit / reject one order. | `Order`, `OrderItem`, `Customer`, `Call transcript (structured)`, `Menu snapshot`. | → Queue; → Live call join. |
| Live call join | Human handover audio. | `Call session`, `Agent presence`. | Modal over Order review. |
| Customer profile | Verify + correct CRM. | `Customer` + prior `Order` history (limited). | From Order review. |
| Day log (shift) | Audit own actions. | `Order events`, `User actions`. | Peer. |

### 2.2 Kitchen
| View | Primary job | Data | Nav |
|---|---|---|---|
| Active queue | Confirmed orders not yet ready; sorted by promised / confirmation time. | `Order (status=confirmed|in-kitchen)`, `OrderItem`. | → Order detail. |
| Order detail | Items + notes; mark ready; flag sold-out. | `Order`, `OrderItem`, allergen notes. | → Queue. |
| Ready-but-unassigned shelf | Awareness of orders waiting courier. | `Order (status=ready, courier=null)`. | Peer. |

`Recommendation:` Hide address, name, phone from kitchen view by default; show only items and item-level notes.

### 2.3 Courier
| View | Primary job | Data | Nav |
|---|---|---|---|
| My assignments | Orders assigned to me today. | `Order (courier=me, status in {assigned, en-route})`. | → Delivery screen. |
| Delivery screen | Address, phone, open navigator, mark delivered, report issue. | `Order`, `Customer (name, phone, address)`, `maps:`/`geo:` deep-link. | → Assignments. |
| Day summary | Completed today. | `Order (status=delivered|closed, courier=me, today)`. | Peer. |
| Offline banner | Status + retry. | Connectivity. | Global persistent. |

### 2.4 Owner / manager
| View | Primary job | Data | Nav |
|---|---|---|---|
| Dashboard (today) | 4 FR-15 cards. | Aggregates over `Order events`. | → Courier breakdown; → Order list. |
| Courier breakdown | Per-courier KPIs. | Aggregates by courier. | → Order list. |
| Order list | Browse/filter orders. | `Order`. | → Order detail (RO). |
| Historical | Compare days/weeks. | Aggregates. | Peer. |
| Settings (minimal v1) | Users, couriers roster, menu snapshot indicator. | `User`, `Courier`, `Menu`. | Peer. |

### 2.5 Cross-role conventions
- Global top bar: role indicator, current user, DE/EN toggle (`Assumption:`), connectivity.
- Toasts for staff; push + system notification for courier (subject to privacy).
- Deep-linkable order IDs across views.
`Recommendation:` One identity, many role surfaces. Role-aware web app for confirmer/kitchen/owner; PWA for courier.

---

## 3. End-to-end flow narratives

Legend: `[Actor]` → `(System event)` → `{State}` → `<UI>`.

### 3.1 F1 Known-caller happy path
1. `[Caller]` dials.
2. `(Telephony answers; AI disclosure line)`.
3. `(CRM lookup)`.
4. `[AI]` greets by first name only; verifies name verbally; does NOT recite stored address yet.
5. `[Caller]` confirms name → `(AI reveals stored address for confirmation)` → confirms.
6. `[Caller]` dictates items; AI echoes running summary.
7. `[AI]` final summary (items, address). `Open question:` price?
8. `(Order persisted draft)` → `{new}` → `<Confirmer / Incoming queue>`.
9. `[Confirmer]` opens `<Order review>`, checks CRM match + AI confidence.
10. `[Confirmer]` Approve → `{new → confirmed}` → `<Kitchen / Active queue>`.
11. `[Kitchen]` opens `<Order detail>` → start prep (optional) → `{confirmed → in-kitchen}`.
12. `[Kitchen]` marks ready → `{in-kitchen → ready}` → `<Ready-but-unassigned shelf>` + assignment trigger.
13. `(System or [Confirmer] assigns courier)` → `{ready → assigned}` → `<Courier / My assignments>` push.
14. `[Courier]` opens `<Delivery screen>` → Navigator → `{assigned → en-route}`.
15. `[Courier]` Delivered → `{en-route → delivered}`.
16. `(Auto-close rule)` → `{delivered → closed}` on dashboard.

`Open question:` `closed` auto or explicit? Brief says courier "closes" — v1 may treat delivered=closed.

### 3.2 F2 New caller + CRM creation
1. Same F1.1–F1.2.
2. `(CRM lookup no match)`.
3. `[AI]` collects name → repeats back → collects address → spells back street/number/PLZ → captures delivery note.
4. `[AI]` collects items; mirrors caller language.
5. `[AI]` summarises; explicit confirmation.
6. `(Customer created `unverified`; Order `draft`)` → `{new}`.
7. `<Order review>` shows "First-time caller" badge; non-blocking address plausibility hints.
8. `[Confirmer]` can edit customer fields before approve.
9. On approve: `(Customer `active`)` → F1.10 onward.

`Assumption:` Light verification — first successful delivery marks customer "trusted" for CRM reuse. Privacy to confirm.
`Open question:` Independent address validation (postcode gazetteer) before kitchen dispatch?

### 3.3 F3 Edit/reject on confirmation
- F3a wrong item: edit panel + menu picker; audit event; approve as F1.
- F3b wrong address: inline edit + PLZ format check; modal "Nur diese Bestellung / Auch im Kundenprofil ändern".
- F3c out-of-stock: substitute / remove / reject whole; reject requires reason (ingredient out, address not deliverable, outside hours, other+free text); callback `SHOULD`.

### 3.4 F4 Human escalation during call
- Triggers: low AI confidence; caller requests human; ≥2 clarifications same slot; confirmer proactively joins.
- `(Escalation event)` → `<Incoming queue>` "Hilfe benötigt" badge.
- `[Confirmer]` taps Join → modal over Order review with live transcript + draft order + caller profile.
- Audio bridge; AI announces handover.
- `(AI remains as scribe or steps out — Open question:)`.
- If callback: `{status: new, flag: callback-required}`; confirmer calls back from CRM number; finalises manually.

`Open question:` SLA for human to pick up after escalation.
`Recommendation:` Join action one-tap from queue, not only from Order review.

### 3.5 F5 Courier flow
1. `(Assignment)` → push + badge.
2. `[Courier]` opens assignment.
3. `<Delivery screen>` shows: first name, phone (tap-to-call), full address, delivery notes, items (collapsed), amount to collect if cash (`Open question:` payment timing).
4. Navigator deep-link (`Open question:` OQ-O3).
5. On foreground return, state `en-route`.
6. On arrival: Zugestellt → confirmation prompt → `{delivered}`.
7. Offline: action queued locally; UI shows "Wird gesendet, sobald online"; retries automatically.

`Open question:` Decline / return an assignment to dispatcher? Not in brief; likely SHOULD.

### 3.6 F6 Owner dashboard day-review
1. `[Owner]` opens `<Dashboard (today)>`.
2. 4 cards with last-updated timestamp.
3. Filter: default today; options last 7 days / custom.
4. Tap "Zugestellt pro Fahrer" → `<Courier breakdown>` with per-row deliveries, value, avg time ready→delivered.
5. Tap row → `<Order list>` filtered by courier+range.
6. Tap order → read-only `<Order detail>`.
7. Export (`Open question:` CSV in v1?).

`Assumption:` Near-real-time dashboard (seconds-to-minutes), NFR-13.

---

## 4. State model (FR-19 aligned)

### 4.1 States
| State | Entered by | Who sees | Available | Blocked |
|---|---|---|---|---|
| `new` | AI finishes capture | Confirmer | Approve, Edit items, Edit customer, Reject, Join call | Kitchen view, Courier assignment |
| `confirmed` | Confirmer approves | Kitchen, Confirmer RO, Owner | Kitchen: Start prep, Mark ready, Flag sold-out (→Confirmer) | Edit items (`Assumption:` locked post-confirm), Courier assignment |
| `in-kitchen` | Kitchen starts prep | Kitchen, Confirmer RO, Owner | Mark ready, Flag sold-out | Courier assignment, Edit items |
| `ready` | Kitchen ready | Confirmer, Kitchen, Owner | Assign courier, Reassign | Edit items, Cancel (elevated) |
| `assigned` | Assignment event | Courier push, Confirmer, Owner | Open delivery; Reassign | Edit items; direct deliver without en-route (needs Confirmer override) |
| `en-route` | Courier starts | Courier, Confirmer, Owner | Mark delivered, Problem melden | Reassign without override |
| `delivered` | Courier marks | Courier, Confirmer, Owner | Close (auto/manual) | Reassign |
| `closed` | Auto/manual | Owner dashboard, Confirmer log | Read-only | All mutations |

Exceptions:
| State | From | Who | Recovery |
|---|---|---|---|
| `rejected` | `new` via Confirmer | Confirmer, Owner | Terminal; counted; optional callback |
| `cancelled` | Any pre-`en-route` elevated | Confirmer, Owner, downstream role | Terminal; reason required |
| `failed-delivery` | `en-route` via "Problem melden" "nicht zustellbar" | Courier, Confirmer, Owner | Callback + re-dispatch, cancel, or close-with-loss |

`Open question:` Can `ready`/`assigned` be cancelled by restaurant without customer contact? Legal/consumer-protection input.
`Open question:` Does `in-kitchen` require explicit "Start prep"? Simpler v1: implicit.
`Recommendation:` Dashboard treats `confirmed` and `in-kitchen` as single bucket.

### 4.2 Transition matrix (concise)
- `new` → `confirmed` | `rejected` | `cancelled`.
- `confirmed` → `in-kitchen` | `ready` (skip) | `cancelled`.
- `in-kitchen` → `ready` | `cancelled`.
- `ready` → `assigned`.
- `assigned` → `en-route` | `ready` (reassign).
- `en-route` → `delivered` | `failed-delivery`.
- `delivered` → `closed`.
- `failed-delivery` → `assigned` | `cancelled` | `closed-with-loss`.

---

## 5. Wireframe-level descriptions (text only)

### 5.1 Confirmer order review (single view)
- Header bar: role & user; call status (idle/live/escalation); DE/EN toggle; connectivity; settings.
- Left — metadata & call: Order ID, timestamp, source "Telefon · KI"; AI confidence badge + per-slot icons; auto-generated human-readable call summary + link to transcript drawer; live-call controls (Join / Rückruf anfordern) when call still active.
- Centre — content: items (qty, name, modifiers, note, price, subtotal); row actions Edit/Remove/Mark sold-out; Add-item (menu picker); totals block (subtotal, delivery fee, MwSt breakdown `Assumption:`, grand total).
- Right — customer & delivery: name, phone tap-to-call `Assumption:`, "Stammkunde"/"Erstanruf" badge, prior-orders count; address block (Straße Hausnr., PLZ Ort, Notiz); plausibility chips.
- Footer sticky: "Ablehnen" (destructive, secondary), "Bearbeiten speichern" (dirty), "Bestätigen & an Küche senden" (primary). Keyboard mnemonics §6.

`Recommendation:` One primary action per view in filled primary style.

### 5.2 Kitchen queue + order detail
- Queue cards sorted by time since confirmed; card: short ID, item count, elapsed timer (dominant monospace), status chip, first 3 items + "+N weitere"; actions Open / Start (optional) / Fertig. No customer identity shown.
- Order detail: items + modifiers + notes expanded (no truncation); allergen notes highlighted (`Assumption:` LMIV scope); primary "Fertig" (≥56×56 target, bottom-anchored); secondary "Position nicht verfügbar" (per-item sold-out dialog back to Confirmer). No address/phone/name/price.

`Recommendation:` Default to focused single-column vertical scroll.

### 5.3 Courier assignment & delivery
- My assignments: header name + status (Verfügbar/Pause) + count; row: short ID, pickup hint, destination street + postal area (not full), amount if cash, chip.
- Delivery screen: large customer first name (never full); large copyable address block; delivery note; action block: "Navigator öffnen" (primary), "Anrufen" (tap-to-call — **phone is NOT visible on the screen by default; the tap triggers the call and emits a reveal/audit event per architecture §7.5 F-10 reconciliation**), "Problem melden"; order summary collapsed; dynamic status button "Unterwegs" → "Zugestellt"; persistent connectivity banner; queued-actions indicator.
- Problem flow: reasons (nicht angetroffen, falsche Adresse, Kunde abgelehnt, Fahrzeugproblem, Sonstiges + free text); outcome radio (erneut versuchen / zurück zum Restaurant / Konfirmierer kontaktieren).

`Recommendation:` Delivery screen as a wake-screen target; resume from lock-screen via notification tap.

### 5.4 Owner dashboard
- Header: range selector (Heute/7 Tage/Benutzerdef.), auto-refresh last-updated, export (`Open question:`).
- 4 KPI cards (FR-15): "Zubereitete Bestellungen"; "Zugestellt pro Fahrer" (stacked bar or ranked list — name, count, delivered value sum, avg time ready→delivered); "Bestellsummen" (sum with state breakdown); "Tagesabschluss" (orders, value, avg ticket, cancel rate, AI-handled share).
- Secondary row (optional): "Anrufe heute" (total/AI/escalated/abandoned); "Ablehnungen" by reason.
- Drill-down: any numeric → filtered `<Order list>`; courier row → `<Courier breakdown>` → list.
- Empty state §7.

`Recommendation:` v1 dashboard literal to FR-15; defer decoration until baselines exist.

---

## 6. Accessibility & inclusivity

Scope: WCAG 2.2 AA.

### 6.1 General
- Contrast 4.5:1 body / 3:1 large text; UI contrast ≥3:1; never colour-only state.
- Keyboard reachable; focus order follows reading order; visible focus (2.4.11); focus not obscured; strong focus appearance (2.4.13).
- Labels associated; error messages describe cause + remedy (3.3.1, 3.3.3); consistent nav (3.2.3, 3.2.4).
- Proper ARIA roles for dynamic regions (order status live region, courier offline banner); name/role/value exposed (4.1.2).

### 6.2 Keyboard (confirmer / tablet with external keyboard / owner)
- Global shortcuts (confirmer): A approve, E edit focus, R reject (with confirm), J join call, / focus item search.
- Discoverable via `?` help overlay.
- Tab order header → left → centre → right → footer.
- Modals trap focus and return focus to invoker (2.4.3, 2.4.11).

### 6.3 Screen reader
- Order review announce on load: "Bestellung {id}, {badge}, {items count} Positionen, Gesamtsumme {total}. Aktion: Bestätigen und an Küche senden ist der Primärbefehl."
- Status transitions via aria-live polite.
- Decorative icons; text labels do the work; aria-label where visual label absent.
- Courier actions: success polite, failure/offline-queued assertive.

### 6.4 Colour & contrast
- Status chips: 3:1 border, 4.5:1 text; icon + label redundant.
- Dark mode for kitchen tablet (reduces glare `Assumption:`) and courier app (daylight light / night dark) — OS theme default.
- Avoid red/green sole encoding; shape + label.

### 6.5 Touch targets
- 44×44 baseline; kitchen primary ≥56×56 for gloves.
- ≥24 px spacing between adjacent destructive and primary.
- Avoid long-press as sole destructive trigger; double-step tap→confirm.

### 6.6 Courier daylight readability
- High-contrast tokens; body ≥16 px, address block ≥24 px.
- Street+number on one line; PLZ+city on next.
- Reduced motion; deterministic.
- Navigator one tap.
- `Recommendation:` Suppress non-critical notifications while `en-route`.

### 6.7 Cognitive load at peak
- Confirmer: one order in focus; queue peripheral.
- Kitchen: one dominant action per card; items grouped visually.
- Owner: four cards, not forty.
- Progressive disclosure.
- Error messages concrete, not technical.

### 6.8 Language toggles & locale (German-specific)
- DE primary; EN secondary (`Assumption:`).
- Date `TT.MM.JJJJ`; 24h clock `HH:mm` (e.g. `01.11.2026`, `19:45`).
- Numbers: decimal comma, thousands dot (`12.345,67 €`).
- Currency: trailing € with non-breaking space (`12,50 €`).
- Address format `Straße Hausnr., PLZ Ort` (two lines); PLZ 5 digits; client-side format check only.
- Phone display with `+49 …`; accept common input variants; normalise to canonical.
- Sort order: German collation (DIN 5007-1 `Assumption:`).
- Umlaut handling: accept `Müller` ≡ `Mueller` in search; store canonical.
- Allergen labelling: pending privacy/legal LMIV decision.
- Formal register "Sie" throughout staff UI and AI voice.

`Open question:` Non-German caller languages (TR/AR/IT/EN) — staff UI reflects?
`Recommendation:` v1 staff UI DE+EN only.

---

## 7. Error & empty states

### 7.1 Courier offline
- Trigger: no network N≈10 s.
- Warning (not blocking).
- Message: "Du bist offline. Deine Aktionen werden gespeichert und automatisch gesendet, sobald die Verbindung zurück ist."
- Actions queued locally; "N Aktionen warten"; auto-sync; manual retry.
- Blocked only: brand-new assignment not cached.
- Telemetry: offline duration per shift; retry success rate.

### 7.2 No couriers available
- Trigger: `ready` with no courier online / all busy beyond threshold (`Open question:`).
- Error for confirmer; informational for kitchen.
- Confirmer banner: "Keine Fahrer verfügbar. {N} Bestellung(en) warten auf Zuordnung."
- Recovery: manual assign, postpone, cancel with callback.
- Blocked: automatic assignment.
- Telemetry: wait time in `ready`; occurrence/hour.

### 7.3 Kitchen rejects item (sold-out)
- Order returns to confirmer; medium severity.
- Confirmer: "Küche meldet: {Position} nicht verfügbar. Bitte bearbeiten oder stornieren."
- Recovery: F3c (substitute/remove/reject + callback).
- Blocked progression to `ready` while unresolved.

### 7.4 AI confidence low
- Informational visually at load; blocking only on one-tap approve for overall "Niedrig" (`Recommendation:` require explicit re-read).
- Inline on field: "KI unsicher bei dieser Position — bitte prüfen."
- Recovery: edit; listen to transcript segment via drawer; callback.
- Blocked: silent approve-all shortcut on low confidence.

### 7.5 Dashboard zero orders
- Informational.
- Message: "Für diesen Zeitraum gibt es noch keine Bestellungen. Prüfen Sie den Zeitraum oder warten Sie auf die ersten Anrufe des Tages."
- Suggest "Heute" if different range; link to setup checklist for first-run.
- Cards show "—" not "0" to distinguish "no data" from "zero known".

### 7.6 Other states
- CRM lookup failure during call: AI → new-customer flow; confirmer badge "Kundendaten konnten nicht geladen werden".
- Address plausibility fail: non-blocking warning + "Trotzdem bestätigen".
- Session expired for staff: inline "Sitzung abgelaufen, bitte erneut anmelden"; preserve unsaved edits in local storage (`Assumption:` subject to privacy).
- Push permission denied on courier: "Benachrichtigungen deaktiviert — Zuweisungen werden nur beim Öffnen der App sichtbar"; OS-settings link.

---

## 8. Content design

### 8.1 AI phone persona
- Polite, formal "Sie" register.
- Discloses AI in first turn.
- Concise: one question per turn; confirm slot before moving on.
- Mirrors caller language if detectable (`Assumption:` v1 DE + EN).
- Stays within menu snapshot; no improvisation.
- Confirms totals only if restaurant opts in.
- Hands over on request without resistance.

Example (DE, `Assumption:`):
- "Guten Tag, hier ist der KI-Telefonassistent von {Restaurant}. Ich kann Ihre Bestellung aufnehmen. Darf ich loslegen?"
- "Darf ich Ihnen die bei uns hinterlegte Lieferadresse vorlesen, nachdem Sie mir Ihren Namen bestätigt haben?"
- "Ich wiederhole Ihre Bestellung zur Kontrolle. Bitte sagen Sie am Ende Ja oder Nein."

### 8.2 Staff UI content principles
- Operator-first; label what will happen.
- Action-dominant verbs on buttons.
- Minimal chrome; help in side drawer.
- Honest severity; no red for everything.
- Localisation-ready; externalised strings.

Example (DE, `Assumption:`):
- Confirm primary: "Bestätigen & an Küche senden"
- Reject with reason: "Diese Bestellung ablehnen? Grund angeben:"
- Kitchen sold-out: "Position nicht verfügbar — zurück an Konfirmierer"

### 8.3 Tone by severity (DE examples)
- Success: "Bestellung an Küche gesendet."
- Info: "Keine neuen Anrufe."
- Warning: "Adresse konnte nicht automatisch geprüft werden."
- Error: "Zuordnung fehlgeschlagen. Bitte manuell zuweisen."
- Blocking: "Keine Fahrer verfügbar. Bitte Aktion wählen."

---

## 9. Prototype and testability plan (no execution)

### 9.1 Validation techniques (plan)
- Clickable prototype from these wireframe descriptions (outside this experiment).
- Moderated usability 5–7 per role.
- Think-aloud for AI confidence surfacing + F4 escalation.
- Content review with native-German staff before pilot copy.
- Dark-launch pilot metrics: capture rate, confirm-time, kitchen-ready-time, delivery-close-time, escalation rate, offline queue duration.

### 9.2 IA usability success criteria (`Assumption:` thresholds)
- Confirmer: 90% approve a well-formed order ≤20 s without hints.
- Confirmer: 80% handle F3b correctly on first attempt.
- Kitchen: 95% mark ready ≤3 s of opening detail.
- Courier: 90% complete F5 without accidental feature discovery; 100% trigger navigator ≤2 taps.
- Owner: 100% identify "Zugestellt pro Fahrer" card.
- Comprehension: ≥4/5 per role can describe state model in own words after guided set.
- SUS per role ≥70 at pilot end-of-month (`Assumption:`).

### 9.3 Non-goals of validation in Phase 1
- No live user research under this experiment.
- No A/B copy testing yet.
- No performance measurement (reserved for NFR work with software architect).

---

## 10. Open questions & recommended ADRs

### 10.1 Open questions
- OQ-UX-1 Confirmer identity (dedicated vs. rotated).
- OQ-UX-2 Kitchen devices (single shared vs. multi-station).
- OQ-UX-3 Courier device (company vs. BYOD); PWA vs. native downstream.
- OQ-UX-4 Preferred DE navigator app (Google / Apple / Waze / HERE WeGo).
- OQ-UX-5 AI quotes prices and totals on call?
- OQ-UX-6 Allergen capture scope on call + kitchen view (LMIV).
- OQ-UX-7 Payment timing — at delivery (cash/card) vs. post-call link vs. pre-paid.
- OQ-UX-8 Callback on edits/rejections — automated outbound call, SMS, or manual.
- OQ-UX-9 Dashboard range beyond "today" in v1?
- OQ-UX-10 Export (CSV / PDF Tagesabschluss) in v1?
- OQ-UX-11 Cancellations post-`ready` without customer contact? Legal.
- OQ-UX-12 Second staff UI language at launch (EN plausible; TR/AR/IT unclear).
- OQ-UX-13 `in-kitchen` state mandatory/optional/omitted v1.
- OQ-UX-14 SLA for human join on escalation (F4).
- OQ-UX-15 Owner access to order detail — RO everywhere, or edit for post-hoc corrections?

### 10.2 Recommended ADRs
- **ADR-UX-A** Client topology (role-aware web + courier PWA vs. separate apps).
- **ADR-UX-B** Navigator deep-link policy (single hard-coded vs. configurable; absent-app fallback).
- **ADR-UX-C** Offline strategy for courier (queued actions, idempotency keys, conflict resolution).
- **ADR-UX-D** Real-time delivery for queues (polling vs. push); impact on confirmer freshness + NFR-4.
- **ADR-UX-E** AI confidence surface (backend emits per-slot confidence; warn/block thresholds).
- **ADR-UX-F** Audit/event model powering dashboard (FR-15, FR-19, FR-21) — single source of truth for "prepared", "delivered", day totals.
- **ADR-UX-G** Localisation framework and copy-string ownership.
- **ADR-UX-H** Accessibility baseline enforcement in CI — WCAG 2.2 AA.
- **ADR-UX-I** Session/auth boundaries for role switching (one identity many surfaces vs. separate sessions).
- **ADR-UX-J** Address validation strategy (format-only vs. gazetteer; EU residency per privacy).
- **ADR-UX-K** Call transcript surfacing in confirmer view (segment linking, retention bounded by privacy).

### 10.3 Handoffs
- To Software Architect: §2 IA entities, §4 state model, §10.2 ADR titles, §7 error states (backend implications), §6.8 locale needs.
- To Voice: §3.1–3.4 call-side behaviour, §8.1 AI persona, §7.4 confidence surfacing, OQ-UX-5/6/14.
- To Privacy: §2.2 kitchen PII minimisation, §3.1 step 4 name-before-address, §3.2 new-customer handling, §5.1 transcript surfacing, §7.4 transcript access, OQ-UX-6/11, retention of session edits in local storage.
- To PO: §10.1 open questions, §9.2 proposed usability thresholds.
- To Reality Checker: verify every `Fact from brief:` traces to a brief line or discovery §; no invented research/metrics; assumptions flagged.

End of UX Architecture.
