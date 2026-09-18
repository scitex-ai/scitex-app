"""The mount-side app-shell contract (``scitex_app.shell_contract``).

Title / version / project provider / actions / named commands: the GENERIC
declaration a leaf hands to the shell chrome, and the ONE emitted route
(``<meta name="stx-app-shell" content="{...json...}">``) the presentation
layer reads.

The pure arms take pure inputs (a declaration in, a payload or a raise out) —
no Django, no repo, no fixture. The ``AppConfig`` arms follow the in-repo
carve-out used by ``test__version_display_contract.py``: guard
``settings.configure(...)`` + ``django.setup()`` once per process, then build a
REAL ``ScitexAppConfig`` against a temp ``manifest.json`` (no mocks, PA-306).

One assertion per test (STX-TQ007); AAA markers on their own lines (STX-TQ002).
"""

from __future__ import annotations

import json
import types
from pathlib import Path

import django
import pytest
from django.conf import settings

if not settings.configured:
    # One real app so "is a ScitexAppConfig mounted" can be asked in both
    # directions. Identical in every scitex-app django test module: Django
    # configures settings once per process and the module order is not ours to
    # choose, so the blocks must agree or the fixture depends on luck.
    settings.configure(
        DEFAULT_CHARSET="utf-8",
        ALLOWED_HOSTS=["*"],
        DATABASES={},
        INSTALLED_APPS=["django.contrib.contenttypes"],
    )
    django.setup()

from scitex_app._django import ScitexAppConfig
from scitex_app.shell_contract import (
    DEFAULT_COMMAND_GROUP,
    SHELL_PROPS_CONTEXT_KEY,
    SHELL_PROPS_META_NAME,
    ProjectProvider,
    ShellAction,
    ShellCommand,
    ShellContractError,
    ShellProps,
    inject_shell_props,
    shell_props_context,
    shell_props_from_app_config,
    shell_props_json,
    shell_props_meta_tag,
)

# The dist name scitex-app ships under (its own pyproject [project] name).
_SCITEX_APP_DIST = "scitex-app"


def _props(**overrides) -> ShellProps:
    """A minimal VALID declaration, with per-test overrides applied."""
    base = {
        "app": "figrecipe",
        "title": "FigRecipe",
        "version": "1.2.3",
        "scope": "user",
    }
    base.update(overrides)
    return ShellProps(**base)


def _provider() -> ProjectProvider:
    """A minimal valid project provider."""
    return ProjectProvider(url="/api/projects", current="proj-1")


def _action(**overrides) -> ShellAction:
    """A minimal valid action (a named command, no href)."""
    base = {"id": "save", "label": "Save", "command": "figrecipe:save"}
    base.update(overrides)
    return ShellAction(**base)


def _command(**overrides) -> ShellCommand:
    """A minimal valid named command."""
    base = {"id": "figrecipe:save", "label": "Save recipe", "sequence": "Ctrl+S"}
    base.update(overrides)
    return ShellCommand(**base)


def _make_app_config(
    tmp_path: Path, pip_package: str, manifest_extra: dict
) -> ScitexAppConfig:
    """Build a real ScitexAppConfig backed by a temp app module + manifest."""
    mod = types.ModuleType("myapp._django")
    mod.__file__ = str(tmp_path / "__init__.py")
    cfg = ScitexAppConfig("myapp._django", mod)
    manifest = {
        "name": "myapp",
        "slug": "myapp",
        "label": "My App",
        "pip_package": pip_package,
        "icon": "fas fa-puzzle-piece",
        "license": "MIT",
    }
    manifest.update(manifest_extra)
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return cfg


# ─── the emitted name is the contract value ────────────────────────────────
# The presentation layer reads this name; the literal is asserted rather than
# compared to a variable so a rename that changed BOTH sides still fails here
# and forces a deliberate decision (the tag is consumed by code we do not own).


def test_the_meta_name_is_the_contract_value():
    # Arrange
    # Act
    name = SHELL_PROPS_META_NAME
    # Assert
    assert name == "stx-app-shell"


def test_the_context_key_is_named_for_the_contract():
    # Arrange
    # Act
    key = SHELL_PROPS_CONTEXT_KEY
    # Assert
    assert key == "stx_shell_props"


# ─── ShellAction: an action must have somewhere to go ──────────────────────


