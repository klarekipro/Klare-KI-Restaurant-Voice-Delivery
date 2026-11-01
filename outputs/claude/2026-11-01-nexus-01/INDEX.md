# Package index — 2026-11-01-nexus-01

Phase 0–1 design-only run for the AI restaurant phone-ordering assistant (Germany).

## Reading order

1. `brief/restaurant-idea.md` *(repo root — the authoritative requirements source)*
2. `handoffs/gate-0.md` — coordinator's Phase-0 synthesis, carried-forward assumptions, open-question backlog
3. `discovery/product-discovery.md` — problem framing, FR/NFR candidates, risks
4. `discovery/business-strategy.md` — DE market, competitive context, business-model options
5. `design/voice-ai.md` — call lifecycle, components, de-DE strategy, 3 architecture archetypes, voice ADR V1–V14
6. `design/privacy.md` — data map, lawful bases, DPIA scope, TOMs, privacy ADR P-01…P-13
7. `design/ux.md` — IA, 6 flows, state model, wireframes (text-only), accessibility, UX ADR A..K
8. `design/architecture.md` — C4 context + containers, domain model, state lifecycle, data model sketch, 7 critical ADRs written in full, ADR index, FR/NFR traceability
9. `handoffs/gate-1.md` — package-assembly verdict and residual blocker summary
10. `review/reality-check-v1.md` — round-1 findings (NEEDS WORK)
11. `review/reality-check-v2.md` — round-2 verification after fixes (PASS)
12. `run-log.md` — delegation ledger, call ids (self-reported), human-intervention record
13. `RESULTS.md` — filled `RESULTS_TEMPLATE.md`

## Status

- Gate 0: PASS (coordinator-authored).
- Gate 1: PASS pending reality-check (coordinator-authored).
- Independent reality-check round 1: NEEDS WORK (16 findings, 4 Major must-fix).
- Fix cycle: applied to F-01, F-02, F-03, F-10 (Major) and F-05, F-07, F-08, F-11, F-12 (Minor). F-04 acknowledged as governance limitation. F-09/F-13/F-14/F-15/F-16 (Minor/Nit) deferred to a later cycle with PO sign-off.
- Independent reality-check round 2: PASS (narrow re-verification; no regressions).
- Independent Codex review: PENDING — no separate Codex session invoked here; see `outputs/codex/` conventions and PROTOCOL §Независимая проверка.
- PO approval: NONE. Design-only artefact; implementation, infrastructure, scaffolding, production and paid integrations remain disallowed under `CLAUDE.md`.

## Scope boundary (restated)

- No code, no scaffolding, no infrastructure change, no production/VPS access, no paid services, no external MCP activation.
- No real-customer data; no secrets; no system/global changes; no modification of other projects.
- All vendor references are category-level `Candidate (verify):`; no commitments.
- All PO-blocking open questions are preserved as `Open question:` / `Pending PO:` / `Needs legal review:`.

## Documents produced in this run (byte-stable copies)

```
outputs/claude/2026-11-01-nexus-01/
├── INDEX.md                                 (this file)
├── RESULTS.md                               (filled template)
├── run-log.md                               (delegation ledger)
├── brief → ../../brief/restaurant-idea.md   (external, authoritative)
├── discovery/
│   ├── product-discovery.md                 (product-manager, a4d4b37fe8b3f76ff)
│   └── business-strategy.md                 (business-strategist, aa2afa5b6caff9e52)
├── design/
│   ├── voice-ai.md                          (voice-ai-integration-engineer, a2131bb81da7db5cb)
│   ├── privacy.md                           (privacy-engineer, a35e24308d8439601)
│   ├── ux.md                                (ux-architect, a03466100e8d2e419)
│   └── architecture.md                      (software-architect, toolu_011zD9FakLWgb3qFR2dZaQdX)
├── handoffs/
│   ├── gate-0.md                            (coordinator)
│   └── gate-1.md                            (coordinator)
└── review/
    ├── reality-check-v1.md                  (reality-checker, afe5e4756b6c67dfd)
    └── reality-check-v2.md                  (reality-checker, a549f80f3b6c9efcd)
```
