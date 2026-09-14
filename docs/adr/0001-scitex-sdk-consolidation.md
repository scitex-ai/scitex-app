<!-- ---
!-- Timestamp: 2026-09-14
!-- Author: ywatanabe
!-- File: scitex-app/docs/adr/0001-scitex-sdk-consolidation.md
!-- --- -->

# ADR 0001 — Consolidate scitex-app + scitex-ui into one scitex-sdk project

- **Status**: Accepted
- **Date**: 2026-09-14
- **Deciders**: ywatanabe (operator), head-ywata-note-win (scitex-app, lead)
- **Affects**: the `scitex_app` package (this repo) and the `scitex_ui` package
  (scitex-ui repo); every fleet consumer that imports either (scitex-hub,
  figrecipe, scitex-writer, scitex-scholar, scitex-cards, scitex-agent-container
  GUI); the published distributions `scitex-app` and `scitex-ui`.

Companion ADR: scitex-ui `docs/adr/0003-scitex-sdk-consolidation.md` (PR #230,
merged `034a8c1`), which records the `scitex_sdk.ui` half. The two ADRs are
deliberately the same decision seen from each package's side.

## Context

The app contract (`scitex_app`) and the UI shell (`scitex_ui`) are released as
two separate distributions, but in practice they are one unit: consumers say
"the SDK (scitex-app, scitex-ui)" and must restate both names every time, pin
both, and track two changelogs that describe one capability. The operator
found the restatement tiring and read it as a signal the two should be one
project (Telegram 5319, 2026-09-14).

Measured coupling that makes the split a real cost, not just a naming
inconvenience:

- The **template contract spans both**: a leaf app extends
  `scitex_app/app_shell.html` (scitex-app), which delegates to
  `scitex_ui/standalone_shell.html` (scitex-ui). A change to the shell's block
  names has to be coordinated across two repos and two releases.
- The **version + scope + mount contracts** (scitex-app) render into the shell
  (scitex-ui); the **accent tokens + pane primitives** (scitex-ui) are
  consumed by the app contract. Neither half is meaningful to a leaf app
  without the other.
- Consumers must keep **both** pinned and in lockstep to get a coherent
  app+shell, even though only one logical capability is wanted.

Neither package imports the other at the Python level today (scitex-app's
`scitex-ui` is a *runtime/optional* dependency — the `ScitexUiRequiredError`
guard names it; scitex-ui does not import scitex-app). So the consolidation is
a **packaging/naming** decision with a real but bounded code-surface to
reconcile, not a dependency tangle.

## Decision

Consolidate into one project, **`scitex-sdk`**, exposing the two halves as
`scitex_sdk.app` and `scitex_sdk.ui`. Do it **facade-first** so nothing breaks
on day one, then move the implementation in gradually, then remove the shims
last.

### 1. One project, two submodules, boundary preserved

`scitex_sdk.app` is the app contract (from `scitex_app`); `scitex_sdk.ui` is
the UI shell (from `scitex_ui`). **The app/ui boundary is kept inside the SDK**
— `scitex_sdk.app` still does not import `scitex_sdk.ui` at the Python level,
and vice versa. The consolidation joins the *release unit*, not the *modules*.
This is load-bearing: the `ScitexUiRequiredError` guard and the bare-`pip
install scitex-app` case only make sense if `app` does not hard-depend on `ui`.
Merging the codebases into one import graph would undo that and is explicitly
**not** the goal.

### 2. Facade / re-export first (step 1) — no behavior change

The first `scitex-sdk` release is a **thin facade**:

- `scitex_sdk.app` re-exports the documented public surface of `scitex_app`
  **by identity** (the same objects); `scitex_sdk.ui` re-exports `scitex_ui`'s.
- The facade `depends on` both original distributions (it does not vendor
  them yet).
- Tests assert `scitex_sdk.app.X is scitex_app.X` (and the `.ui` half) — an
  identity bar, not a name-count bar. A copy or reimplementation fails.

Identity is what makes the consumer migration **mechanical**: a
`from scitex_app import X` -> `from scitex_sdk.app import X` rewrite changes
zero behavior, so it can be done by tool and reviewed as a diff.

### 3. Prompt mechanical consumer migration — not a long deprecation tail

Once the facade releases, consumers migrate their imports **promptly** with a
mechanical rewrite (one PR per consumer repo), not over a long deprecation
window. The operator's explicit rationale: "usage may change a bit, but fix
aggressively now while it's early; it looks mechanical." Small API adjustments
are acceptable **now** (early, cheap) and must each be recorded in the
CHANGELOG. The original `scitex-app` / `scitex-ui` distributions become thin
compat **shims** (re-export + `DeprecationWarning`) so nothing breaks if a
consumer has not migrated yet, and the shims are removed **last** — only after
every consumer is migrated and released.

### 4. Version scheme

`scitex-sdk` carries its **own** version (starts `0.1.0`), independent of the
wrapped packages. Each half keeps its own version through the migration window
(`scitex_app.__version__`, `scitex_ui.__version__`); consumers pin the
umbrella `scitex-sdk` version and the facade's floors on the **published**
versions of the halves. The half versions converge with the codebase as the
implementation moves in; the umbrella version is the single thing consumers
track once the move completes.

### 5. History + naming

Preserve git history where practical (subtree / filter-repo) as the
implementation moves. The irreversible naming bits — the GitHub repo
(`scitex-ai/scitex-sdk`), the PyPI project (`scitex-sdk`), and any npm name —
are reported **before** registration and gated on operator sign-off. The
scitex-ui JS/TS side is `@scitex/ui` and is `private: true` (consumed via
`file:`/vendored copy, never a public npm publication), so no public npm name
changes at the facade step (scitex-ui ADR 0003; open for override at the
move step).

## Consequences

- **Positive**: one name, one version, one changelog for the app+shell unit;
  the cross-package template/version contracts live in one repo; consumers
  stop restating both distributions.
- **Positive**: facade-first + identity tests + shims = non-breaking; any
  consumer can rewrite mechanically and nothing breaks until the shims are
  removed (after everyone has migrated).
- **Cost**: a migration window where both the facade and the shims exist, and
  a one-time mechanical rewrite across ~6 consumer repos.
- **Cost**: the `app`/`ui` boundary must be *enforced* inside the SDK (no
  cross-import), or the consolidation silently regresses into a monolith that
  breaks the `ScitexUiRequiredError` bare-install case.
- **Reversible**: steps 1–3 are reversible (the facade is additive; the shims
  keep the old paths working). Only the name registration is irreversible, and
  it is gated on operator sign-off.

## Open items (not decided by this ADR)

- The **PyPI trusted publisher** for `scitex-sdk` is an operator action
  (PyPI console); the release is blocked on it, not on code.
- The exact `scitex_sdk.ui.__version__` semantics (facade's own vs
  re-exported `scitex_ui.__version__`) — reconciled in the facade ui-surface
  review, where identity (`is`) is the bar.
- Mobile-layout work (card
  `ui-mobile-layout-primitives-extract-from-apps-20260914`) lands in
  `scitex-sdk` **if** the move comes first; the two are independent and must
  not block each other.
