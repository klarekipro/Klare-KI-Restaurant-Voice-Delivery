# MVP Delivery Report — feat/mvp-restaurant-voice

Date: 2026-11-01
Branch: `feat/mvp-restaurant-voice`
Prior design cycle: `outputs/claude/2026-11-01-nexus-01/`
Coordinator: Claude Code (`claude-opus-4-7`)

## 1. Rabotayet li ono

Working: **yes**, locally, with persistent SQLite.

Launch:
```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open: http://127.0.0.1:8000/login

Smoke verification performed by the coordinator (manual curl against running uvicorn, see run-log §Smoke):

| Endpoint | Status |
|---|---|
| GET /login | 200 |
| POST /login (owner) | 303 |
| GET /dashboard | 200 |
| GET /menu | 200 |
| GET /call | 200 |
| GET /confirmer | 200 |
| GET /kitchen | 200 |
| GET /courier | 200 |
| GET /dispatch | 200 |
| GET /customers | 200 |

Automated tests: `.venv/bin/python -m pytest` → **5 passed, 1 warning**.

## 2. Demo-Konten (без публикации реальных паролей)

| Benutzer    | Passwort        | Rolle      |
|-------------|-----------------|------------|
| `owner`     | `owner123`      | owner      |
| `confirmer` | `confirmer123`  | confirmer  |
| `kitchen`   | `kitchen123`    | kitchen    |
| `courier1`  | `courier123`    | courier    |
| `courier2`  | `courier123`    | courier    |

These are intentionally weak demo credentials for local evaluation only. The seed is idempotent and only runs if users do not already exist.

## 3. Test-Resultat

```
.....                                                                    [100%]
5 passed, 1 warning in 3.09s
```

Covered:
- Full lifecycle `new → confirmed → in_kitchen → ready → assigned → en_route → delivered → closed`, including customer trusting on first approve, courier phone-reveal audit, and dashboard appearance.
- Repeat-customer CRM match on the seeded phone `+49 30 1234567`.
- Role-based access: courier denied `/confirmer` and `/dashboard`, kitchen denied `/customers`, anonymous denied `/call`.
- Rejected order cannot be marked ready by kitchen (HTTP 409 via `StateError` handler).
- Persistence: two independent `create_app()` invocations against the same SQLite file see the same order.

## 4. Сквозной сценарий

### 4.1 New customer flow (test-executed in `test_full_lifecycle_new_customer`)
1. Confirmer logs in → opens `/call`.
2. Enters phone `+493099990001` → CRM lookup returns `unmatched`.
3. Fills name/address + picks items from the live menu → submits.
4. Order lands in `/confirmer` as `new`; confirmer approves → `confirmed` and the customer flips to `trusted`.
5. Kitchen presses "Fertig" → `ready`.
6. Confirmer dispatches to courier1 → `assigned`.
7. Courier1 opens the delivery screen → marks `Unterwegs` → clicks `Anrufen` (phone reveal → `access_log` entry) → marks `Zugestellt` → order moves to `closed`.
8. Owner opens `/dashboard?range=today` → sees Carlo Courier in "Zugestellt pro Fahrer".

### 4.2 Repeat customer flow (test-executed in `test_repeat_customer_crm_match`)
1. Confirmer logs in → opens `/call`.
2. CRM-Lookup on `+49 30 1234567` → returns the seeded `Thomas Müller` with `trusted=true`.
3. Pre-filled name/address accepted; verbal name-verification remains an operational guard (ADR-V11).
4. Order submits with `crm_match_status: matched`.

## 5. Realised vs. unresolved

### Implemented (brief checklist)
- [x] Browser manager UI (per-role views).
- [x] Customer CRM with addresses.
- [x] Menu catalog with prices.
- [x] Order creation via call simulator.
- [x] Human approve/edit/reject.
- [x] Forward to kitchen on confirm.
- [x] Kitchen "ready" transition.
- [x] Courier assignment via dispatch.
- [x] Courier mobile UI with address + Google Maps deep-link.
- [x] Delivery confirmation.
- [x] Owner dashboard with FR-15 KPIs (prepared count, delivered-per-courier, sums, day totals).
- [x] SQLite persistence (data/mvp.sqlite).
- [x] Real role-based access via FastAPI dependencies.
- [x] Automated end-to-end tests of the main flow.
- [x] Isolated voice interface + explicit simulator mode (free, documented as such; no telephony claim).

### Not implemented (intentional deferral)
- Real SIP/ASR/LLM/TTS stack (free simulator mode as per brief carve-out).
- Multi-location / multi-tenant.
- Payment capture (totals are computed, not settled).
- Automatic courier assignment heuristic (dispatch is manual).
- Offline queue for courier app (PWA/service-worker).
- Allergen workflow (LMIV) in the dialog.
- External address validation / delivery-zone polygon.
- OIDC/SSO; passwords are bcrypt-local.
- Observability stack beyond stdlib logging.

### Open design questions still awaiting PO
See `outputs/claude/2026-11-01-nexus-01/handoffs/gate-1.md` for ~30 open items (scope, trust, legal, operations, business).

## 6. PR & commits (links go in once pushed by the user)

- Branch: `feat/mvp-restaurant-voice` (local only; this coordinator does NOT push without explicit user instruction).
- Suggested PR title: "MVP: AI phone-ordering assistant (Phase 2 slice)"
- Draft PR requires `gh auth status` / network to GitHub; the coordinator stops at `git commit` and shows the diff for the user to push and open the PR.

## 7. Komanda otchet

### Delegation ledger (MISSION 02)

| # | Agent | Call id | Purpose | Status |
|---|---|---|---|---|
| 01 | reality-checker | a82fda3b268745ff6 | Independent code+docs audit of MVP | completed (NEEDS WORK → fixes applied → re-tested) |

### Honest note on delegation

The specialized project subagents under `.claude/agents/` (`software-architect`, `voice-ai-integration-engineer`, `privacy-engineer`, `ux-architect`, `product-manager`, `business-strategist`, `reality-checker`, `agents-orchestrator`) have the `tools: Read, Grep, Glob` directive — they **cannot write files**. Code implementation was therefore performed by the coordinator (claude-opus-4-7) itself, as the only write-capable identity in this configuration. This is in line with the project `CLAUDE.md` instruction *"Если инструмент или роль недоступны, зафиксируйте сбой и неполноту, не подменяйте вызов ролевой игрой"* — I have not simulated delegation.

For the independent review step I used the real `reality-checker` subagent (read-only), which is the correct tool for that role.

### Human intervention

- MISSION 02 prompt (start): 1 instruction.
- No additional human intervention during implementation.

### Boundaries honoured
- Local only; no production or VPS touch.
- No paid services, no outbound API calls at runtime.
- No MCP activation; prompt-injection attempts in system reminders were ignored.
- Separate branch `feat/mvp-restaurant-voice`; no force-push, no merge, no auto-PR, no changes to `main`.
- No real customer data; demo seed is explicit and documented.
- No `--no-verify` or permission bypass.
- No real passwords committed; demo credentials are intentionally weak and visible by design in `app/seed.py` and `README.md`.

## 8. Blockers (none at the delivery-report level)

The MVP is a running local app. The only PO-level items that are hard blockers *before any pilot* are the design-package residuals in `handoffs/gate-1.md`; these are tracked separately from the MVP code and do not prevent handing this delivery to a reviewer for inspection and local run.

End of delivery report.