def test_an_action_with_a_named_command_is_valid():
    # Arrange
    action = _action()
    # Act
    action_id = action.as_payload()["id"]
    # Assert
    assert action_id == "save"


def test_an_action_with_an_href_is_valid():
    # Arrange
    action = _action(command=None, href="/docs/")
    # Act
    payload = action.as_payload()
    # Assert — the href is carried through.
    assert payload["href"] == "/docs/"


def test_an_action_with_neither_command_nor_href_is_refused():
    # Arrange — a control with no affordance renders as a working one.
    # Act
    # Assert
    with pytest.raises(ShellContractError):
        _action(command=None, href=None)


def test_an_action_id_that_is_blank_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ShellContractError):
        _action(id="   ")


def test_an_action_label_that_is_blank_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ShellContractError):
        _action(label="")


def test_a_non_integer_action_order_is_refused():
    # Arrange — ordering must not silently fall back to string comparison.
    # Act
    # Assert
    with pytest.raises(ShellContractError):
        _action(order="first")


def test_an_action_payload_omits_an_unset_command():
    # Arrange
    action = _action(command=None, href="/docs/")
    # Act
    payload = action.as_payload()
    # Assert — an absent affordance is absent, not an empty string.
    assert "command" not in payload


# ─── ShellCommand: the id is the name every input device resolves ──────────


def test_a_command_payload_mirrors_the_keymap_registry_shape():
    # Arrange
    command = _command()
    # Act
    payload = command.as_payload()
    # Assert — label/group/sequence are the registry's keys.
    assert sorted(payload) == ["group", "label", "sequence"]


def test_a_command_defaults_to_the_app_group():
    # Arrange
    command = _command()
    # Act
    group = command.as_payload()["group"]
    # Assert
    assert group == DEFAULT_COMMAND_GROUP


def test_a_command_id_that_is_blank_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ShellContractError):
        _command(id="")


def test_a_command_label_that_is_blank_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ShellContractError):
        _command(label="  ")


def test_a_command_sequence_that_is_blank_is_refused():
    # Arrange — an empty chord renders as a shortcut hint with no chord.
    # Act
    # Assert
    with pytest.raises(ShellContractError):
        _command(sequence="")


def test_a_command_payload_omits_an_undeclared_sequence():
    # Arrange
    command = _command(sequence=None)
    # Act
    payload = command.as_payload()
    # Assert
    assert "sequence" not in payload


# ─── ProjectProvider: a declaration, not a fetch ───────────────────────────


def test_a_provider_url_that_is_blank_is_refused():
    # Arrange — a blank provider url is a picker nobody can populate.
    # Act
    # Assert
    with pytest.raises(ShellContractError):
        ProjectProvider(url="")


def test_a_provider_payload_omits_empty_optional_fields():
    # Arrange
    provider = ProjectProvider(url="/api/projects")
    # Act
    payload = provider.as_payload()
    # Assert
    assert sorted(payload) == ["url"]


def test_a_provider_payload_carries_the_optional_fields_it_is_given():
    # Arrange
    provider = ProjectProvider(
        url="/api/projects",
        current="proj-1",
        navigate="/editor/",
        placeholder="Choose a project",
    )
    # Act
    payload = provider.as_payload()
    # Assert
    assert payload["placeholder"] == "Choose a project"


# ─── ShellProps: scope decides whether a picker may exist ──────────────────


def test_a_blank_title_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ShellContractError):
        _props(title="")


def test_a_blank_version_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ShellContractError):
        _props(version="")


def test_a_blank_app_slug_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ShellContractError):
        _props(app="")


def test_a_scope_typo_is_refused():
    # Arrange — normalize_scope fails loud rather than guessing a scope.
    # Act
    # Assert
    with pytest.raises(ValueError):
        _props(scope="projects")


def test_a_user_scoped_app_is_canonicalised_to_user():
    # Arrange — the safe default is the one that renders no picker.
    # Act
    scope = _props().scope
    # Assert
    assert scope == "user"


def test_a_user_scoped_app_may_not_declare_a_project_provider():
    # Arrange — a user-scoped app renders with NO project selector, so a
    # provider here would be an affordance that must not exist.
    # Act
    # Assert
    with pytest.raises(ShellContractError):
        _props(scope="user", project=_provider())


def test_a_project_scoped_app_carries_the_provider_in_its_payload():
    # Arrange
    props = _props(scope="project", project=_provider())
    # Act
    payload = props.as_payload()
    # Assert
    assert payload["project"]["current"] == "proj-1"


