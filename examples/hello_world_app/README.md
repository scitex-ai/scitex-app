# Hello World — a SciTeX app you can start from

The smallest complete answer to **"how do I start an app?"**. One Django app,
one button, and the mount contract wired correctly.

It deliberately shows almost **no components**. For "what is in scitex-ui and
what does it look like", see scitex-ui's catalogue in that repo's `examples/`.
This is the template; that is the catalogue.

## Run it

Nothing here depends on the SciTeX monorepo. From an empty directory:

```bash
python -m venv .venv
.venv/bin/pip install --no-cache-dir 'scitex-app>=0.8.0' 'scitex-ui>=0.16.0' django
.venv/bin/python manage.py runserver
```

Then open **both**:

| URL | mode |
|---|---|
| `http://127.0.0.1:8000/` | standalone |
| `http://127.0.0.1:8000/apps/u/hello_world/` | embedded, as scitex-hub mounts a published app |

Same code, same build, both work. Press the button in each — the API call
resolves under whichever prefix you are on.

> `--no-cache-dir` is not superstition: PyPI's JSON API can report a version as
> `latest` for several minutes before pip's index can resolve it, and a stale
> cache produces a confusing "no matching distribution" for a version you can
> see on the website.

## What to copy, and why

**`urls.py` — every route relative.** No leading slashes. `include()` supplies
the prefix, so the same file serves both mounts unchanged. This is the half
that has always worked.

**`views.py` — derive the prefix with the SDK, not by hand.**

```python
prefix = mount_prefix(request, view_path="")
```

`view_path` is *this view's own route as written in urls.py*. `request.path` is
the mount prefix **plus** that route, so only the view can subtract it — only
the view knows it. Move this view to `path("editor/", ...)` and you must pass
`view_path="editor/"`, or the SDK raises rather than handing back a
plausible-looking prefix. A hand-rolled derivation is silently correct at the
app root and silently wrong everywhere else.

**`page.html` — read the marker, and throw if it is absent.**

```js
const el = document.querySelector('meta[name="stx-mount"]');
if (!el) throw new Error("stx-mount marker missing");
const base = el.content;              // "" standalone, "/apps/u/hello_world" embedded
fetch(base + "/api/greet");           // the slash belongs to the ENDPOINT
```

Never `?? "/"`. A default is indistinguishable from a correct read, so an app
that forgot to emit the marker behaves exactly like one that did — until it is
mounted under a prefix, at which point every call 404s and the code still looks
right.

**Do not prefix hub's platform routes.** `/platform/api/context/`,
`/platform/api/data/` and friends live at the server root and are not under
your mount. Joining the base onto those breaks them — this page's advice
over-applied.

**`apps.py` — no `ImportError` fallback.** Subclassing `ScitexAppConfig` is
what makes this a SciTeX app. A `try/except` falling back to plain
`AppConfig` would let the app keep running while silently ceasing to be one,
so the contract evaporates exactly when it goes missing.

## The claim is tested, not asserted

`project/urls.py` mounts the same app twice on purpose, so one process can
exercise both. `tests/` then checks what the browser would actually receive:

```bash
.venv/bin/pip install --no-cache-dir pytest
.venv/bin/python -m pytest tests -q      # 6 passed
```

The suite includes a **control** — a route that must 404 — because without one
a server returning 200 for everything would satisfy every other assertion.

It was also verified by regression: forcing the prefix back to the withdrawn
trailing-slash convention turns two tests red. Worth noting that **four stayed
green**, because that mistake breaks the client-side join, not Django's
routing. If this example only tested "does it respond", it would have shipped
broken with a green suite.
