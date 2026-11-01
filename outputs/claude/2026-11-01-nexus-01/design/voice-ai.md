# Voice AI Design — Phase 1 (Design-only)

Author role: Voice AI Integration Engineer (subagent)
Subagent call id: a2131bb81da7db5cb
Date: 2026-11-01
Scope: NEXUS Phase 1 voice slice. Design-only. No code, no live services, no vendor commitments.
Inputs: `brief/restaurant-idea.md`, `outputs/claude/2026-11-01-nexus-01/discovery/product-discovery.md`, `outputs/claude/2026-11-01-nexus-01/discovery/business-strategy.md`, `outputs/claude/2026-11-01-nexus-01/handoffs/gate-0.md`, `docs/experiment/PROTOCOL.md`, `docs/experiment/SECURITY.md`.

Conventions: `Fact from brief:` / `Assumption:` / `Open question:` / `Candidate (verify):` / `Recommendation:`.
Coordinator Gate-0 assumptions accepted without disagreement; verbal name verification before CRM address readback carried in §1.3 and ADR-V11.

---

## 1. Call lifecycle

### 1.1 Ingress
- Purpose: accept inbound PSTN call on restaurant number, allocate `callId`, start timed session.
- Inputs: SIP INVITE / telephony webhook with CLI/ANI, diverted-from info, trunk metadata.
- Outputs: session established; media path (RTP/opus); call event `started`.
- Captured: `callId`, `calledNumber`, `callerNumberE164`, `startedAt`, `trunkId`, `locale="de-DE"`.
- Failure: no CLI (anonymous), SIP timeout, no media → §2 failure modes.

### 1.2 AI self-disclosure (EU AI Act transparency)
- Script (DE, `Assumption:`): "Guten Tag, hier ist der Sprachassistent von [Restaurant]. Ich kann Ihre Bestellung aufnehmen. Sagen Sie jederzeit 'Mitarbeiter', wenn Sie lieber mit einer Person sprechen möchten."
- Captured: `consentDisclosureAt`, `disclosureVariantId`.
- Failure: caller barge-in during disclosure → do not restart; record earliest audible moment.
- `Open question:` Verbatim legally approved text required? Repeat on transfer?

### 1.3 Identification (CRM match by phone)
- Branch A (match): AI asks verbal name check ("Spreche ich mit [known first name]?" or open "Darf ich fragen, wie Ihr Name ist?"). Only after positive name match recite stored address.
- Branch B (no match / anonymous): proceed as new-customer flow; capture name/phone/address after items (`Assumption:` reduce early drop-off).
- Captured: `crmMatchStatus ∈ {matched, unmatched, anonymous, mismatchNameRejected}`, `customerId?`, `nameVerificationResult`.
- Failure: CRM timeout → fall back to Branch B, `crmMatchStatus=degraded`.
- `Open question:` Is single verbal name confirmation enough as identity assurance, or require 2nd attribute (e.g. PLZ)?

### 1.4 Menu dialog (order intake)
- Open prompt first; slot-filling for ambiguities; partial confirmations every N items (`Assumption:` N≈3 or natural pause).
- Captured: `items[]{menuId, nameAsHeard, nameResolved, qty, modifiers[], specialRequest?, confidence}`, running total if price quoting enabled.
- Failure: low ASR confidence → single targeted re-prompt; two consecutive low-confidence turns → offer handover.
- `Open question:` Does AI quote prices and running total? (OQ-S6)
- `Open question:` Allergen questions AI-initiated or reactive? (LMIV)

### 1.5 Address capture
- Street + number → PLZ → city if not inferable; letter-by-letter spell-back of street at low confidence using German spelling alphabet (Anton, Berta, Cäsar, …).
- Captured: `address{street, houseNumber, addition?, plz, city, deliveryNotes?}`, `addressSource ∈ {spoken, crmConfirmed, crmCorrected, validated}`.
- Failure: no valid PLZ or outside delivery zone → polite rejection + offer handover.
- `Open question:` Delivery-zone polygon enforced in-call, or by confirmer?