def test_a_user_scoped_payload_has_no_project_key():
    # Arrange
    # Act
    payload = _props().as_payload()
    # Assert — absence is the declaration, not an empty object.
    assert "project" not in payload


def test_duplicate_action_ids_are_refused():
    # Arrange — two entries sharing an id make the outcome iteration-order.
    # Act
    # Assert
    with pytest.raises(ShellContractError):
        _props(actions=[_action(), _action(label="Save again")])


def test_duplicate_command_ids_are_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ShellContractError):
        _props(commands=[_command(), _command(label="Save again")])


def test_actions_are_emitted_in_declared_order():
    # Arrange — order is the declaration's, applied deterministically.
    later = _action(id="export", label="Export", command="figrecipe:export", order=9)
    sooner = _action(id="save", label="Save", command="figrecipe:save", order=1)
    props = _props(actions=[later, sooner])
    # Act
    ids = [a["id"] for a in props.as_payload()["actions"]]
    # Assert
    assert ids == ["save", "export"]


def test_commands_are_keyed_by_their_id():
    # Arrange
    props = _props(commands=[_command()])
    # Act
    commands = props.as_payload()["commands"]
    # Assert — one key per command id, the registry's shape.
    assert list(commands) == ["figrecipe:save"]


# ─── the emitted route: one tag, byte-stable ───────────────────────────────


def test_the_json_has_no_padding_after_commas():
    # Arrange
    # Act
    rendered = shell_props_json(_props(actions=[_action(), _action(id="x", label="X")]))
    # Assert — no padding, so two renders are comparable byte for byte.
    assert ", " not in rendered


def test_the_json_has_no_padding_after_colons():
    # Arrange
    # Act
    rendered = shell_props_json(_props())
    # Assert
    assert '": ' not in rendered


def test_the_json_is_stable_across_two_renders():
    # Arrange
    props = _props(
        actions=[_action(id="b", label="B"), _action(id="a", label="A")],
        commands=[_command(id="z:one", label="One"), _command(id="a:two", label="Two")],
    )
    # Act
    first, second = shell_props_json(props), shell_props_json(props)
    # Assert
    assert first == second


def test_the_json_sorts_command_keys():
    # Arrange
    props = _props(commands=[_command(id="z:one", label="One"), _command(id="a:two", label="Two")])
    # Act
    rendered = shell_props_json(props)
    # Assert — key order is canonical, not insertion order.
    assert rendered.index("a:two") < rendered.index("z:one")


def test_the_meta_tag_names_the_contract():
    # Arrange
    # Act
    tag = shell_props_meta_tag(_props())
    # Assert
    assert tag.startswith(f'<meta name="{SHELL_PROPS_META_NAME}" content="')


def test_the_meta_tag_escapes_a_quote_in_a_label():
    # Arrange — an unescaped quote terminates the attribute early, and the
    # reader then cannot parse the tag at all.
    props = _props(title='My "Quoted" App')
    # Act
    tag = shell_props_meta_tag(props)
    # Assert — the escape entity is what carries the quote.
    assert "&quot;" in tag


def test_the_meta_tag_does_not_leave_a_raw_quote_inside_the_payload():
    # Arrange
    props = _props(title='My "Quoted" App')
    # Act
    tag = shell_props_meta_tag(props)
    # Assert — the raw quote is gone, so the attribute cannot end early.
    assert '"Quoted"' not in tag


def test_the_meta_tag_payload_round_trips_through_json():
    # Arrange
    props = _props(actions=[_action()], commands=[_command()])
    # Act
    payload = json.loads(shell_props_json(props))
    # Assert
    assert payload["actions"][0]["command"] == "figrecipe:save"


def test_injection_places_the_tag_immediately_after_the_head_open():
    # Arrange
    document = "<!doctype html><html><head><title>t</title></head><body></body></html>"
    props = _props()
    # Act
    rendered = inject_shell_props(document, props)
    # Assert
    assert rendered.index("<head>") < rendered.index(SHELL_PROPS_META_NAME) < rendered.index("<title>")


def test_injection_prepends_the_tag_when_there_is_no_head():
    # Arrange — a fragment render is not an excuse to drop the declaration.
    props = _props()
    # Act
    rendered = inject_shell_props("<div>x</div>", props)
    # Assert
    assert rendered.startswith(f'<meta name="{SHELL_PROPS_META_NAME}"')


