# Changelog

All notable changes to `scitex-app` are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Internal
- **The `stx-mount` marker name is now checked across packages AND languages.**
  It is declared four times — `_django.py` (which renders it), `embed.py`'s
  no-Django fallback, `scitex_ui/mount.py`, and scitex-ui's `mount.ts` (which
  reads it in the browser) — and nothing enforced agreement; scitex_ui's own
  comment said "must match mount.ts" and admitted no mechanism. A rename on one
  side degrades either to a thrown error or, in the other ordering, to a page
  that renders perfectly and 404s its API only under a mount. The check reads
  the TypeScript constant out of scitex-ui's shipped source, so it needs no
  checkout, and SKIPS when scitex-ui is absent — scitex-app does not depend on
  it and must not.

### Added
- **`scitex_app.authz` — the authorization verdict, as a value rather than a
  boolean.** `can()` itself is not here yet; the type ships first because
  scitex-ui is building the display side against a shape agreed in a message
  thread, and a contract that lives only in a thread drifts. Four kinds
  (`allowed`, `denied`, `denied-because-not-signed-in`,
  `denied-because-not-entitled`), `kind` as the discriminant, payload travelling
  with the verdict so nobody reconstructs the reason, and a validator that
  enforces payload ABSENCE as well as presence — a plain denial that offered a
  sign-in URL would tell a user to do something that cannot help. Deliberately
  no `.allowed` boolean: it reads naturally, passes review, and silently treats
  "sign in first" as identical to "never".

### Internal
- **`import scitex_app` is now asserted not to import Django or `scitex_ui`.**
  0.11.0 made `_standalone` — the module that runs Django servers — import
  eagerly at package root, and nothing checked that it stayed cheap. The
  existing import-smoke leg installs the extras, so Django is present there and
  it would pass whether or not the property held. The new test runs in a
  subprocess so the assertion is independent of what the runner has installed,
  and it is load-bearing for someone else: scitex-scholar made scitex-app a hard
  dependency and retired their "not installed" fallback, so an import-time
  regression here is now an outage there rather than a downgrade.

## [0.11.0] - 2026-09-03

Minor: `hosts_to_allow` becomes public API, and the app validator gains a warn
tier plus the three checks its own documentation had been promising. Released
now because figrecipe and scitex-scholar are each holding a verbatim copy of
`hosts_to_allow` and cannot replace it with an import until the public name
ships.

### Added
- **`scitex_app.hosts_to_allow(host)` is now public** — what a `--host` bind
  implies for Django's `ALLOWED_HOSTS`. It became public because it was about to
  be depended on privately: scitex-scholar and figrecipe each carried a verbatim
  copy, and on 0.10.1 both were replacing it with
  `from scitex_app._standalone import _hosts_to_allow`. Three repositories
  committing to an underscore path is a promise nobody made, and deciding the
  name before the dependency exists is cheaper than deprecating an accidental
  one after. `_hosts_to_allow` survives as a migration alias so the in-flight
  PRs that were told to use it keep working; it is removed once both have
  swapped (card `app-retire-private-hosts-to-allow-alias`).
- **The three checks the docs promised and nothing ran.** JS dangerous-pattern
  scanning, a bundle-size cap and manifest privilege validation existed in
  `scitex_app.validator.AppValidator`, worked, were covered by tests, were
  described to app developers by the shipped skill doc — and were called by
  nothing; the CLI read no `.js` file at all. Ported into the live path as
  `validate_js` / `validate_bundle_size` / `validate_privileges`, each behind a
  `check_*` keyword defaulting to `False`, so no caller's results change today.
  The JS pattern list was narrowed from nine to five on measurement: the four
  dropped were the Python forbidden list copy-pasted into a JS scanner, and
  `exec\s*\(` produced the only finding either peer repo had — `re.exec(line)`
  in a `while` loop, i.e. correct JavaScript.

### Changed
- **Advisory validator findings no longer fail a build.** `appmaker.validate()`
  returned one flat list and the CLI does `raise SystemExit(1)` on any entry, so
  "should" and "must" were indistinguishable to the only thing acting on them.
  Two findings were worded as advice and enforced as failures — the
  `name` must end in `_app`/`-app` convention, and the deprecated `--color-*`
  CSS variables — and the first was UNCLEARABLE: an app whose correct name would
  COLLIDE with an existing registry entry could satisfy the rule only by
  creating the collision. New `appmaker.validate_with_warnings(app_dir)` returns
  `(errors, warnings)`; `validate()` keeps its signature and now returns errors
  only. `scitex-app app validate` prints advisory notices in yellow and exits
  non-zero only on errors. The remaining error-tier findings are unchanged.