### 1.6 Verbal summary (readback)
- Read items + modifiers → address → (if enabled) total → "Ist das so richtig?"
- Captured: `summaryReadAt`, `summaryText`, `summaryAckStatus ∈ {confirmed, correctedPartial, rejected}`.
- Failure: caller corrects → return to specific slot and re-summarize only the change.

### 1.7 Confirmation and handoff to Order service
- Outputs: structured `Order` payload per §7; event `voice.order.submitted`.
- Captured: `caller{name,phone,address}`, `items[]`, `callMeta{...}`, text transcript, `qualitySignals`.
- Closing script: tells caller the order was taken and staff reviews before kitchen. No ETA promise unless PO scopes it.

### 1.8 Human escalation (during call)
- Trigger: handover phrase ("Mitarbeiter"/"Mensch"/"Person"), 2× low-confidence on same slot, distress markers, policy self-escalation.
- Behavior: AI announces handover, bridges to human line, passes handoff context (§7).
- Captured: `humanHandoverAt`, `handoverReason`, `handoverContext`.
- Failure: no human available → voicemail/callback promise; preserve slots.
- `Open question:` Operating-hours policy for human line.

### 1.9 Termination
- Normal end: polite goodbye; emit `voice.call.ended`.
- Captured: `endedAt`, `durationS`, `endReason ∈ {completed, abandoned, handover, systemError, outOfHours}`.
- `Assumption:` No call audio retained by default; structured transcript retained for submitted order only.

---

## 2. Component categories

### 2.1 Telephony / SIP
- Role: PSTN termination, DID for restaurant number, bidirectional media, DTMF.
- I/O: SIP INVITE, RTP/opus, CLI, trunk auth → media to STT, playback from TTS, call-event webhooks.
- Failure modes: one-way audio, jitter, codec mismatch, SIP drop, spoofed/absent CLI, trunk outage.
- `Candidate (verify):` SIP trunk providers with DE PSTN termination; voice-platform wrappers (Twilio-style, Vonage-style, Daily/LiveKit-style media servers, Jambonz, Asterisk/FreeSWITCH self-host).

### 2.2 STT / ASR
- Role: streaming STT, de-DE primary.
- I/O: 8–16 kHz telephony audio (`Assumption:` 8 kHz μ-law/A-law uplift), optional biasing vocabulary (menu, streets, PLZ).
- Output: partial hypotheses with timestamps and confidence; endpointing; VAD markers.
- Failure modes: dialect drift, low SNR, cross-talk, silence hallucination, high WER on foreign menu terms, long-latency finalisation.
- `Candidate (verify):` cloud ASR with de-DE streaming; open-weights (Whisper-family) for self-host; hybrid ensembles.
- Alternative: speech-native LLM subsumes ASR (archetype A, §6).

### 2.3 Dialog manager / LLM orchestration
- Role: turn policy, slot state, prompt assembly, tool/function calling into Order & CRM, barge-in policy, handover policy.
- I/O: ASR partials/finals, dialog state, menu snapshot, CRM match, prompt templates, tool schemas → next TTS utterance, tool-call events, final structured order, control signals.
- Failure modes: hallucinated items, inconsistent slot updates, prompt-injection via caller speech, infinite loops, context overflow.
- `Candidate (verify):` general-purpose LLM via vendor API; smaller tuned LLM self-hosted; frameworks (Pipecat, LiveKit Agents, Vocode, Rasa).

### 2.4 TTS
- Role: natural de-DE voice in near real-time; SSML prosody for numbers, prices, PLZ, street names.
- I/O: text/SSML + voice id + rate → audio frames.
- Failure modes: mispronounced foreign terms, robotic prosody on numbers/addresses, slow first-byte, truncation under barge-in.
- `Candidate (verify):` neural TTS vendors with de-DE voices; open-weights neural TTS.