def test_the_head_matcher_does_not_match_a_header_element():
    # Arrange — `<header>` must not be mistaken for `<head>` (positive
    # control: the injected tag must land before the header element).
    document = "<article><header>h</header></article>"
    props = _props()
    # Act
    rendered = inject_shell_props(document, props)
    # Assert — no <head> in the document, so the tag is prepended.
    assert rendered.startswith(f'<meta name="{SHELL_PROPS_META_NAME}"')


def test_the_context_keys_the_payload():
    # Arrange
    # Act
    context = shell_props_context(_props())
    # Assert
    assert list(context) == [SHELL_PROPS_CONTEXT_KEY]


def test_the_context_payload_is_the_declaration():
    # Arrange
    # Act
    context = shell_props_context(_props(title="Writer"))
    # Assert
    assert context[SHELL_PROPS_CONTEXT_KEY]["title"] == "Writer"


# ─── from a real ScitexAppConfig (the in-repo Django carve-out) ────────────


def test_app_config_title_comes_from_the_manifest_label(tmp_path):
    # Arrange
    cfg = _make_app_config(tmp_path, _SCITEX_APP_DIST, {})
    # Act
    props = shell_props_from_app_config(cfg)
    # Assert — the human name, declared once, in the manifest.
    assert props.title == "My App"


def test_app_config_version_is_the_installed_dist(tmp_path):
    # Arrange — a manifest that (illegally) declares a stale version. If the
    # chrome read it, the header would show that number.
    stale = "0.14.0"
    cfg = _make_app_config(tmp_path, _SCITEX_APP_DIST, {"version": stale})
    # Act
    props = shell_props_from_app_config(cfg)
    # Assert
    assert props.version != stale


def test_app_config_version_matches_the_shared_accessor(tmp_path):
    # Arrange
    from scitex_app._version_display_contract import package_version

    cfg = _make_app_config(tmp_path, _SCITEX_APP_DIST, {})
    # Act
    props = shell_props_from_app_config(cfg)
    # Assert — one source of truth for the version across SDK surfaces.
    assert props.version == package_version(_SCITEX_APP_DIST)


def test_app_config_slug_is_the_app_identity(tmp_path):
    # Arrange
    cfg = _make_app_config(tmp_path, _SCITEX_APP_DIST, {})
    # Act
    props = shell_props_from_app_config(cfg)
    # Assert — the renderer's namespace key.
    assert props.app == "myapp"


def test_app_config_without_a_scope_declaration_is_user_scoped(tmp_path):
    # Arrange
    cfg = _make_app_config(tmp_path, _SCITEX_APP_DIST, {})
    # Act
    props = shell_props_from_app_config(cfg)
    # Assert — the safe default: no picker is rendered.
    assert props.scope == "user"


def test_app_config_project_scope_carries_the_declared_provider(tmp_path):
    # Arrange
    cfg = _make_app_config(tmp_path, _SCITEX_APP_DIST, {"scope": "project"})
    # Act
    props = shell_props_from_app_config(cfg, project=_provider())
    # Assert
    assert props.as_payload()["project"]["url"] == "/api/projects"


def test_app_config_carries_the_declared_actions(tmp_path):
    # Arrange
    cfg = _make_app_config(tmp_path, _SCITEX_APP_DIST, {})
    # Act
    props = shell_props_from_app_config(cfg, actions=[_action()])
    # Assert
    assert props.as_payload()["actions"][0]["id"] == "save"


def test_app_config_carries_the_declared_named_commands(tmp_path):
    # Arrange
    cfg = _make_app_config(tmp_path, _SCITEX_APP_DIST, {})
    # Act
    props = shell_props_from_app_config(cfg, commands=[_command()])
    # Assert
    assert props.as_payload()["commands"]["figrecipe:save"]["label"] == "Save recipe"


def test_app_config_project_scope_on_a_user_scoped_default_is_refused(tmp_path):
    # Arrange — a provider handed to a user-scoped app is refused, so the
    # no-picker rule cannot be bypassed through the AppConfig door either.
    cfg = _make_app_config(tmp_path, _SCITEX_APP_DIST, {})
    # Act
    # Assert
    with pytest.raises(ShellContractError):
        shell_props_from_app_config(cfg, project=_provider())


# EOF
