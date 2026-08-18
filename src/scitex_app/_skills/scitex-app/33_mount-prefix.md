---
description: |
  [TOPIC] Mount Prefix
  [DETAILS] The `stx-mount` contract — how a SciTeX app learns the URL prefix it is mounted under, so one codebase works standalone and embedded at /apps/u/<module>/. Covers why the prefix carries no trailing slash, why relative URLs are prefix-lucky rather than prefix-safe, why the reader throws instead of defaulting, and why the marker is a <meta> and not a <base href>.
tags: [scitex-app-mount-prefix]
---

# Mount prefix — where your app is, and how the browser finds out

**The contract in one line:** the server tells the browser where the app is
mounted, via `<meta name="stx-mount">`. Read it, join relative endpoint names
onto it, never guess.

Available from **scitex-app 0.7.0**. **Semantics changed in 0.8.0** — see the
slash section; 0.7.x's convention is withdrawn.

## The problem this exists to remove

One codebase runs standalone (mounted at `/`) and embedded as a scitex-hub
built-in app (at `/apps/u/<module>/`). `scitex_urlpatterns` was always
prefix-agnostic *server*-side — its patterns are relative, so `include()` works
under any root — but nothing told the *browser*, so every app answered the
question itself. Measured across the three real consumers on 2026-08-18:
writer invented `data-api-base` (correct), figrecipe hardcoded
`/static/figrecipe/…`, scholar hardcoded `/api/graph/…` plus one *accidentally*
relative call.

Three apps, three answers. Not three bugs — one missing declaration.

## Use it

```js
const el = document.querySelector('meta[name="stx-mount"]');
if (!el) throw new Error("stx-mount marker missing — the server did not declare a mount");
const base = el.content;                       // "" at root, "/apps/u/x" embedded

fetch(base + "/api/search?q=" + encodeURIComponent(q));
fetch(base + "/api/graph/health");
```

That is the whole API. **Throw when the marker is absent; never default to root.**
A default is indistinguishable from a correct read, so the one app that
forgot to emit it behaves exactly like the ones that did — until it is
mounted somewhere. scitex-scholar shipped a client-side fix against a page
emitting no marker, and a `?? "/"` fallback made the diff look complete
while changing nothing.

**Read it inline at each call site, or declare it once for the whole page — but
not once per file.** Classic `<script>` tags share one global scope, so the same
`const` in two of them is `SyntaxError: Identifier ... has already been
declared`, which breaks the **entire page**, not just the second file. The
snippet above invites per-file declaration, which is why this is here and not in
a footnote. ES modules have their own scope and are unaffected. *(scitex-scholar
hit this in a first draft, verified both directions, and caught it before
shipping.)*

### Prefix YOUR endpoints. Not the platform's.

The base belongs to routes **your app owns** — the ones under your
`urlpatterns`. Hub's platform endpoints (`/platform/api/context/`,
`/platform/api/data/`, `/apps/store/api/…`) live at the server root and are
*not* under your mount. Prefixing those breaks them, which is this page's
advice over-applied:

```js
fetch(base + "/api/search");        // yours       -> /apps/u/x/api/search
fetch("/platform/api/context/");    // hub's       -> stays at the root
```

### The prefix NEVER ends in `/`. The slash belongs to the endpoint.

Root is `""`; embedded is `"/apps/u/figrecipe"`. So you write
`base + "/api/x"`, and leaf code must not strip or re-add anything.

**This reversed in 0.8.0, and the reason is the only part worth memorising.**
0.7.0–0.7.1 published the opposite (prefix ends in `/`, endpoint does not
start with one). Both conventions produce *identical* correct output, so
testing correct usage cannot tell them apart. They differ only in what the
**likeliest mistake** does — run through a real URL resolver:

| convention | likely mistake | result |
|---|---|---|
| 0.7.x: `"/"` + `"/api/x"` | endpoint written with a leading slash | `//api/x` → **`https://api/x` — a different host** |
| now: `""` + `"api/x"` | endpoint missing its slash | `https://site/api/x` (root, accidentally fine) |
| now: `"/apps/u/f"` + `"api/x"` | same | `/apps/u/fapi/x` — 404, right host |

`//api/x` is protocol-relative: the browser sends the request, and whatever
it carries, **off-origin**. The withdrawn convention's most natural error
leaves the site; this one's 404s. That asymmetry is the whole argument, and
it is invisible unless you deliberately run the wrong usage.

**The general rule, and the most useful thing on this page: when choosing
between two contracts, compare their FAILURE modes, not their happy paths.**
Correct usage looks identical either way, which is exactly why an author picks
up the wrong instinct. It applies twice more below.

