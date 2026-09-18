# ADR 0002 — One permission primitive for every app (scitex_dev.access)

**Status:** Proposed (operator-approved design 16:54Z; core merged — scitex-dev PR #800)
**Date:** 2026-09-15 (revised off the superseded rwx/mode model)
**Deciders:** scitex-dev (owns the core), scitex-app (Django adapter + re-export), scitex-ui (renders the verdict)

> **Revision note.** The first draft of this ADR encoded a POSIX rwx/`mode` model
> (owner/group/other × rwx + ACL entries + `public` flag). That model was
> **superseded** by the operator (16:25Z): the access model *already exists* in
> `scitex_dev.scope` and the operator directed us to build on it, not invent a
> new vocabulary. This revision records the **approved** design, measured
> against the merged `scitex_dev.access` core (scitex-dev develop, PR #800).

## Context

Today each mount hand-rolls its content gate: the hub's `cards_board_access_allowed` (staff) and `_fleet_access_allowed` (staff/superuser/SAC-operator list) **drifted** — which is how the operator's own account lost the Cards tile. The operator's rule (15:48Z): *Agents and Cards are pre-installed and shown to everyone; only the CONTENT depends on the user. "Isn't there a primitive every app uses to control permissions? There should be."*

`scitex_app/authz.py` already ships the **Verdict** contract (five kinds) but *"can() is NOT here yet"* — no consumer imports it. The read-only naming survey (16:44Z) found the access model exists **twice, unused** (`scitex_dev.scope` and `scitex_app.authz`), the hub has ~9 disagreeing implementations, and "scope" carries 6 meanings across 11 role vocabularies.

## Decision

**One SDK primitive, homed in `scitex-dev`, built on `scitex_dev.scope`.** The operator approved the design (16:54Z): roles `read < write < admin` (Gitea-compatible), default project visibility **private**, **explicit** agent delegation grants, **username** as the immutable principal id, and **no implicit staff bypass** (staff = `org:scitex-staff` grants). The core is implemented and **merged** (scitex-dev PR #800 → develop); `scitex-app` owns the Django adapter and re-export; `scitex-sdk` re-exports it for apps.

### 1. Vocabulary — reuse `scitex_dev.scope`, no new roles

The five types every app agrees on (`scitex_dev.scope._types`), measured:

- `PrincipalKind = Literal["user", "org", "agent"]` (+ `anonymous` as a first-class principal in `access`);
- `Role = Literal["admin", "write", "read"]` with `effective_role(granted, owner_role)` — **not** rwx; "read-only" is simply `read`;
- `Visibility = Literal["public", "private"]` (default **private**);
- `DataLivesAt = Literal["owner", "project"]`, `ViewKind = Literal["pinned", "cross"]`.

An **agent is `agent:<owner>/<name>`** and is capped by its owner's role (the `agent-ceiling` / `owner-has-no-role` reasons); the asker is resolved from the session/OS account, never taken from request data.

### 2. The core (scitex-dev, merged) — two functions

Measured from `scitex_dev.access.__init__`:

- **`check(principal, action, resource, *, grants, memberships) -> AccessDecision`** — the single evaluator. Rules: owner=admin; grant; inherited default grant from the parent; org via membership (capped); public read for signed-in and anonymous; agent ceiling; no staff bypass; an unregistered kind is `unresolved/kind-unregistered`.
- **`accessible(principal, action, kind, *, ...) -> AccessFilter`** — the **data-scope half**: a backend-neutral filter (owners / resource refs / parent refs / public, plus the agent ceiling) a list view applies **once** to rows.
- **`require(...)`** raises `AccessDenied(PermissionError)` / `AccessUnresolved(RuntimeError)`; **`decide_missing()`** renders a missing resource identically to not-visible.

**Resources are typed refs over one namespace** — `resource_ref(kind, path)` → `"<kind>:<path>"` (e.g. `cards:/users/<id>/cards/<card-id>`, `agents:/agents/<name>`), not a raw owner string. `KindSpec` names the kind, its path prefix, and the action→role mapping. **Kinds register through the `scitex_dev.access.kinds` entry point** — that is the single extension point; the surface never grows per app.

### 3. The answer — one well-formed record

Every answer is an **`AccessDecision`** (spec `scitex-access/1`) that **wraps** `scitex_dev.status.Check` with an `xch_` exchange id and a **closed, append-only `Reason`** (backed by `spec/reasons.yaml` + a drift test). `http_status` and `exit_code` (0/10/11, never 1/2) are **derived** from `(kind, reason)`, never serialised. Reasons include `owner / grant / inherited / org / public` (allowed); `role-too-low / agent-ceiling / owner-has-no-role / token-scope / not-visible / not-entitled` (denied); `credential-*` (not-signed-in); `enforcer-unreachable / identity-unresolved / kind-unregistered` (unresolved). This is the operator's 17:01Z requirement that *every access problem produces feedback in one fixed structure*.

### 4. CLI + surfaces (one implementation, thin adapters)

The CLI follows the fleet `dev <noun>` convention (like `dev secret`); the recommended noun is **`access`**: `scitex-<pkg> dev access check|list-kinds …` (+ `--json`), federated as `scitex-dev ecosystem dev access …`. The Python API, CLI, MCP tools, and hub HTTP API (`/api/access/*`) are all **thin adapters** over the one core — no app writes its own ACL command. "ACL" stays the internal data-structure name.

### 5. scitex-app's half (this repo) — the Django adapter

`scitex_app.access_django` translates `AccessFilter` (owners / resources / parents / public / agent ceiling) into Django **`Q` objects**, plus an **`AccessScopedManager`** so request code writes `Model.objects.for_principal(principal, action)` (and `Model.unscoped` stays greppable + audit-flagged). Content models get an `AccessScopedModel` mixin (indexed `owner` / `project`). The adapter is **proved with `from scitex_dev.access.testing import assert_equivalent; assert_equivalent(your_selector)`** — the evaluator must agree with the Django queryset and the store query on random fixtures (the hub's equivalence-suite requirement). The `scitex_app.authz` **Verdict** carries over unchanged; its decision-kind strings already match the core's five kinds, so it is **aliased/re-homed** (the core's `Decision`/`AccessDecision` is the canonical record). Manifest renames the operator approved: `data_lives_at` and `listing`. Exported via **`scitex_sdk.app`** (the 0.1.1 facade).

### 6. Authority + storage

- **Enforcers:** Gitea (repos/projects), hub DB (customer content), card store (fleet content), OS (`setfacl` mirror for files), sac (control plane). The hub resolves principals (users, orgs, agents) and exposes them via the existing `/api/me/` seam — so `check()` has no new hub-side dependency.
- **Grants live beside the enforcer** (hub Postgres `access_grant`; store `access_grants` with a hub mirror of org/delegation). **RLS is rejected for v1** (pgbouncer transaction mode + a second evaluator + owner bypass) — recorded in scitex-dev ADR-0014, cross-linking cards ADR-0017 ("a tenant is a store"). Isolation between users comes from `check`/`accessible` + per-adopter **zero-foreign-rows tests**, not DB separation.
- **Operator principle (17:38Z):** "treat everyone the same, me or a customer" — no internal/customer split; every human is a `user` principal, every agent `agent:<owner>/<name>`, all evaluated by the same rules; instance administration is a **grant** (`org:<instance>-admins`), not a separate data world.

## Consequences

- **Positive:** one stable, tested contract every app keys off; the operator's lost-Cards-tile class of bug is structurally removed; content ACL is proven by an equivalence suite; files get real OS-backed enforcement; every problem yields one well-formed, machine- and human-readable record.
- **Negative / cost:** the hub resolves principals via `/api/me/`; each app adds a boundary/zero-foreign-rows test; `accessible()` returns a filter, not a list, so callers apply it (a small but real API shape to teach); a DB migration + `AccessScopedModel` mixin per adopter.
- **Out of scope here (deliberate):** each app's STORAGE schema (rows carrying the grants/public columns) is the adopter's own follow-up against this contract — the SDK supplies the **evaluator**, not the storage.

## Alternatives considered

- **POSIX rwx/`mode` model** (this ADR's first draft) — superseded: it invented a new role vocabulary and a boolean-adjacent mental model; the operator's 16:25Z finding was that `scitex_dev.scope` (read/write/admin, Gitea-compatible) already exists and should be the vocabulary.
- **`can()` boolean** — rejected (15:55Z): mis-models the five answer kinds under truthiness.
- **Per-mount hand-rolled gates** — the status quo that already drifted once; ruled out (15:52Z).

**Cross-links:** scitex-dev PR #800 + ADR-0014 (RLS rejected for v1) + `scitex_dev.access`/`scitex_dev.scope`; hub `docs/MASTER/00_SECURITY_PERMISSION_ARCHITECTURE.md` (Layer 4); `scitex_app/authz.py` (Verdict — carried over unchanged); scitex-cards ADR-0017 ("a tenant is a store"); ADR 0001 (scitex-sdk consolidation — exported via `scitex_sdk.app`); card `sdk-authz-can-primitive-for-per-user-app-content-20260914`.
