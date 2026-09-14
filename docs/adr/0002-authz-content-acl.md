# ADR 0002 — One permission primitive for every app: authorize() + content ACL

**Status:** Proposed (operator GO 16:01Z, Telegram 5409)
**Date:** 2026-09-14
**Deciders:** scitex-app (owns `scitex_app.authz`), hub (backs the model), scitex-ui (renders the Verdict)

## Context

Today each mount hand-rolls its content gate: the hub's `cards_board_access_allowed` (staff) and `_fleet_access_allowed` (staff/superuser/SAC-operator env list) have **drifted** — which is how the operator's own account lost the Cards tile. The operator's rule (15:48Z): *Agents and Cards are pre-installed and shown to everyone; only the CONTENT depends on the user. Hiding the whole app is wrong. "Isn't there a primitive every app uses to control permissions? There should be."*

`scitex_app/authz.py` already defines the **Verdict contract** (five kinds: `allowed`, `denied`, `denied-because-not-signed-in`, `denied-because-not-entitled`, `unresolved`) plus `ResolveState` and `hub_url()`, but states *"`can()` is NOT here yet"* — and **no consumer imports it**. `scitex_app/_app_scope.py` declares a user/project scope for the *project-selector marker only*; it does not scope data.

The principle **already exists, partially** — in the hub, not the SDK:

- **Hub `docs/MASTER/00_SECURITY_PERMISSION_ARCHITECTURE.md` (2026-02-20):** "one authenticated user cannot read, modify, or exhaust resources of another user." **Layer 4** is project-scoped RBAC: Project read = owner, members, or public; write = `Project.can_edit` via `ProjectMembership.permission_level`. Enforced on hub file + git endpoints; the Scholar library is scoped by project root.

The gap is an **SDK-level content contract that leaf apps must follow** — so every app asks ONE primitive *"may this actor see/do this, and over which data?"* instead of per-app code. Adoption is **fleet-wide** (15:52Z/15:53Z): hub (Cards/Agents mounts, launcher, project access), scitex-cards (per-user scoping), sac GUI (fleet rows), writer / figrecipe / scholar (project + content), stats (builds on it from the start), and scitex-ui (renders the Verdict states).

## Decision

**One SDK primitive, POSIX-shaped.** The operator generalised it to Unix rwx (16:00Z, Telegram 5397) and to "everything is a file" (16:00Z, Telegram 5398). The model below **supersedes** the earlier `read < write < admin` levels (card `c_36770a236685`) and **builds on** the hub's `Project` + `ProjectMembership.permission_level` — it does not invent new roles.

### 1. Everything is a resource with a canonical path

Cards, agents, manuscripts, figures, libraries, analyses, and files all get a canonical resource path, e.g.

```
/users/<id>/cards/<card-id>
/groups/<id>/projects/<slug>/figures/<name>
/agents/<name>
```

Each carries the **same mode+ACL record**, evaluated by the **same** `authorize()` / `scope_for()`. A real file is the special case where the path is also on disk and the ACL is mirrored to `setfacl`.

### 2. POSIX rwx + ACL (the record)

A resource carries:

- **Base mode** `owner / group / other × rwx` (e.g. `0750`), where
  - `r` = view / list content,
  - `w` = edit / delete,
  - `x` = execute actions on it (run an agent, compile a manuscript, run an analysis, trigger a card workflow);
- **ACL entries** `user:<id>`, `group:<id>`, `agent:<name>` — each with its own rwx;
- **a mask** (the standard POSIX-ACL mask over the group/other/entries);
- **`public`** — a separate **explicit** flag (anonymous read). `other` covers any *signed-in* user; `public`/anonymous is distinct because `other != anonymous` on the web.

**Identical in shape to POSIX ACLs**, so file resources map **1:1 onto `chmod`/`setfacl`** on the per-user OS accounts the cloud already creates (defence in depth — card `c_b55c8236fc5e`).

Special bits (setuid/setgid/sticky, the leading `7` in `7777`) are **not needed initially**; the only later candidate is **sticky** on shared folders (only owners delete their own entries).

### 3. Owners and agents