### Why not just make the URLs relative?

Same test, different choice. A relative URL **infers** its base from wherever
the document sits; `stx-mount` **declares** it. scitex-scholar measured both,
booting Django mounted at `/scholar/` and issuing the URLs its shipped
JavaScript actually issues:

| URL as shipped | result |
|---|---|
| `/api/graph/health` (root-absolute) | **404** |
| `/scholar/api/graph/health` | 503 — reached the view |
| `api/search?q=x` (relative), mounted at `/scholar/` | **200** |
| `api/search?q=x` (relative), mounted at `/scholar` | **404** |

The 503s are the control — the view answering "no CrossRef DB", so routing under
a prefix already works and only the client URLs are wrong. Without it the 404s
are ambiguous between "wrong URL" and "never mounted".

The last two rows are the point: the *relative* call works at `/scholar/` and
404s at `/scholar`. Converting root-absolute calls to relative trades three
loud deterministic failures for one silent failure contingent on a trailing
slash nobody documents.

> **Relative URLs are not prefix-safe. They are prefix-lucky.** — scitex-scholar

## Credit: this is scitex-writer's pattern

scitex-writer solved this first, in its own templates, before the SDK offered
anything: `data-api-base` on its root element, read back as
`root.dataset.apiBase`, with relative endpoint names joined onto it. **That
pattern *is* the contract** — `stx-mount` is only the SDK's supported way to
obtain the base.

Named deliberately: this problem returns when a future author reinvents a
spelling because nobody told them the question was answered. The current
implementation's properties — throw rather than guess, subtract the view's own
route — came from scitex-ui's `mount.py`, which reasoned them out first.

## Why a `<meta>` and not `<base href>` or a template render

**Not a Django template render.** A built SPA's `index.html` routinely contains
`{{` and `{%` inside inlined JS; the template engine would interpret them and
corrupt the bundle, for reasons having nothing to do with mounting. The
injection is a plain string insertion adding exactly one tag.

**Not `<base href>`.** It would fix relative URLs, but silently changes the
resolution of *every* relative reference in the document — anchors, form
actions, fragment links — a large behavioural change to an app's own markup in
exchange for a value the app can simply read.

## What the SDK does and does not promise

**Does:** if you serve your shell through `scitex_editor_page`, the marker is
present and correct — `request.path` minus the view's own route, which is exact
rather than guessed. `scitex_urlpatterns` registers it at the mount root, so the
default `view_path=""` is right unless you mount it elsewhere.

**Does not (1):** rewrite your assets. Root-absolute URLs in your bundle
(`/static/<pkg>/…`) are still root-absolute and still break under a prefix. That
is a build-tool concern — set your bundler's `base` — and the SDK deliberately
does not paper over it at serve time. A rewriter would work, which is the
problem: apps would go on shipping root-absolute assets while an invisible layer
patched them, and the day it missed a case nobody would know where magic
stopped.

**Does not (2): inject into templates you render yourself.** `scitex_editor_page`
exists for a *built SPA shell* — it reads `index.html` off disk and inserts the
tag. If your view does `render_to_string(...)`, or anything else returning HTML
the SDK never touched, **nothing injects the marker.**

Silent trap: you read "the SDK injects it", ship the client half, and the
page still renders — only the API calls 404, only under a prefix, and the diff
looks correct. This is why the reader now throws instead of defaulting.

A Django-template app emits the marker itself. **Call the SDK rather than
copying a derivation** — 0.7.1 shipped a copyable one-liner here and it was
wrong for any view not at the app root:

```python
from scitex_app.embed import mount_prefix
# in the view:  stx_mount = mount_prefix(request, view_path="editor/")
```
```html
<meta name="stx-mount" content="{{ stx_mount }}">
```

`view_path` is **this view's own route as written in `urls.py`**, required for
anything not at the app root: `request.path` is the whole path — prefix *plus*
the route the view occupies — so only the view can subtract it, because only
the view knows it. Measured against 0.7.1's snippet: correct at the root, wrong
in 3 of 5 cases, every wrong one a non-root view, silently. A mismatch raises.

**This is not an SDK gap.** A template-rendered app is *writer-shaped*, not
*SPA-shaped* — the case `data-api-base` was invented for, where the server
already owns the HTML. `scitex_editor_page` exists only because a built SPA's
`index.html` is opaque bytes the server did not author. Same contract, two
shapes; automatic injection covers one. *(Found by scitex-scholar, who is that
shape and nearly shipped the client half against a marker nothing emitted.)*

## Related

- `15_manifest-schema.md` — `frontend_type` is recorded, never branched on.
- `17_app-develop-frontend.md` — bundler configuration.
