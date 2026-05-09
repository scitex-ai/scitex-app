---
description: |
  [TOPIC] manifest.json — Complete Schema
  [DETAILS] Complete manifest.json schema for SciTeX apps — required fields, all optional metadata, privilege types and valid scopes, dependency layout..
tags: [scitex-app-manifest-schema]
---

# manifest.json — Complete Schema

```json
{
  "$schema": "scitex-app-manifest",
  "$schema_version": "2.0.0",

  "name": "my_awesome_app",
  "slug": "my-awesome-app",
  "label": "My Awesome App",
  "app_name": "my_awesome_app",
  "version": "0.1.0",
  "icon": "fas fa-flask",
  "subtitle": "Short subtitle (80 chars max)",
  "about": "Longer about text (200 chars max)",
  "description": "Full description shown in app catalog.",
  "author": "Your Name",
  "license": "AGPL-3.0",

  "keyboard_shortcut": "",
  "order": 50,
  "accent_color": "",
  "body_class": "my-awesome-app-page",

  "partial_template": "my_awesome_app/index_partial.html",
  "context_builder": "",
  "ai_hint": "Short description injected into LLM context.",

  "capabilities": [],
  "allowed_extensions": [],
  "hidden_patterns": ["__pycache__", "node_modules", ".git", ".venv"],

  "privileges": [
    {"type": "filesystem", "scope": "project"},
    {"type": "network",    "scope": "none"},
    {"type": "api",        "scope": "scitex"}
  ],

  "wip": true,
  "standalone": true,
  "standalone_command": "my-awesome-app gui",
  "standalone_port": 8050,
  "frontend_type": "html",

  "dependencies": {
    "python": [],
    "system": [],
    "node": [],
    "r": [],
    "other": []
  },
  "container": null
}
```

## Required fields

`name`, `slug`, `label`, `version`, `icon` — missing any causes a
validation error.

## Privilege types and valid scopes

| `type`       | Valid `scope` values            |
|--------------|---------------------------------|
| `filesystem` | `project`, `readonly`, `none`   |
| `network`    | `none`, `allowlist`             |
| `api`        | `scitex`, `llm`, `none`         |