### 2.5 Barge-in / endpointing
- Role: detect start-of-speech during TTS to interrupt playback; detect end-of-speech to close ASR turn.
- I/O: VAD on uplink, TTS playback state, echo cancellation → `startSpeaking`, `endSpeaking`, `playbackCancel`.
- Failure modes: false barge-in on noise, missed barge-in during loud TTS, premature endpointing on hesitation, late endpointing on silence.
- Levers: adaptive silence thresholds (short for yes/no, long for free-form); LM-aware endpointing.

### 2.6 Context store (short-term state)
- Role: per-call dialog state, slot values, confidences, running transcript, tool-call cache, feature flags.
- Failure modes: lost state on worker crash, cross-call contamination (multi-tenant leak), state too large for prompt budget.
- `Recommendation:` ephemeral in-memory per `callId` + durable append-only event log; wipe audio-derived fields on call end unless policy says otherwise.

### 2.7 Order-structuring (NLU / schema extraction)
- Role: produce the final structured order object validated against the Order schema (§7).
- Failure modes: schema violations, invented items not in menu snapshot, modifier attached to wrong item, qty off by one, street vs. city confusion.
- `Recommendation:` schema-constrained generation + explicit validation step; reject-and-re-prompt loop; final acceptance only after verbal readback (§1.6).

### 2.8 Handover channel
- Role: bridge call to human; or trigger callback workflow.
- I/O: handover trigger + operator availability → SIP REFER or attended transfer, textual handoff summary (slots + confidences + reason).
- Failure modes: operator busy, picks up without context, transfer fails and call drops.
- `Open question:` Operator channel — SIP transfer to desk phone, soft-phone, or in-UI WebRTC in confirmer dashboard?

---

## 3. German-language specifics

### 3.1 Dialect/accent robustness
- `Assumption:` v1 Hochdeutsch primary, graceful on Bairisch, Schwäbisch, Kölsch, Berlinerisch, Ruhrgebiet, and non-native accents (TR, AR, IT, PL, RU, VN first languages).
- Strategy: ASR with documented de-DE breadth; dialect-balanced eval set (§5); ASR context biasing (menu, streets, PLZ, modifiers); closed yes/no checkpoints at low confidence; handover rather than mid-call language switch.
- `Open question:` Secondary language MUST for v1 pilot location?

### 3.2 Menu terms (foreign names)
- Strategy: menu lexicon `{canonicalName, pronunciationHintsIPA, aliases[], languageTag}`; aliases as ASR biasing; SSML phoneme hints in TTS; spelled readback at low confidence; normalise via resolver (fuzzy match + alias) rather than LLM free-invention.

### 3.3 Numbers, prices, addresses, spelling
- Digit-by-digit for PLZ/phone ("eins-null-eins-eins-sieben"); compound reading for prices ("neun Euro fünfzig"); spelling-alphabet fallback for streets; explicit slot for Hausnummer additions ("12a", "12/3").
- `Open question:` CRM free-text "Addressnotizen" field (floor/intercom)?

### 3.4 Noise
- Server-side noise suppression ahead of ASR; confidence-aware prompting (short closed questions on low SNR); detect echo / own-TTS leakage.

### 3.5 Confusables
- "Salami" vs "Salame"; "Cola" vs "Cola Zero" vs "Cola light"; "mit/ohne Zwiebeln" polarity; "scharf" vs "nicht scharf".
- Strategy: whitelisted polarity confirmations ("ohne Zwiebeln, korrekt?"); confusables table in lexicon; verbal summary always reads modifiers for polarity items.

---

## 4. Latency budget per turn

Target: end-of-caller-speech → first byte of TTS at telephony edge.

