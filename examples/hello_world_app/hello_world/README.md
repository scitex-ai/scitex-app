# hello_world

The smallest SciTeX app that mounts anywhere. Every file here exists to
demonstrate one rule, and the app is deliberately trivial so the rules are the
only thing left to look at.

    apps.py                        subclass ScitexAppConfig, no ImportError fallback
    urls.py                        every route RELATIVE — include() supplies the prefix
    views.py                       derive the prefix from the SDK, never from request.path
    manifest.json                  the app's declaration; NO `version` key
    templates/hello_world/
      page.html                    STANDALONE shape — owns the document
      index_partial.html           WORKSPACE shape — renders into the shell's container

## Run it standalone

    python manage.py runserver

## Why there is no `version` in manifest.json

The version is derived at runtime from the installed `pip_package` via
`importlib.metadata`. A hand-written one drifts from the package it claims to
describe, and it did: every app tile in the hub once displayed a wrong version
from exactly this. Both validators reject the key.

This example declared `version: "0.1.0"` until 2026-09-06 — so the file
developers copy prescribed the defect the validator exists to catch. That is
worse than an ordinary bug, because a reference implementation is believed.

## Why `pip_package` is `scitex-app`

An app's `pip_package` names the distribution it ships inside, because that is
what `importlib.metadata` is asked for. This example ships inside `scitex-app`,
so that is the honest answer — not a placeholder, and it resolves.

## Checking it

    scitex-app app validate examples/hello_world_app/hello_world

This example is covered by a test that runs the SDK's own validator against it
(`tests/test_example_app_validates.py`). The example failed that validator on
eight counts until 2026-09-06 and nothing noticed, because nothing ran it.

One ADVISORY remains and is deliberate: the manifest `name` is `hello_world`,
not `hello_world_app`. The convention exists so app-registry entries do not
collide; here the name must match the Django app module so that
`templates/hello_world/` reads as the ordinary Django convention it is. An
advisory is advice, and this one has a stated reason to decline.