- **Changing the mode/ACL is owner-only** — the `chown`/`chmod` analogue (an optional admin grant comes later).
- **An operator is a group membership**, not a special case.
- **Agents act *for* an owner user.** An agent's effective bits = `(grant to the agent) AND (the owner user's bits)` — **never more** than the owner. This is the canonical test case (Cards: a user-owned, agent-assigned card — see `c_6818e6d58f50`).

### 4. Two functions (the names)

The operator questioned `can` — it reads as a boolean but returns a five-kind Verdict, and a boolean-shaped name invites `.can(...)` truthiness that collapses `denied-because-not-entitled` / `denied-because-not-signed-in` / `unresolved` into "no." **Final names (scitex-app's call):**

- **`authorize(actor, action, resource) -> Verdict`** — the existing five kinds; synchronous and total per the module contract. `action` maps onto a bit (`read`/`write`/`execute`).
- **`scope_for(actor, app_or_kind) -> <query predicate>`** — the **data-scope half**. Returns a predicate a list view applies **once** to filter rows: `owned-by-actor OR granted-to-actor OR granted-to-actor's-groups OR (for agents) granted-to-actor's-owner OR public`.

Both are exported via **`scitex_sdk.app`** (the 0.1.1 facade), alongside the submodule aliases.

### 5. Backing model + inheritance

- **Build on the hub's `Project` + `ProjectMembership.permission_level`** (read/write/admin → r/w/x), cross-linked to `docs/MASTER/00_SECURITY_PERMISSION_ARCHITECTURE.md`. The **hub resolves principals** (users, orgs, agents) and exposes them to leaf apps via the **existing `/api/me/` seam** — so `authorize()` has no new hub-side dependency.
- **Directory-style default-ACL inheritance:** a new resource inherits a default ACL from its parent path (POSIX default ACLs), so *sharing a project shares its contents* without per-item grants.

### 6. How the whoami resolves (locked from the #806 seam review)

The resolver uses an **injectable transport seam (PA-306-compliant)** — **not** `raise_for_status()` (which would lose the 401/5xx bodies the five Verdict kinds need to be told apart):

- `200` + `plan=null` → `denied-because-not-entitled` (signed in, no plan);
- `401 {missing|invalid|expired|revoked}` → `denied-because-not-signed-in`;
- `5xx` → `unresolved` (a dead hub is not "signed out");
- `200` + `plan` → proceed to the rwx/ACL evaluation.

`sign_in_url` / `upgrade_url` are supplied by the `authorize()` layer, not the resolver.

### 7. Adoption order + files

1. **hub** (Cards/Agents mounts, projects) — swaps its two drifted hand-rolled gates.
2. **scitex-cards** (per-user scoping) + **sac GUI** (fleet rows) — adopt the same scope.
3. **writer, figrecipe, scholar, stats** — project + content access.

Each adopter adds an **ACL-backed boundary test**. For **files** the SDK `authorize()` check is complemented by **OS enforcement** (per-user Linux UID, `chmod 700` home, POSIX ACLs via `setfacl` for group/shared grants, mirrored on change) so a bug in one layer does not leak data.

## Consequences

- **Positive:** one stable contract every app keys off (the ADR locks the names so the fleet-wide adoption cannot drift again); the operator's lost-Cards-tile class of bug is structurally removed; content ACL is testable per app; files get real OS-backed enforcement.
- **Negative / cost:** the hub must resolve principals via `/api/me/`; each app adds a boundary test; `scope_for` returns a predicate, not a list, so callers must apply it (a small but real API shape to teach).
- **Out of scope here (deliberate):** the per-app schema half (cards/manuscripts/etc. *carrying* the grants+public columns) is each adopter's own follow-up, scoped against this contract — the SDK supplies the **evaluator**, not the storage.

## Alternatives considered

- **`can()` boolean** — rejected: mis-models the five Verdict kinds under truthiness (operator + hub, 15:55Z).
- **`read < write < admin` levels** — superseded by rwx (the operator's 16:00Z Unix generalisation; `x` covers "execute actions" that a two-level model had no slot for).
- **Per-mount hand-rolled gates** — the status quo that already drifted once; the operator explicitly ruled it out (15:52Z).

**Cross-links:** hub `docs/MASTER/00_SECURITY_PERMISSION_ARCHITECTURE.md` (Layer 4); `scitex_app/authz.py` (Verdict contract, this ADR fills the `can()` gap); ADR 0001 (scitex-sdk consolidation — the primitive ships via `scitex_sdk.app`); card `sdk-authz-can-primitive-for-per-user-app-content-20260914`.