### Fixed
- **Two false-positive classes in the mount-prefix scan**, both found by running
  it against real app packages rather than fixtures. `xhr.open("GET", url)` was
  reported as `inferred-base request URL 'GET'` — XHR's first argument is the
  METHOD, so the remediation told the author to join a verb to the mount; XHR
  URLs are now read from the second argument. And bundler configs were scanned
  despite the rule's own docstring excluding them, reporting
  `new URL(".", import.meta.url)` in `vite.config.ts` — Node's `__dirname`
  idiom, evaluated at build time, reaching no browser. Measured on
  scitex-writer: 8 findings before, 5 after, with the 3 removed being exactly
  these; scitex-scholar (known-clean) stays at 0 and figrecipe's published
  0.34.6 stays at 6, so no true positive was lost.

### Internal
- `appmaker/_validate.py` (537 lines) split into a package of one module per
  concern — app layout, security, manifest, frame rules, dependencies, prefix
  safety — with the full re-export surface preserved on `_validate`, so
  `from scitex_app.appmaker._validate import <anything>` is unaffected. Tests
  moved to the mirror directory the project-structure audit requires; the test
  NAME set is identical before and after.

## [0.10.1] - 2026-09-02

Patch: a server bound to `0.0.0.0` now answers on the addresses it is
actually reachable at. Released immediately — scitex-scholar 1.9.0 and
figrecipe 0.34.6 are both hitting the 400 in the field, and both carry a
local copy of the fix that they replace with an import from this wheel.