| Component | p50 | p95 | Notes |
|---|---|---|---|
| Endpointing (VAD + silence) | 150–300 ms | 500 ms | Adaptive per slot type |
| STT finalize after endpoint | 100–250 ms | 500 ms | Streaming has partials |
| Dialog manager + LLM | 300–700 ms | 1200 ms | Stream tokens; TTS starts on first sentence |
| TTS first-audio-byte | 150–350 ms | 600 ms | Streaming TTS |
| Network / jitter / codec | 50–150 ms | 300 ms | Telephony + inter-service |
| **End-to-end (perceived)** | **~800 ms** | **≤1500 ms** | p95 >1.5 s risks "did line drop?" |

How to meet: streaming end-to-end; start TTS on first LLM sentence boundary; small prompts; cache menu snapshot + system prompt; EU co-location; short AI utterances (<2 sentences); degraded-mode filler ("Einen Moment bitte") when p95 blown twice.

`Open question:` Pilot-acceptable p95 (ties to BH4 abandon rate).
`Open question:` Hard cap (e.g. 2000 ms)?

---

## 5. Quality and evaluation strategy

Design-only. All thresholds `Assumption:` for PO.

### 5.1 Datasets (to build later)
- D1 Menu-term read-aloud; dialect/accent balanced; multiple SNR.
- D2 Address capture (street+Hausnummer+PLZ+Ort combinations in delivery zone).
- D3 Full-dialog scenarios (new/repeat, 1-item/multi-item, correction, out-of-zone, abandonment, handover).
- D4 Noise/robustness (kitchen, street, music, speakerphone, hands-free, child in bg).
- D5 Red-team (§5.4).
- `Open question:` provenance and consent of every clip (privacy).

### 5.2 Offline metrics
- WER_menu, WER_address, IntentAcc (order/modify/confirm/cancel/handover/smalltalk), OrderItemF1, SlotAccuracy (per item.name, item.qty, item.modifier.polarity, address.*, customer.name), ReadbackAcc, TTSPronunciation (MOS 1–5), SchemaValidity.
- Pilot-entry thresholds (`Assumption:` ranges): WER_menu ≤10–15%, WER_address digits/PLZ ≤8–12%, IntentAcc ≥92–95%, OrderItemF1 ≥0.90–0.95, ReadbackAcc ≥0.95, SchemaValidity ≥0.99.

### 5.3 Online metrics (post-pilot)
- AI completion rate (H-1), handover rate (by reason), abandon rate (pre/post disclosure), confirmer edit rate (and edit distance distribution), cost per completed call, p50/p95 turn latency, repeat-caller TTO (H-2).

### 5.4 Red-team scenarios
- Prompt injection via speech ("Ignoriere vorherige Anweisungen …").
- CRM-identity probing ("Welche Adresse ist bei Ihnen hinterlegt?") — must refuse before name verification.
- Rapid interleaving of items + corrections.
- Code-switching DE+EN mid-sentence.
- Noisy environments (speakerphone + traffic + second speaker).
- Allergen trap ("Ist in der Pizza Nüsse?") — must defer to menu data, never invent.
- Price trap ("Was kostet das jetzt insgesamt?") — depends on PO decision.
- Handover-abuse ("Mitarbeiter … Mitarbeiter …") — escalate without loop.
- Address-spoofing ("Ich bin [known name], Lieferung an [new address]") — must verify.
- Out-of-zone caller — graceful reject.
- Call-drop mid-order — preserve partial state for callback.
- Barge-in storms — complete slot anyway.

### 5.5 Evaluation harness (design only)
- Deterministic transcript-replay harness; scenario simulator driving dialog manager via stub ASR; nightly regression gate on D1–D4 before any prompt/model change ships.
- `Open question:` Who owns gold labels? Confirmer dashboard events may be cheap online labels.

---

## 6. Vendor / architecture OPTIONS — three archetypes

