---
description: |
  [TOPIC] Mount Prefix
  [DETAILS] The `stx-mount` contract — how a SciTeX app learns the URL prefix it is mounted under, so one codebase works standalone at / and embedded at /apps/u/<module>/. Covers the guaranteed trailing slash, why relative URLs are prefix-lucky rather than prefix-safe, and why the marker is a <meta> and not a <base href>..
tags: [scitex-app-mount-prefix]
---

# Mount prefix — where your app is, and how the browser finds out

**The contract in one line:** the server tells the browser where the app is
mounted, via `<meta name="stx-mount">`. Read it, join relative endpoint names
onto it, never guess.

Available from **scitex-app 0.7.0**.

---

## The problem this exists to remove

A SciTeX app runs in two places from one codebase:

| mode | mounted at |
|---|---|
| standalone (`run_standalone`) | `/` |
| embedded as a scitex-hub built-in app | `/apps/u/<module>/` |

`scitex_urlpatterns` has always been prefix-agnostic on the *server* side — its
patterns are relative, so `include()` works under any root. Nothing told the
*browser*. Client code therefore had no supported way to learn its mount point,
and every app answered the question for itself.

Measured across the three real consumers on 2026-08-18, before this shipped:

| app | what it did |
|---|---|
| scitex-writer | invented `data-api-base` in its own templates — correct |
| figrecipe | hardcoded `/static/figrecipe/assets/…` — breaks under a prefix |
| scitex-scholar | hardcoded `/api/graph/…`, plus one *accidentally* relative call |

Three apps, three answers. Not three bugs — one missing declaration.

---

## Use it

```js
const base = document.querySelector('meta[name="stx-mount"]')?.content ?? "/";

fetch(base + "api/search?q=" + encodeURIComponent(q));
fetch(base + "api/graph/health");
```

That is the whole API.

### The trailing slash is guaranteed. Do not normalise.

`stx-mount` **always** ends in `/`. Standalone it is `"/"`; embedded it is
`"/apps/u/figrecipe/"`. From `scitex_app/_django.py`:

```python
mount_prefix = request.path if request.path.endswith("/") else request.path + "/"
```

So endpoint names must **not** start with a slash, and leaf code must **not**
strip or re-add one. A `base.replace(/\/$/, '')` in every leaf is the same
nine-implementations problem one level down, and it is worse than redundant: it
re-derives a value the server already computed correctly.

If you ever observe a `stx-mount` without a trailing slash, that is an SDK bug.
File it; do not work around it.

---

## Why not just make the URLs relative?

Because that is not a fix — it is a quieter bug. This is the single most
important paragraph on this page.

A relative URL **infers** the base from wherever the document happens to sit.
`stx-mount` **declares** it.

scitex-scholar measured both, by booting Django with the app mounted at
`/scholar/` and issuing the exact URLs its shipped JavaScript issues:

| URL as shipped | result |
|---|---|
| `/api/graph/health` (root-absolute) | **404** |
| `/scholar/api/graph/health` | 503 — reached the view |
| `api/search?q=x` (relative), mounted at `/scholar/` | **200** |
| `api/search?q=x` (relative), mounted at `/scholar` | **404** |

The 503s are the control: they are the view answering "no CrossRef DB", i.e.
routing under a prefix already works and only the client URLs are wrong. Without
that control the 404s would be ambiguous between "wrong URL" and "never
mounted".

Read the last two rows together. The *relative* call works at `/scholar/` and
404s at `/scholar`. Converting the root-absolute calls to relative would trade
three loud, deterministic, reproducible failures for one silent failure
contingent on whether a deployer typed a trailing slash — which nobody documents
and nobody checks.

scitex-scholar's phrasing, which says it better than a paragraph:

> **Relative URLs are not prefix-safe. They are prefix-lucky.**

Inference is correct exactly when the deployment happens to be shaped the way
the inference assumes, and fails silently otherwise — the worst available
failure mode for something a leaf author cannot test without a real mount.

---

## Credit: this is scitex-writer's pattern

scitex-writer hit this first and solved it in its own templates, before the SDK
offered anything:

```html
<div class="writer-app" data-api-base="{{ api_base|default:'/' }}">
```

```js
const v = (root?.dataset.apiBase) || "/";
fetch(v + "api/file?path=" + …)
```

A server-supplied base with relative endpoint names joined onto it. **That
pattern *is* the contract.** `stx-mount` is only the SDK's supported way to
obtain the base, so that every app gets it without inventing a third mechanism.

Named here deliberately: the way this problem comes back is a future author
reinventing a fourth spelling because they did not know the question had been
answered.

---

## Why a `<meta>` and not `<base href>` or a template render

Decided for reasons that are not obvious, and recorded so they are not undone by
someone who does not know them.

**Not a Django template render.** A built SPA's `index.html` routinely contains
`{{` and `{%` inside inlined JS. The template engine would try to interpret
them and corrupt the bundle, for reasons having nothing to do with mounting. The
injection is a plain string insertion that adds exactly one tag and touches
nothing else.

**Not `<base href>`.** It would fix relative URLs, but it silently changes the
resolution of *every* relative reference in the document — anchors, form
actions, fragment links — which is a large behavioural change to an app's own
markup in exchange for a value the app can simply read.

**Matched as `<head>` / `<head ...>` specifically.** A substring search for
`<head` also matches `<header`, which put the marker inside a `<header>` element
on documents that had one and no real head. The tag stayed findable, so the
contract held, but the placement contradicted its own reasoning. Where there is
no head at all the tag is prepended — still correct, since the parser hoists a
leading `<meta>` — so the prefix is never silently dropped.

---

## What the SDK does and does not promise

**Does:** if you serve your shell through `scitex_editor_page`, the marker is
present and its value is correct. It is derived from `request.path`, which is
exact rather than a guess — the view is registered at `path("", …)`, so its
request path *is* the mount prefix.

**Does not:** rewrite your assets. Root-absolute URLs in your bundle
(`/static/<pkg>/…`) are still root-absolute and still break under a prefix. That
is a build-tool concern — set your bundler's `base` — and the SDK deliberately
does not paper over it at serve time. A rewriter would work, which is the
problem: every app would go on shipping root-absolute assets while an invisible
layer patched them, and the day it missed a case nobody would know where the
magic stopped.

---

## Related

- `15_manifest-schema.md` — `frontend_type` is recorded, never branched on; the
  SDK has no opinion about your framework.
- `17_app-develop-frontend.md` — bundler configuration.
- `05_standalone.md` — `run_standalone`, the `/` case.