### Fixed
- **`_allowed_hosts` now honours a `0.0.0.0` bind.** It appended the bound
  host *string*, and `"0.0.0.0"` was already in the base list, so `--host
  0.0.0.0` contributed nothing and a request carrying the real interface
  address in its Host header was refused with 400 `DisallowedHost` (measured
  2026-09-02 by scitex-scholar on 1.9.0 and by figrecipe on 0.34.6; this
  function's own docstring had recorded the figrecipe symptom on 08-23). The
  bind now contributes what it implies: loopback nothing, a concrete address
  itself, `0.0.0.0` the hostname plus every interface's IPv4 read from the
  interfaces (`SIOCGIFADDR`) — not from name resolution, which inside a
  container returns addresses that are not the LAN interface. Never widened
  to `"*"`. The derivation is scitex-scholar's `_hosts_to_allow` (PR #137)
  verbatim, so scholar and figrecipe can replace their copies with an import.

## [0.10.0] - 2026-08-23

Minor: `run_standalone()` gains language activation. Released now rather than
batched because scitex-hub is building against the i18n contract today and
cannot, while it exists only on `develop`.

### Added — standalone can actually render a non-English language

Catalog *discovery* was already free: Django auto-discovers
`<app>/locale/<lang>/LC_MESSAGES/django.mo` for anything in `INSTALLED_APPS`,
with no `LOCALE_PATHS` and no cooperation from the host. **Activation** was
missing. Nothing ever called `activate()` and `LANGUAGE_CODE` sat at Django's
`en-us` default, so a standalone app could ship a complete, working Japanese
catalog, load it, and render English forever.

`_configure_django()` now sets:

- `LocaleMiddleware`, before `CommonMiddleware` per Django's ordering requirement
- `USE_I18N` explicitly, rather than inheriting a default that could move
- `LANGUAGE_CODE` from `SCITEX_LANGUAGE_CODE` (default `en-us`)
- `LANGUAGES` from `SCITEX_LANGUAGES` (comma-separated), **omitted entirely when
  unset** — passing `[]` would assert "this app supports no languages", the
  opposite of "the app did not say"

### Added — a declared language with no compiled catalog now says so

A language in `LANGUAGES` with no `.mo` does not error: gettext falls back to the
source string, so it reads as *"nobody has translated it yet"* rather than *"the
mechanism is broken"*. Startup now names the language, states that its strings
will render as source, and names the likely cause.

It **prints rather than raises** — a missing translation must not stop a server
starting, and refusing to serve English because Japanese is absent would be worse
than the bug. It checks for the **compiled** `.mo` only, because a `.po` without
its `.mo` is exactly the shape that ships green.

**`msgfmt` is absent** from this container, from scitex-hub's container, and from
`scitex-hub-prod-django:latest` — the image serving production. Three
environments, three absences. `django-admin compilemessages` shells out to it, so
compile at build time via a pure-Python path and ship the `.mo` inside the
distribution.

### Fixed — `serve --host <addr>` bound correctly and then 400'd every caller

`ALLOWED_HOSTS` was a hardcoded loopback-only literal while `--host` accepted any
address, so the server printed `serving at http://<addr>:<port>` and rejected
every request. The banner asserted the opposite of the truth.

The bound host is now always allowed — binding to an address is the statement
that you intend to be reached on it — plus `SCITEX_ALLOWED_HOSTS`
(comma-separated) for the proxy/tunnel case.

Deliberately **not** widened to `["*"]` under `DEBUG`. These apps ship no
authentication and `DJANGO_DEBUG` defaults to `"true"`, so a wildcard would make
every reachable address an unauthenticated reader by default.

**This does not fix embedded leaf apps** that set `DJANGO_SETTINGS_MODULE` and
call `django.setup()` before `run_standalone()` — `_configure_django()` returns
early when settings are already configured, so their own `settings.py` supplies
`ALLOWED_HOSTS` and this change never executes for them. Verified by
scitex-scholar against their running process.

### Documentation

- `35_i18n.md` — the locale convention for mounted apps, leading with the silent
  fallback rather than the layout.
- `05_standalone.md` — states that `run_standalone()`'s settings apply **only if
  Django is not already configured**, with the one-line check to confirm which
  settings you actually got. It previously caveated only re-entrancy.
- `07_backend-validation.md` — the CLI runs `appmaker.validate`, not
  `AppValidator`; neither is a superset of the other, and the doc now carries the
  measured coverage table. It also told developers to add a `version` key that
  both implementations reject.

## [0.9.1] - 2026-08-20

### Fixed — the prefix check flagged the fix it prescribes

0.9.0's `validate_prefix_safety` reported this as `inferred-base`:

```js
`${STX_MOUNT}/api/search?${params}`
```

which is exactly what the finding's own remediation text tells an app to write.
The rule condemned its own prescribed fix. Found by scitex-scholar within
minutes of 0.9.0 publishing, by running the check against a tree they knew to
be **correct** — the only configuration in which a false positive is
distinguishable from a true one.

The discriminator was syntax, not semantics. Same variable, same correct code:

| form | 0.9.0 |
| --- | --- |
| `fetch(STX_MOUNT + "/api/x")` | passed (concatenation) |
| `` `${STX_MOUNT}/api/x` `` | **flagged** (template literal) |

Interpolation is precisely when a URL stops being a bare literal, so a
correctly-fixed site that needs a query string is *forced* into the flagged
form.

**Root cause: a three-valued signal collapsed into two.** A literal opening with
`${…}` is *variable-prefixed* — neither root-absolute nor document-relative,
because what precedes the path is a value the scanner cannot see. 0.9.0 folded
that unknown into "inferred-base".

The fix is deliberately narrow: a leading `${STX_MOUNT}` (see
`MOUNT_IDENTIFIERS`) is satisfied; a leading `${anythingElse}` is *unknown* and
is not reported, recorded as an explicit exclusion. Deciding whether an
arbitrary variable holds the mount requires its value, and inferring it is what
produced the bug.

**Not blunted.** The known-answer control was re-run: scholar's shipped wheel
still reports exactly its three root-absolute sites. Two further test arms exist
solely to prevent this becoming a blanket amnesty — a genuinely root-absolute
and a genuinely relative URL must still be flagged.

No behaviour change for anyone who did not opt in: the check remains **unarmed**
(`validate()` skips it unless `check_prefix_safety=True`), so 0.9.0 could not
have failed a build on this.

## [0.9.0] - 2026-08-20

### Added — mount-prefix safety check, SHIPPED UNARMED

`scitex_app.appmaker.validate_prefix_safety()` reports request URLs that do not
resolve under an app mount. **It is a record, not a gate.** `validate()` skips it
unless `check_prefix_safety=True`, so nothing fails on it — flipping that default
is the arming action, and it has not been taken. Arming today would fail apps
whose fixes are not yet released.

Two classes are reported, and the second is why the check exists:

| class | example | behaviour |
| --- | --- | --- |
| root-absolute | `fetch("/api/x")` | ignores the mount; 404s everywhere, so it gets found |
| inferred-base | `fetch("api/x")` | resolves against the *document* URL — works at `/app/`, 404s at `/app` |

The second passes a smoke test and breaks on a redirect. A root-absolute-only
rule would miss it. Platform routes (`/platform/api/`, `/apps/store/api/`) are
exempt — hub owns them, they live at the server root, and prefixing them breaks
them.

Known limits, stated because an enumeration's exclusions are invisible in its
output: no dataflow, so a URL built across statements or bound to a name that
does not look url-ish is missed; static/asset base paths (a bundler `base`
setting) are out of scope as a build-config concern with different correct
answers.

### Fixed — template and CSS validation were unreachable for every `_`-prefixed app

`validate()` skipped `validate_templates` and `validate_css` whenever
`_is_embedded_package()` was true, and that returns true from the **directory
name alone** (`root.name.startswith("_")`), before any manifest is read. So every
app living in `_django/` had both checks unconditionally off — listed, invoked,
and structurally unreachable.

The comment gave it away: *"embedded packages use compiled React builds"* is a
claim about the FRONTEND, while the condition tested the PACKAGING. An embedded
app declaring `frontend_type: "vanilla"`, with hand-written Django templates and
CSS and no React build anywhere, was skipped regardless.

The skip is now keyed on the property the comment always claimed:

```python
if not is_embedded or (frontend_type and frontend_type != "react"):
```

**Strictly additive — no app loses a check it had:**

| case | before | after |
| --- | --- | --- |
| non-embedded, any type | runs | runs |
| embedded + `"react"` | skipped | skipped |
| embedded + declared other | **skipped** | **runs** |
| embedded + undeclared | skipped | skipped |

`frontend_type` is deliberately not tested as `!= "react"` alone: the field is
inconsistent in the wild (`"html"`, `"django"`, `"vanilla"` all appear, and the
default differs by module), so only `"react"` reliably means compiled. An
undeclared app is left alone rather than guessed at, since guessing would invent
findings on compiled output.

**Upgrade note.** If your app is an embedded package that declares a non-React
`frontend_type`, template and CSS validation will run against it for the first
time and may report findings you have not seen before. That is the fix working.

## [0.8.1] - 2026-08-18

No code change. `scitex_app` behaves identically to 0.8.0.

### Documented — 0.8.0's root prefix is `""`, which is FALSY

**If you are migrating from 0.7.x, delete any `|default`, `||` or `or` around
the mount prefix before you do anything else.** Under 0.7.x those were correct
and harmless: `"/"` was the right root, so writing a default was sensible.
0.8.0 made the root the empty string, and every "use this when empty" idiom
now silently restores the withdrawn value:

```django
{{ stx_mount|default:'/' }}    ← renders "/" at root
```

which makes the documented join produce `//api/x` — protocol-relative, which
the browser resolves to a **different host**. That is the exact failure 0.8.0
was cut to prevent, reintroduced by a line that was correct when it was
written. Django `|default:`, Jinja `|default()`, JS `||` and Python `or` all
fire on `""`; use `??` or an explicit `is None` if you need a fallback.

**Migrating is ONE coordinated change; the half-fix is worse than not
starting.** Two things inverted together — the root value became falsy, and the
slash moved from the base to the endpoint. Drop the default but keep
`base + "api/x"` and you get `<prefix>api/x`; flip the join but keep the default
and you get `//api/x`; fix the template but not the bundle and a `||` restores
the old value anyway. Grep template default, base read and every fetch site
before changing one. *(scitex-writer found this — all three faces are present
in their app at once.)*

Found by **scitex-scholar** while migrating, before it shipped. Their tell is
worth repeating: a guard test that should have flipped after the migration kept
passing. A test that survives a breaking change unchanged is evidence about the
test.

This is the server-template twin of the `?? "/"` removed from the client half
in 0.8.0 — that instance was fixed and documented for JS, and the same warning
was not carried to the side where the idiom was *more* likely, because the old
convention rewarded writing it.

### Changed — the contract page is split

`33_mount-prefix.md` (162 lines) is now the contract; `34_mount-prefix-rationale.md`
holds the reasoning. The decisive argument — the failure-mode table showing
`//api/x` resolving off-origin — stays **inline in the contract**, because it is
what must not be undone; only secondary material moved, with the contract
pointing at it.

Both ship in the wheel, which is why a documentation-only change gets a
release: the page a consumer reads is the one in the artifact they installed,
and the misleading version was the one on PyPI.

## [0.8.0] - 2026-08-18

### BREAKING — `stx-mount` carries no trailing slash

Root is now `""` (was `"/"`); embedded is `"/apps/u/x"` (was `"/apps/u/x/"`).
**The slash moved to the endpoint**: write `base + "/api/x"`, not
`base + "api/x"`. 0.7.0–0.7.1's convention is withdrawn two days after it
shipped.

**Why, and it is not a preference.** scitex-ui ships its own `mount_prefix`
with the opposite convention on the *same* meta tag name, in the same venv.
Two SDKs, one tag, incompatible semantics — that had to collapse to one, and
both conventions produce **identical correct output**, so testing correct
usage cannot choose between them. Running each one's *likeliest mistake*
through a real URL resolver can:

| convention | likely mistake | result |
|---|---|---|
| 0.7.x `"/"` + `"/api/x"` | endpoint written with a leading slash | `//api/x` → **`https://api/x` — a different host** |
| 0.8.0 `""` + `"api/x"` | endpoint missing its slash | `https://site/api/x` (root, accidentally fine) |
| 0.8.0 `"/apps/u/f"` + `"api/x"` | same | `/apps/u/fapi/x` — 404, right host |

`//api/x` is protocol-relative: the browser sends the request, **and whatever
it carries, off-origin**. The withdrawn convention's most natural error leaves
the site; this one's 404s on the right host. scitex-hub confirmed this was
their surface too, since hub is what embeds apps.

### BREAKING — the reader throws instead of defaulting to root

`?? "/"` is gone from the contract. A default is indistinguishable from a
correct read, which is exactly how scitex-scholar's prefix fix nearly shipped
as a silent no-op: nothing emitted a marker, the fallback returned root, and
the diff looked complete.

### Fixed — the 0.7.1 derivation was wrong for any non-root view

0.7.1 handed template-rendered apps a copyable one-liner that assumed the view
sits at the app root. Measured: correct at the root, **wrong in 3 of 5 cases,
every wrong one a non-root view, and wrong silently**.

`request.path` is the whole path — the mount prefix *plus* the route the view
occupies — so only the view can subtract it, because only the view knows it.
New `mount_prefix(request, view_path=...)` does, and raises
`MountPrefixMismatch` rather than returning a best guess. `scitex_editor_page`
takes `view_path` too; its default `""` remains correct for `scitex_urlpatterns`,
which registers it at the mount root.

### Migrating

```js
// before (0.7.x)
const base = document.querySelector('meta[name="stx-mount"]')?.content ?? "/";
fetch(base + "api/x");

// after (0.8.0)
const el = document.querySelector('meta[name="stx-mount"]');
if (!el) throw new Error("stx-mount marker missing");
fetch(el.content + "/api/x");
```

Template apps: replace any hand-copied derivation with
`from scitex_app.embed import mount_prefix`, passing your view's own route.

### Credit

The implementation properties are **scitex-ui's** — throw rather than guess,
subtract `view_path` rather than assume root. They argued *against their own
scope*, separating "which code survives" from "which package owns the
contract", and that argument is why the contract stayed here while their design
won. Their `mount.py` also reasoned out the `SCRIPT_NAME` double-prefix trap
and the `resolver_match.route` dead end first. The compare-failure-modes rule
is **scitex-scholar's** generalisation.

## [0.7.1] - 2026-08-18

- **docs(mount-prefix): the SDK does not inject into templates you render
  yourself.** 0.7.0's contract page said "if you serve your shell through
  `scitex_editor_page`, the marker is present" and never stated the other case.

  scitex-scholar nearly shipped through the gap. Their view does
  `render_to_string(...)` — a Django template, not a built SPA shell — so
  nothing injected the marker. Their four client-side changes would have read no
  marker, hit the `?? "/"` fallback, and reproduced the previous behaviour
  exactly, while looking correct in the diff. The page still renders; only the
  API calls 404, and only under a prefix. It was five sites, not four, and the
  fifth would have made the other four useless.

  The page now carries a second "does not" beside the asset-rewriting one, with
  the two-line derivation to copy so a leaf's copy cannot drift from the SDK's,
  and explains why this is **not** an SDK gap: a template-rendered app is
  *writer-shaped*, not *SPA-shaped* — the case `data-api-base` was invented for,
  where the server already owns the HTML. `scitex_editor_page` exists only
  because a built SPA's `index.html` is opaque bytes the server did not author.
  Same contract, two shapes; automatic injection covers one.

  Also records a foot-gun the page's own example invites: two classic `<script>`
  tags each declaring `const STX_MOUNT` share one global scope, so the second is
  a `SyntaxError` that breaks the **whole page**, not just that file.

- **Why a patch release for a documentation change.** The contract page ships
  *inside the wheel* (`scitex_app/_skills/scitex-app/33_mount-prefix.md`), so a
  doc fix that is not released does not exist for the people it is written for —
  and the misleading version is the one currently on PyPI. That is the same
  failure 0.7.0 was cut to end, one level down: 0.7.0 existed only because a
  working contract had been sitting unreleased on `develop` while three
  consumer apps each invented their own answer to a question the SDK had already
  answered. Shipping the correction immediately is the consistent move.

  No code changed. `scitex_app` behaves identically to 0.7.0.

## [0.7.0] - 2026-08-18

- **feat(django): the SDK now tells the browser where the app is mounted.**
  `scitex_urlpatterns` was already prefix-agnostic on the server — its patterns
  are relative, so `include()` works under any root — but nothing told the
  *browser*. Client code had no supported way to learn its mount point, so
  leaves hardcoded `/`: correct standalone, silently broken the moment the app
  is embedded under a prefix.

  `scitex_editor_page` now injects a marker into the served shell:

      <meta name="stx-mount" content="/apps/u/figrecipe/">

  The value is derived server-side from `request.path`. That is exact rather
  than a guess: the view is registered at `path("", ...)`, so its request path
  *is* the mount prefix. Never compute it client-side.

  **Prior art, and it is not ours.** scitex-writer hit this first and solved it
  in its own templates — `data-api-base="{{ api_base|default:'/' }}"` read back
  as `root.dataset.apiBase`, with relative endpoint names joined onto it. That
  pattern *is* the contract; `stx-mount` is simply the SDK's supported way to
  obtain the base, so every app gets it without inventing a third mechanism.
  Read the marker, join relative endpoint names onto it, and the same build
  works at `/` and under any prefix.

  **Why a `<meta>` and not `<base href>` or a template render.** A built SPA's
  `index.html` routinely contains `{{` and `{%` inside inlined JS. Running it
  through Django's template engine would try to interpret those and corrupt the
  bundle for reasons unrelated to mounting. The injection is therefore a plain
  string insertion that adds exactly one tag and touches nothing else. It is
  matched against `<head>` / `<head ...>` specifically — a substring search for
  `<head` also matches `<header`, which placed the marker inside a `<header>`
  element on documents that had one and no real head. Where there is no head at
  all the tag is prepended, which is still correct (the parser hoists a leading
  `<meta>`), so the prefix is never silently dropped.

- **Why this is a minor bump, stated plainly because the omission is the
  lesson.** The feature above landed on `develop` while `pyproject.toml` still
  read `0.6.1` — the same string already published to PyPI and already
  installed across the fleet. Two different builds wore one version number, so
  "am I on 0.6.1?" answered *yes* for a build that lacked the feature and *yes*
  for a build that had it. A version string that cannot distinguish them has
  stopped being an identifier. The practical cost was real: three consumer apps
  looked as though they had ignored a contract that, from where they sat, did
  not exist.

- **test(django): one assertion per test**, and the mount marker is pinned
  against both real mounts it exists to span — `/` standalone and
  `/apps/u/<module>/` as a scitex-hub built-in app.

- **fix(ci): auto-merge counted QUEUED checks as green.** A check still sitting
  in the queue is not a passing check; treating it as one made the gate report
  success before the evidence existed.

- **chore(audit-config): retire 8 PS-224 exemptions measured inert**, and
  relocate the security reasoning into the workflows themselves, so the reason
  lives next to the thing it justifies.

## [0.6.1] - 2026-08-05

- **fix(gui-launcher): `--force` could SIGTERM an unrelated process.**
  `argv_is_ours()` scanned the whole argv including `argv[0]` — the
  *interpreter* path. A project-local venv puts the project name in that path,
  so `/home/x/<project>/.venv/bin/python` claimed **every** process started
  from that venv as ours: a test run, a jupyter kernel, an unrelated dev
  server. Since `serve_gui(--force)` terminates on `holder.ours`, the flag
  could kill a stranger whose only connection to us was the directory its
  interpreter happened to live under — precisely the failure `--force` exists
  to avoid.

  0.5.0's own note claimed ownership "is proven from the holder's argv, not
  its name". The proof was weaker than the sentence: the documented
  counter-example (`myscitex_writerx` does not match) is about **token
  boundaries** and said nothing about **path segments**.

  `argv[0]` now contributes only its last two path components — the program
  and the directory immediately containing it. One level up is what a program
  *is*; three levels up is only where it lives. Everything after `argv[0]` is
  matched whole, so module paths still count:

  | argv[0] | verdict |
  |---|---|
  | `/opt/venv/…/scitex_writer/__main__.py` | ours — parent names it |
  | `/usr/local/bin/scitex-writer-gui` | ours — script names it |
  | `/home/x/<project>/.venv/bin/python` | **not** ours |
  | `/home/x/<project>/.venv/bin/jupyter` | **not** ours |

  All four are pinned by tests, so the boundary cannot drift silently in
  either direction. Reported by scitex-scholar with a deterministic
  reproduction in which only `argv[0]` differed.

  Known residual, documented in the docstring rather than left implied: a
  stranger run as `python /home/x/<package>/run.py` still matches, because a
  script living inside the package tree is real argv evidence.

## [0.6.0] - 2026-08-05

- **security(paths): caller-supplied path components are now validated and
  contained.** `scitex_app.paths` joined `owner` / `repo` / `slug` straight
  onto a filesystem root with no validation and no containment check. On the
  hub these were not exploitable for traversal only because Django's `<str:>`
  URL converter excludes `/` — a property of the **routing layer**, not of
  this module. Every other consumer lost that: a CLI caller, a service
  embedding the package, or a future `<path:>` route on the hub itself, which
  would have silently re-opened it. A guard that holds only because of what
  some caller upstream happens to do is not a guard.

  Measured before the fix: **3 of 14** behaviours safe. Cross-tenant reach was
  real, not theoretical — `owner="alice"`, `repo="../../bob/proj/bobrepo"`
  returned bob's actual project directory. An absolute component escaped the
  base directory entirely, because `Path("/a/b") / "/c"` is `Path("/c")`:
  pathlib silently discards the root. After: **14 of 14**.

  Both checks are required and neither substitutes for the other. Per-segment
  validation alone misses a symlink planted inside the root; containment alone
  misses cross-tenant reach, because `owner="alice/../bob"` lands on a
  directory that is still *inside* the base dir.

  Fixed across the whole family, not just the two functions first reported:
  `resolve_user_project_dir`, `resolve_published_project_dir` (identical
  defect on `slug`), `parse_dev_module_name`, `resolve_manifest`,
  `resolve_template_dir`, `resolve_static_dir`, and `find_partial_template`
  (whose caller-supplied `filename` was never validated — a traversal filename
  read any file on the host).

  **Not a breaking change for correct callers.** A refusal returns `None`,
  which is the module's existing "not found" answer, so a probe stays a 404
  rather than becoming a 500. Refusals are logged with `%r`, so a hostile name
  cannot inject control characters into your logs. Package-side half of
  scitex-hub #527.

- **Breaking (install surface): `dev` and `docs` are PEP 735 dependency
  groups, not extras.** Requesting either as a bracketed extra no longer
  resolves; use `pip install -e . --group dev` (pip ≥ 25.1), or `--group
  docs` to build the documentation. `[all]` is unchanged and remains the only
  public extra.

  This keeps the build toolchain out of the user-facing install: `[all]` must
  give every runtime capability and no pytest, ruff or sphinx. Groups are not
  `[project.optional-dependencies]`, so the closure rule that would otherwise
  force the toolchain into `[all]` no longer applies to them.

  If you install the toolchain with an unknown extra, note that pip **warns
  and still exits 0** — so a `pip install -e ".[dev]" || fallback` chain will
  never reach its fallback and will silently install nothing. Request groups
  with `--group`, which fails loudly on a tool that does not support them.

- deprecate(chat): `LLM_MODEL` is renamed to `SCITEX_APP_LLM_MODEL`. The old
  name still works and logs a deprecation warning; it is aliased rather than
  renamed because it was a published, documented contract. If both are set the
  prefixed one wins **and the conflict is logged** — the pick is never silent.
  The unprefixed name is being retired because it is generic enough to collide
  with another tool in the same environment, which would quietly change which
  model you talk to.

## [0.5.0] - 2026-07-19

- fix(gui-launcher): `--force` now reclaims an **orphaned** instance of
  our own app — one still holding the port after dying without clearing
  its runtime state, and therefore invisible to `status()`. That is the
  exact case the flag exists for, and it was the one case it refused,
  then printed remedies that ignored `--force` entirely. A flag that
  names the fix and does not perform it is the same bug as an install
  hint that installs nothing. (scitex-writer finding, 2.31.0)

- fix(gui-launcher): ownership is proven from the holder's **argv**, not
  its process name. A `comm` of `python` names nothing and is shared by
  every Python server on the box — terminating on that evidence would
  terminate strangers.

- fix(gui-launcher): `port_holder` no longer reports "a process owned by
  another user" when the truth is "this `/proc` will not let us look".
  Our agent containers deny `/proc/<pid>/fd` even for a same-uid
  process, so the module built to prevent confident wrong answers was
  giving one. It now returns a validated `PortHolder` dataclass whose
  `status` is one of the declared `free` / `identified` / `unreadable`,
  and whose `ours` is three-valued (`True` / `False` / `None` = we could
  not look).

  **Breaking (public API):** `embed.gui_port_holder()` and
  `_gui_runtime.port_holder()` now return a `PortHolder` instead of
  `dict | None`. Callers checking `if holder is None` should use
  `if not holder.in_use`; `holder["pid"]` becomes `holder.pid`. Both
  gain an optional `package` argument that populates `ours`.

  The holder-identification path is proven against real listening
  sockets on a host; inside our containers those tests **skip**, because
  `/proc/<pid>/fd` is unreadable there. Stated rather than papered over
  — claiming a green we did not get is the failure mode this change
  exists to fix.

## [0.4.2] - 2026-07-13

- chore: consolidate optional-dependencies into a single `[all]` extra
  (operator directive, prompted by scitex-writer PR #322). Extras are
  now all-or-nothing — `chat`/`chat-all`/`cli`/`cloud`/`django`/`mcp`
  collapse into one `[all]`; `dev`/`docs` stay separate (those are for
  building the package, not using it). `cli = []` was already empty
  (click/rich moved to base `dependencies` earlier) — an install hint
  that resolves to a no-op looks like a fix but installs nothing, and
  the user believes they already tried it. Every install-this-extra
  hint (formerly naming `mcp` or `cli`) across the CLI, skill docs, and
  sphinx docs now points at `all`. Added `tests/develop/test_extras.py`,
  which reads the real `pyproject.toml` and fails if any extra is
  empty or any referenced extra name is missing/empty.
  (#54)

## [0.4.1] - 2026-07-13

- fix(gui-runtime): `_gui_runtime.state_path(package)` now honors a
  `SCITEX_<PACKAGE>_GUI_STATE` env override before falling back to the
  `scitex_config` resolution, matching scitex-writer's pre-existing
  `SCITEX_WRITER_GUI_STATE` convention (dropped during the 0.4.0
  generalization from writer PR #316). This repo bans mocks/
  monkeypatch, so the env var is the only channel available to a
  subprocess-driven end-to-end CLI test (`gui serve` run as a real
  subprocess) — without it, such a test writes to the developer's
  actual runtime state instead of a temp file. (#51)

## [0.4.0] - 2026-07-13

- feat: add `scitex_app.embed`, a public host-embedding API. 3+ consumers
  (figrecipe, writer, scitex-todo) were reaching into the private
  `scitex_app._django` / `scitex_app._standalone` modules for
  host-embedding, including one hard top-level import. Root cause was
  our own skill docs and app-scaffold templates teaching that private
  import pattern to every consumer; both now reference
  `scitex_app.embed`, so newly scaffolded apps stop reproducing it.
  `scitex_app.chat`'s own docstrings and docs/APP_SDK.md are also fixed
  — `from scitex_app.chat import X` raises `ModuleNotFoundError` because
  `chat` is a lazy `__getattr__` attribute, not a real submodule; the
  working form is `from scitex_app import chat` then `chat.X`. (#48)
- feat: add a shared GUI launcher (`scitex_app.embed.serve_gui` +
  `scitex_app._gui_runtime`), generalized from scitex-writer's `gui
  serve` runtime module (writer PR #316). Binds the exact port or fails
  loud (never drifts to the next free port), refuses a second instance
  via runtime state (self-healing a stale recorded pid), identifies a
  foreign port holder via `/proc` (no `ss`/`lsof` shell-out), and
  `--force` only ever stops the instance recorded in its own runtime
  state — never a process it does not own. Scaffolded apps' `gui
  --force` no longer blind-kills whatever holds the port via `fuser -k`.
  `scitex-config` is now a real (non-dev) dependency. (#49)

## [0.3.0] - 2026-07-12

- feat(validator): forbid a hand-written `version` in `manifest.json`;
  require `pip_package` (the dist name) instead. The app version is now
  the SINGLE SOURCE OF TRUTH of the installed pip package, read at
  runtime via `importlib.metadata`. A manifest `version` inevitably
  drifts from the package (2026-07 incident: manifests stuck at
  `0.14.0` while packages shipped `2.25.0` / `0.29.9` / `1.4.2`, so
  every app tile in scitex-hub showed a wrong version). Both validators
  (`scitex_app.validator.AppValidator` and
  `scitex_app.appmaker._validate`) drop `version` from their
  required-field lists, add `pip_package`, and emit an error when a
  `version` key is present. The scaffold now generates `pip_package`
  instead of `version`, and the manifest schema doc documents the rule.
  **Breaking:** existing manifests that declare `version` must remove it
  and add `pip_package`. (#47)

## [0.2.10] - 2026-06-14

(Version 0.2.9 was claimed by an earlier orphan tag on 2026-06-03 that
never published to PyPI; jumping to 0.2.10 to avoid the conflict.)

- fix(appmaker): emit nested-package layout (`<wrapper>/<name>/`) + add
  `[tool.hatch.build.targets.wheel] packages = ["<name>"]` block to
  generated `pyproject.toml`. Pre-fix the scaffold emitted a FLAT layout
  that hatchling refused to package — every `pip install --no-deps
  --target=<dir> <gitea-archive-url>` from the hub then failed with
  "Unable to determine which files to ship inside the wheel". Port of
  scitex-cloud PR #293 M4 done-gate. New test gate
  (`tests/scitex_app/appmaker/test__scaffold.py`, 36 cases, no mocks,
  incl. real `pip install` into a fresh venv) prevents regression. (#35)

## [0.2.8] - 2026-05-26

- test: de-mock + fix test quality; fix fastmcp call-tool API drift
- ci(docs): make _sphinx_html commit-back step non-fatal
- ci: normalize codecov.yml to canonical shape
- ci(quality): replace broken ecosystem-clone template with single-package audit-all
- ci(codecov): disable PR comments to stop email noise
- tests: PA-307 TQ001/TQ002/TQ003/TQ007 mechanical cleanup
- fix: NL001 PEP 515 underscore separators for integer literals
- fix(docs): suppress Sphinx docstring RST issues and duplicate FilesBackend warning

## [0.2.7] - 2026-05-26

- fix(workflows): resync integrated release pipeline from scitex-dev v0.11.20
- fix(workflows): standardize to scitex-dev canonical set
- ci+docs: normalize workflow filenames + README badges (PS-164)
- quality: subprocess coverage + dev extras + audit gate + flat file-ops API
- docs(readme): recommend uv pip install <pkg>[all] (faster resolver)
- ci(release): sync publish-pypi.yml fix from ecosystem
- release(deps): bump 0.2.6 -> 0.2.7; auto-publish on tag push

## [0.2.6]

- Initial CHANGELOG entry — see git log for prior history.