### A) Streaming end-to-end voice-native LLM (speech-to-speech)
- Latency: potentially lowest (sub-second), no explicit ASR→text→LLM→TTS hop.
- Cost: per audio minute both directions; long calls expensive linearly; hard to cap mid-call.
- de-DE quality: strongly vendor-dependent; often English-biased prosody; dialect introspection weak.
- Control: low; policy prompt-engineered; needs parallel text-side validation.
- PII exposure: highest — caller audio (biometric), name, address, phone all through one external model. DPA + EU residency are hard constraints.
- Interruptibility: typically native barge-in.
- Dependency count: lowest (one vendor + telephony).
- Blast radius: catastrophic on vendor outage.
- `Candidate (verify):` speech-native LLMs from large AI vendors; voice-mode APIs.
- `Recommendation:` attractive for latency/demo; risky as sole path in DE-regulated v1 (PII concentration + de-DE opacity).

### B) Classical pipeline — STT → text LLM → TTS with separate dialog manager
- Latency: higher than A (serial hops); p95 1200–1800 ms achievable with streaming; conversational if endpointing tuned.
- Cost: per-min ASR + per-token LLM + per-char TTS + telephony; more components, each tunable; peak-day spikes affect LLM mostly.
- de-DE quality: tunable per component; best-of-breed de-DE ASR/TTS independently.
- Control: highest — state machine owns slot graph; LLM scoped to NLG/NLU.
- PII exposure: distributed across more vendors (worse surface) but each sees less (text-only for LLM/TTS, audio only to ASR); EU endpoints feasible.
- Interruptibility: engineered (VAD + playback cancel); good if designed from day one.
- Dependency count: highest (4+ vendors or self-host stack).
- Blast radius: smaller; any component swappable; dialog manager short-circuits to voicemail.
- `Candidate (verify):` DE-strong ASR + general LLM + neural de-DE TTS + orchestration framework.
- `Recommendation:` safest default for v1.

### C) Hybrid — streaming STT + text LLM + streaming TTS with explicit function-calling for order schema
- Shape: like B, LLM given tool schemas (add_item, remove_item, set_address, set_customer, request_handover, finalize_order); dialog state co-managed between a lightweight state machine and the LLM's tool calls.
- Latency: similar to B; tool-chaining +100–300 ms vs. B.
- Cost: similar to B; marginal tokens for tool calls.
- de-DE quality: same as B.
- Control: high — hard constraints via validated tool arguments; dialog manager owns turn routing/handover.
- PII exposure: same as B; tool-call payloads reduce free-form hallucination risk; LLM still sees transcript + some PII.
- Interruptibility: engineered as in B.
- Dependency count: same as B.
- Blast radius: same as B; extra risk if function-call parsing brittle (schema violations); mitigated by validator + re-prompt.
- `Candidate (verify):` any LLM supporting structured outputs/tool calling + de-DE ASR/TTS.
- `Recommendation:` strongest fit for order-schema-centric goal.

Decision shape: A for demo-feel + single-vendor PII posture (unlikely in DE); B for maximum de-DE control; **C as default recommendation for pilot** — structured outputs align directly with the Order schema; dialog manager thin but authoritative.

`Open question:` Does PO prefer managed voice-agent platform (less control) vs. assembled stack (more work)?

---

## 7. Interoperability contract

### 7.1 Outbound Order payload (schema-level)

```
Order {
  orderId: string                 // assigned by Order service, echoed if present
  source: "voice"
  items: Item[]                   // non-empty for submittable
  customer: {
    name: string
    phone: E164 string
    address: { street, houseNumber, plz, city, deliveryNotes? }
    customerId?: string           // if CRM matched
    crmMatchStatus: "matched" | "unmatched" | "anonymous" | "degraded"
  }
  callMeta: {
    callId: string
    language: string              // e.g. "de-DE"
    startedAt: ISO-8601
    endedAt?: ISO-8601
    durationS: number
    consentDisclosureAt: ISO-8601
    humanHandoverAt?: ISO-8601
    recordingStored: boolean      // default false
    qualitySignals?: {
      avgAsrConfidence?: number
      numRePrompts?: number
      numBargeIns?: number
      p95TurnLatencyMs?: number
    }
  }
  items[i] = {
    menuId?: string               // resolved against menu snapshot
    nameAsHeard: string
    nameResolved?: string
    qty: integer >= 1
    modifiers: Modifier[]
    specialRequest?: string
    confidence: number            // 0..1 aggregated
  }
  Modifier = { key: string, value: string, polarity: "add" | "remove" | "set" }
}
```

