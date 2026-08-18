---
description: |
  [TOPIC] Mount Prefix — Rationale
  [DETAILS] Why the stx-mount contract is shaped the way it is: why relative URLs are prefix-lucky rather than prefix-safe, why the marker is a <meta> and not a <base href> or a template render, and whose pattern it originally was. Read this before changing the contract in 33_mount-prefix.md.
tags: [scitex-app-mount-prefix-rationale]
---

# Mount prefix — why it is shaped this way

The contract itself is `33_mount-prefix.md`. This page holds the reasoning, so
that changing the contract means first meeting the argument for it.

Each section below is the same test the contract's slash rule uses: **compare
the FAILURE modes, not the happy paths.**

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
