---
description: |
  [TOPIC] App Lifecycle — Validate, Install, Test, Submit
  [DETAILS] App lifecycle — Steps 3–6 (validate, dev-install, test, submit) plus the canonical reference implementation (figrecipe). Companion to 10_app-lifecycle.md..
tags: [scitex-app-app-lifecycle-deploy]
version: 0.2.6
exported_via: installed
---

# App Lifecycle — Validate, Install, Test, Submit

Companion to [10_app-lifecycle.md](10_app-lifecycle.md) (Steps 1-2:
Scaffold + Develop). Split out for SK401 budget.

## Steps 3–5: Validate, Dev-Install, Test

See [13_app-validate-install.md](13_app-validate-install.md) for full
detail. Quick path:

```bash
# 3. Validate
scitex-app app validate .

# 4. Dev-install
export SCITEX_API_TOKEN="your-jwt-token"
scitex-app app dev-install . --server http://127.0.0.1:8000

# 5. Open http://127.0.0.1:8000/ and check your tab appears
```

## Step 6: Submit

```bash
export SCITEX_API_TOKEN="your-jwt-token"
scitex-app app submit .
```

**Expected output:**
```
Submitting app from: /path/to/my_awesome_app
Submission successful!
  PR: https://gitea.scitex.ai/scitex-apps/registry/pulls/42
```

Submission opens a PR to the scitex-apps registry. After approval, the
app becomes visible in the public catalog and `load_approved_apps()`
registers it globally on server startup.

**Before submitting:**
- Set `"wip": false` in `manifest.json`
- Ensure all validation checks pass (`scitex-app app validate .`)
- Write a clear `README.md` and `description` in `manifest.json`
- Confirm `version` is a proper release version (e.g. `"1.0.0"`)

## Reference Implementation

The `figrecipe` app is the canonical working example:

```
~/proj/figrecipe/src/figrecipe/
    manifest.json
    views.py
    urls.py
    templates/figrecipe/index_partial.html
    static/figrecipe/css/figrecipe.css
    _django/frontend/          # React frontend (bridge + Zustand store)
```