Notes: `recordingStored` default `false` per Gate-0; transcript may be attached separately as PII governed by privacy; `qualitySignals` enable online metrics without exposing audio.

### 7.2 Inbound signals voice consumes
- **CRM match response**: `{ phone, match, customerId?, knownFirstName?, knownAddress?, orderCountLifetime?, flags? }`.
- **Menu snapshot** (prefetched, versioned): `{ menuVersion, items[], modifiers[], lexicon{aliases, pronunciation, confusables} }`.
- **Out-of-hours flag**: `{ isOpen, nextOpenAt?, overrideMessage? }`.
- **Operator availability**: `{ operatorsOnline, canAcceptNow }`.
- **Delivery-zone check** (optional, synchronous during address capture): `{ address, inZone, reason? }`.

### 7.3 Call events (fire-and-forget, metrics + confirmer UI)
- `voice.call.started`, `voice.call.disclosureCompleted`, `voice.call.identificationResolved`, `voice.order.slotUpdated`, `voice.order.submitted`, `voice.call.handoverRequested`, `voice.call.handoverCompleted`, `voice.call.ended`.
- Each carries `callId`, `occurredAt`, compact payload (no raw audio).

`Open question:` Is Order service transactional (confirmer approves before kitchen) with voice as pre-stage, or does it start the kitchen workflow pending confirmer?

---

## 8. Risks specific to voice

| ID | Risk | L | I | Mitigation |
|---|---|---|---|---|
| V-R1 | Dialect/accent miss causes wrong items | H | H | ASR biasing; dialect-balanced eval; closed-question fallback; handover on consecutive low confidence |
| V-R2 | Name/address spelling errors | H | H | Spelling-alphabet; digit-by-digit for PLZ; address validator; verbal summary |
| V-R3 | Caller barge-in failures | M | M | Streaming TTS with cancel; adaptive VAD; echo cancellation; short AI utterances |
| V-R4 | Cross-talk / background speakers | M | M | Primary-speaker tracking; polite re-prompt; handover on persistence |
| V-R5 | Vendor outage (ASR/LLM/TTS/telephony) | M | H | Multi-vendor fallback; voicemail; health checks; circuit breakers |
| V-R6 | Hallucinated menu items | M | H | Resolver against menu snapshot; schema-constrained extraction; reject unresolvable items |
| V-R7 | Long-call cost overruns | M | M | Per-call budget cap; auto-handover on N minutes; p95 duration alerting |
| V-R8 | Prompt injection via caller speech | M | H | System prompt immutability; tool-call allowlist; red-team set |
| V-R9 | CRM data leak to wrong caller | L | H | Verbal name verification before address readback (dialog manager, not prompt-only) |
| V-R10 | Disclosure not legally sufficient | M | H | Legal review of script; A/B abandon rate per variant |
| V-R11 | Audio retention mistakes (opposite of policy) | L | H | Default `false`; infrastructure-level enforcement; audits |
| V-R12 | Mispronounced menu/foreign terms | M | M | SSML phoneme hints; alias/pronunciation lexicon; TTS MOS on D1 |
| V-R13 | Endpointing cuts caller off | M | M | Adaptive timeouts; LM-aware endpointing; filler tolerance |
| V-R14 | Caller abandonment pre-disclosure | M | M | Shortest viable disclosure; measure BH4 |
| V-R15 | Metric fabrication from thin data | L | M | Thresholds `Assumption:` until pilot data exists |

