---
description: |
  [TOPIC] App — Test, Troubleshoot, Env Vars
  [DETAILS] App testing in browser, standalone mode, troubleshooting, and environment variables reference. Companion to 13_app-validate-install.md..
tags: [scitex-app-app-test-troubleshoot]
version: 0.2.6
exported_via: installed
---

# App — Test, Troubleshoot, Env Vars

Companion to [13_app-validate-install.md](13_app-validate-install.md)
(which covers Steps 3-4: validate + dev-install). Split out for SK401
budget.

## Step 5: Test in Browser

Navigate to `http://127.0.0.1:8000/` and verify your app works.

**Testing checklist:**
- [ ] Tab appears in sidebar with correct icon and label
- [ ] Clicking the tab loads the partial template without HTTP errors
- [ ] Browser DevTools console shows no JS errors
- [ ] API endpoints respond correctly (test with browser DevTools Network tab)
- [ ] CSS is scoped — no style leakage into workspace shell
- [ ] App works with and without an active project

### Standalone mode (no SciTeX Cloud required)

```bash
# Runs a minimal Django workspace shell at localhost:8050
my-awesome-app gui

# With options
my-awesome-app gui --port 9000 --no-browser

# Or via scitex-app CLI
scitex-app standalone --app my_awesome_app --port 8050
```

Standalone mode is useful for:
- Testing without a full SciTeX Cloud instance running
- Distributing the app as a standalone tool
- CI testing

## Troubleshooting

### Tab does not appear after dev-install

- Confirm the API call returned "Dev install successful!" — if it failed silently, check your token
- Verify `SCITEX_API_TOKEN` belongs to the same user you're logged in as on the server
- Hard-refresh the browser (Ctrl+Shift+R) — sidebar is cached
- Check server logs: `tail -f /path/to/scitex.log` — look for import errors in `views.py`

### Validation fails: CSS targets shell selector

```
✗ static/my_awesome_app/css/my_awesome_app.css: targets shell selector '.workspace-sidebar'
```

Rename to use your app's own prefix: `.my-awesome-app-sidebar`.

### Validation fails: views.py not found

```
✗ Missing required file: views.py (checked at root and _django/ subdir)
```

The validator looks at `views.py` at the app root or under `_django/`.
Ensure the file exists at one of those locations.

### Template not rendering in workspace

- Check `"partial_template"` in `manifest.json` matches the actual template path
- Path is relative to Django `TEMPLATES` dirs: typically `my_awesome_app/index_partial.html`
- Run `python manage.py check` to surface template syntax errors
- Confirm the template has no `<html>`, `<head>`, or `<body>` tags — partials must be fragments

### React bundle not loading

- Run `npm run build` before `dev-install`
- Check `vite.config.js` outputs to `static/my_awesome_app/dist/`
- Confirm the `<script>` tag in the partial uses `{% load static %}` and `{% static '...' %}`
- Check browser DevTools Network tab for 404 on the JS bundle path

### CSRF error on API POST

Add CSRF token to `fetch` headers:

```javascript
'X-CSRFToken': document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '',
```

Or use the Django `{% csrf_token %}` input and read its value:

```javascript
'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || '',
```

### Dev-install: "Authentication failed"

```
Error: Authentication failed (401)
```

Token is invalid or expired. Generate a fresh token from
Profile → Settings → API Tokens.

### Dev-install: "Validation failed before install"

```
Error: Validation failed — fix errors before installing
  ✗ manifest.json missing required field: slug
```

Fix the reported validation error first, then re-run `dev-install`.

## Environment Variables Reference

| Variable             | Purpose                                  | Default                          |
|----------------------|------------------------------------------|----------------------------------|
| `SCITEX_API_TOKEN`   | JWT token for `dev-install` / `submit`   | — (required)                     |
| `SCITEX_SERVER_URL`  | Server URL for `dev-install` / `submit`  | `http://127.0.0.1:8000`          |
| `SCITEX_API_URL`     | Cloud API URL for `get_files()` backend  | `http://127.0.0.1:8000`          |
| `SCITEX_BASE_DIR`    | Base dir for path resolution             | — (raises if missing)            |
| `SCITEX_WORKING_DIR` | Working dir for standalone file tree     | —                                |
| `DJANGO_SECRET_KEY`  | Django secret key (standalone mode)      | `"scitex-standalone-dev-key"`    |
| `DJANGO_DEBUG`       | Django debug mode                        | `"true"`                         |