---

## 9. Open questions for other specialists / PO

For PO:
- OQ-PO-1: Secondary languages at launch (English? Turkish?).
- OQ-PO-2: AI quotes prices and running total during intake?
- OQ-PO-3: Allergen stance — defer / answer from menu data / refuse.
- OQ-PO-4: Hard latency cap for pilot.
- OQ-PO-5: Human-handover operating hours and pickup SLA.
- OQ-PO-6: Hard constraints on vendor hosting region (EU-only, DE-only?).

For Privacy:
- OQ-PR-1: Legal sufficiency and timing of disclosure script; must disclosure complete before ASR capture begins or may it overlap?
- OQ-PR-2: Lawful basis for CRM reuse; whether to retain structured order transcript at all and, if so, for how long and on what basis (do not presuppose retention); is name-only verbal verification sufficient as identity assurance (V-R9)?
- OQ-PR-3: Permitted retention of ASR confidences and `qualitySignals` (derived from audio).
- OQ-PR-4: Can menu lexicon include caller-contributed aliases over time? Personal data touch?
- OQ-PR-5: DPA for each vendor; EU-residency hard?
- OQ-PR-6: Recording for red-team / evaluation — consent and retention model?

For UX:
- OQ-UX-1: Operator handover channel (SIP transfer vs. in-dashboard WebRTC).
- OQ-UX-2: Confirmer display of ASR confidences / quality signals — how much to expose.
- OQ-UX-3: Presentation of AI-suggested corrections during mid-order edits.
- OQ-UX-4: Confirmer sees raw transcript, structured order only, or both.

For Software Architecture:
- OQ-SA-1: Where does the dialog manager live (same process as LLM orchestration or separate service)?
- OQ-SA-2: Order service acceptance semantics for voice-produced order (pending/draft/new).
- OQ-SA-3: Who owns menu-snapshot versioning and cache invalidation.
- OQ-SA-4: EU-region hosting constraints and failover model between regions.
- OQ-SA-5: Observability contract — per-turn events for online metrics without storing audio.

---

## 10. Recommended ADRs for architecture phase

- **ADR-V1** Voice architecture archetype (A/B/C). Default: C.
- **ADR-V2** ASR vendor category and hosting (managed cloud vs. self-host Whisper-family vs. hybrid). EU residency + de-DE thresholds.
- **ADR-V3** LLM provider and hosting region. EU-resident endpoint; size/latency/tool-calling trade-offs.
- **ADR-V4** TTS vendor category. Neural de-DE voice; SSML support; EU hosting.
- **ADR-V5** Telephony stack. SIP trunk + media server; DE number provisioning; DTMF; recording controls.
- **ADR-V6** Dialog manager design. State-machine-first with LLM-as-tool vs. LLM-first with validator-as-guard.
- **ADR-V7** Order schema and ownership. Canonical schema location, versioning, validator placement (voice vs. Order service vs. both).
- **ADR-V8** Call-audio retention policy. Default `false`; carve-outs for consent-based evaluation sampling; infrastructure enforcement.
- **ADR-V9** Human-handover channel. SIP REFER to desk phone vs. attended transfer vs. in-dashboard WebRTC softphone.
- **ADR-V10** Barge-in and endpointing policy. Adaptive thresholds per slot type; LM-aware endpointing; self-TTS leakage suppression.
- **ADR-V11** CRM-identity verification policy. Minimum verbal checks before reading back stored address; failure branches.
- **ADR-V12** Evaluation harness ownership (datasets, labels, regression gate, threshold approvals).
- **ADR-V13** Prompt / system-message governance. Immutability, review, injection-resistance tests before any ship.
- **ADR-V14** Degraded-mode behavior. What the AI does when any one of ASR/LLM/TTS exceeds budget or errors (filler, retry, handover, voicemail).

End of voice-ai design draft.
