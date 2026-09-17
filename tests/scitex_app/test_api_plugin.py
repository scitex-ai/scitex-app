#!/usr/bin/env python3
"""The leaf API-plugin contract (``scitex_app.api_plugin``).

Mirrors src/scitex_app/api_plugin.py (PS-204). Pure inputs, real objects, no
mocks (PA-306): every arm feeds a declaration in and reads either a raise or a
payload out. One assertion per test (STX-TQ007); AAA markers on their own lines
(STX-TQ002).
"""

from __future__ import annotations

from importlib.metadata import EntryPoint

import pytest

from scitex_app.api_plugin import (
    API_ENTRY_POINT_GROUP,
    DESCRIPTOR_IMPLEMENTATION,
    OAUTH2_FLOW,
    OAUTH_SECURITY_SCHEME,
    RECOMMENDED_COMPUTE_COSTS,
    RECOMMENDED_RATE_CLASSES,
    RESERVED_IDEMPOTENCY_HEADERS,
    ApiError,
    ApiField,
    ApiPlugin,
    ApiPluginContractError,
    ApiRoute,
    ApiSchema,
    Audit,
    AuthScope,
    Deprecation,
    Idempotency,
    OAuthProvider,
    Pagination,
    RateLimit,
    discover_api_plugins,
)

#: The declared-sequence carriers on each descriptor, paired with a value that
#: is the WRONG type for that sequence — the shapes a duck-typed stand-in
#: arrives in. Each is fed to its descriptor below and must be refused by name.
_BAD_ROUTES: list = ["x"]
_BAD_FIELDS: list = ["recipe_path"]
_BAD_METHODS: list = [1]
_BAD_SCOPES: list = [1]
_BAD_ERRORS: list = [1]
_BAD_ENUM: list = [1]


def _field(**overrides) -> ApiField:
    base = {"name": "recipe_path", "type": "string"}
    base.update(overrides)
    return ApiField(**base)


def _schema(**overrides) -> ApiSchema:
    base = {"name": "SaveRequest", "fields": [_field()]}
    base.update(overrides)
    return ApiSchema(**base)


def _auth(**overrides) -> AuthScope:
    base = {"project_scope": "project", "scopes": ["recipes:write"]}
    base.update(overrides)
    return AuthScope(**base)


def _rate(**overrides) -> RateLimit:
    base = {"rate_class": "standard", "compute_cost": "standard"}
    base.update(overrides)
    return RateLimit(**base)


def _oauth(**overrides) -> OAuthProvider:
    """The authorization server a scoped plugin has to declare (blocker 5)."""
    base = {
        "authorization_url": "https://auth.scitex.example/oauth2/authorize",
        "token_url": "https://auth.scitex.example/oauth2/token",
        "scopes": {
            "recipes:write": "Create and modify recipes",
            "recipes:read": "Read recipes",
        },
    }
    base.update(overrides)
    return OAuthProvider(**base)


def _route(**overrides) -> ApiRoute:
    base = {
        "path": "recipes/save",
        "methods": ["GET"],
        "handler": "figrecipe.api:save_recipe",
        "auth": _auth(),
        "rate": _rate(),
    }
    base.update(overrides)
    return ApiRoute(**base)


def _plugin(**overrides) -> ApiPlugin:
    base = {
        "id": "figrecipe",
        "title": "FigRecipe",
        "api_version": "1",
        "routes": [_route()],
        "oauth": _oauth(),
    }
    base.update(overrides)
    return ApiPlugin(**base)


# ─── calibration: the published names are the contract ─────────────────────


def test_the_entry_point_group_is_the_declared_name():
    # Arrange
    # Act
    group = API_ENTRY_POINT_GROUP
    # Assert
    assert group == "scitex.apis"


def test_the_descriptor_implementation_is_declared():
    # Arrange — pydantic would change the published install surface of a
    # stdlib-only base, so the choice is stated where a reader will find it.
    # Act
    implementation = DESCRIPTOR_IMPLEMENTATION
    # Assert
    assert implementation == "stdlib-frozen-dataclasses"


# ─── ApiField / ApiSchema ──────────────────────────────────────────────────


def test_a_field_type_outside_the_closed_set_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        _field(type="uuid")


def test_a_blank_field_name_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        _field(name="  ")


def test_a_non_boolean_required_flag_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        _field(required="yes")


def test_a_blank_enum_member_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        _field(enum=["csv", ""])


def test_a_schema_with_no_fields_is_refused():
    # Arrange — an empty schema cannot be told apart from an undocumented body.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        ApiSchema(name="Empty", fields=[])


def test_a_schema_field_declared_twice_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        _schema(fields=[_field(), _field()])


def test_a_schema_keeps_its_declared_field_order():
    # Arrange
    schema = _schema(fields=[_field(name="b"), _field(name="a")])
    # Act
    names = [f.name for f in schema.fields]
    # Assert
    assert names == ["b", "a"]


# ─── ApiError ──────────────────────────────────────────────────────────────


def test_an_error_code_that_is_blank_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        ApiError(code="", status=400, message="bad")


def test_an_error_status_below_the_client_error_range_is_refused():
    # Arrange — a 2xx "error" is not an error any client can branch on.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        ApiError(code="no_recipe", status=200, message="no recipe loaded")


def test_an_error_status_above_the_server_error_range_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        ApiError(code="no_recipe", status=600, message="no recipe loaded")


def test_a_non_integer_error_status_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        ApiError(code="no_recipe", status="400", message="no recipe loaded")


def test_a_non_boolean_retryable_flag_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        ApiError(code="no_recipe", status=400, message="x", retryable="no")


# ─── AuthScope: fail closed ────────────────────────────────────────────────


def test_an_auth_scope_with_neither_scopes_nor_public_is_refused():
    # Arrange — forgetting to declare auth must not open an endpoint.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        AuthScope(project_scope="project")


def test_an_auth_scope_that_is_both_public_and_scoped_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="exactly one of the two"):
        AuthScope(scopes=["recipes:read"], public=True)


def test_a_public_scope_that_is_user_scoped_is_refused():
    # Arrange — a public route is not scoped to an actor. The default
    # project_scope is 'user', so omitting it here must not slip through.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="project_scope='none'"):
        AuthScope(public=True)


def test_a_public_scope_that_is_project_scoped_is_refused():
    # Arrange — a public listing advertised as project-filtered is a lie.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="project_scope='none'"):
        AuthScope(project_scope="project", public=True)


def test_an_explicitly_public_scope_is_accepted():
    # Arrange — public must be SAID, not inferred from an omission, and it
    # carries project_scope='none' with it.
    # Act
    scope = AuthScope(project_scope="none", public=True).public
    # Assert
    assert scope is True


def test_an_unknown_project_scope_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        AuthScope(project_scope="team", scopes=["recipes:read"])


def test_a_blank_oauth_scope_string_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        AuthScope(scopes=["recipes:read", " "])


# ─── Idempotency / Pagination / RateLimit / Audit / Deprecation ────────────


def test_a_non_boolean_idempotency_flag_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        Idempotency(required="yes")


def test_a_blank_idempotency_header_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        Idempotency(key_header="")


def test_an_idempotency_header_with_a_carriage_return_is_refused():
    # Arrange — "X-Key\rHost: evil" is a header name plus a second header.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="not a valid HTTP field name"):
        Idempotency(key_header="X-Key\rHost: evil")


def test_an_idempotency_header_with_a_line_feed_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="not a valid HTTP field name"):
        Idempotency(key_header="X-Key\nHost: evil")


def test_an_idempotency_header_with_a_crlf_pair_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="not a valid HTTP field name"):
        Idempotency(key_header="X-Key\r\nX-Second: 1")


def test_an_idempotency_header_with_a_control_character_is_refused():
    # Arrange — a NUL is not a tchar either, even without a newline.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="not a valid HTTP field name"):
        Idempotency(key_header="X-Key\x00")


def test_an_idempotency_header_with_a_colon_is_refused():
    # Arrange — ':' separates the name from the value, so it cannot be in one.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="not a valid HTTP field name"):
        Idempotency(key_header="X-Key:")


def test_an_idempotency_header_with_a_space_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="not a valid HTTP field name"):
        Idempotency(key_header="Idempotency Key")


def test_an_idempotency_header_with_an_inner_tab_is_refused():
    # Arrange — an inner tab is not stripped away by the blank check.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="not a valid HTTP field name"):
        Idempotency(key_header="Idempotency\tKey")


def test_a_deployment_specific_idempotency_header_is_accepted():
    # Arrange — a valid token the module has never heard of is still valid.
    # Act
    header = Idempotency(key_header="X-Idempotency-Key", required=True).key_header
    # Assert
    assert header == "X-Idempotency-Key"


def test_an_unknown_pagination_style_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        Pagination(style="page")


def test_pagination_limits_with_style_none_are_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        Pagination(style="none", default_limit=20)


def test_a_paginated_route_needs_both_limits():
    # Arrange — an unbounded page size is an unbounded response.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        Pagination(style="offset", default_limit=20)


def test_a_default_limit_above_the_maximum_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        Pagination(style="offset", default_limit=100, max_limit=50)


def test_a_bounded_pagination_declaration_is_accepted():
    # Arrange
    # Act
    style = Pagination(style="offset", default_limit=20, max_limit=100).style
    # Assert
    assert style == "offset"


def test_a_blank_rate_class_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        RateLimit(rate_class="", compute_cost="render")


def test_a_whitespace_only_rate_class_is_refused():
    # Arrange — hub ruling 2026-09-17: extensible, but never whitespace.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        RateLimit(rate_class="   ", compute_cost="render")


def test_a_blank_compute_cost_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        RateLimit(rate_class="interactive", compute_cost="")


def test_a_whitespace_only_compute_cost_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        RateLimit(rate_class="interactive", compute_cost="\t\n")


def test_a_deployment_specific_rate_class_is_accepted():
    # Arrange — the vocabulary is extensible; a third-party class must not be
    # rejected for not being one of the documented examples.
    # Act
    rate_class = RateLimit(rate_class="gpu-batch", compute_cost="heavy").rate_class
    # Assert
    assert rate_class == "gpu-batch"


def test_the_recommended_rate_classes_are_the_documented_examples():
    # Arrange — calibration: the docs quote these names, so a silent rename
    # would leave the documentation describing classes that no longer exist.
    # Act
    classes = tuple(RECOMMENDED_RATE_CLASSES)
    # Assert
    assert classes == ("interactive", "standard", "bulk")


def test_the_recommended_compute_costs_are_the_documented_examples():
    # Arrange
    # Act
    costs = tuple(RECOMMENDED_COMPUTE_COSTS)
    # Assert
    assert costs == ("light", "standard", "heavy")


def test_a_recommended_rate_class_and_cost_are_accepted_together():
    # Arrange — the documented pair must itself be a valid declaration.
    # Act
    rate = RateLimit(
        rate_class=RECOMMENDED_RATE_CLASSES[0], compute_cost=RECOMMENDED_COMPUTE_COSTS[1]
    )
    # Assert
    assert rate.compute_cost == "standard"


def test_an_unknown_audit_level_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        Audit(level="everything")


def test_a_deprecation_without_a_sunset_version_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        Deprecation(sunset_version="")


def test_a_non_dotted_sunset_version_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        Deprecation(sunset_version="soon")


def test_a_deprecation_with_a_sunset_and_a_replacement_is_accepted():
    # Arrange
    # Act
    replacement = Deprecation(sunset_version="2", replacement="recipes/save_v2").replacement
    # Assert
    assert replacement == "recipes/save_v2"


# ─── ApiRoute: the path declaration cannot escape ──────────────────────────


def test_an_absolute_route_path_is_refused():
    # Arrange — the host owns the mount prefix.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        _route(path="/recipes/save")


def test_a_traversing_route_path_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        _route(path="../../etc/passwd")


def test_a_double_slash_route_path_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        _route(path="recipes//save")


def test_a_backslash_route_path_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        _route(path="recipes\\save")


def test_a_query_string_in_a_route_path_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        _route(path="recipes/save?force=1")


def test_a_whitespace_route_path_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        _route(path="recipes/save now")


def test_a_trailing_slash_route_path_is_refused():
    # Arrange — one endpoint, two spellings: the declaration must be normalized
    # so a collision cannot hide behind a single character.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="not in NORMALIZED form"):
        _route(path="recipes/save/")


def test_two_routes_that_differ_only_by_a_trailing_slash_are_refused():
    # Arrange — the second spelling never survives route construction, so the
    # plugin can never silently keep just one of them.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="not in NORMALIZED form"):
        _plugin(routes=[
            _route(path="recipes/save"),
            _route(path="recipes/save/", handler="figrecipe.api:other"),
        ])


def test_a_placeholder_segment_is_accepted():
    # Arrange — the placeholder is declared alongside the path it appears in.
    # Act
    path = _route(path="call/{call_id}", path_params=["call_id"]).path
    # Assert
    assert path == "call/{call_id}"


# ─── ApiRoute: methods, transport, handler ─────────────────────────────────


def test_a_route_with_no_methods_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        _route(methods=[])


def test_a_lowercase_method_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        _route(methods=["get"])


def test_a_method_outside_the_declared_set_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        _route(methods=["HEAD"])


def test_a_method_declared_twice_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        _route(methods=["GET", "GET"])


def test_an_unknown_transport_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        _route(transport="graphql")


def test_a_streaming_transport_is_accepted():
    # Arrange — leaves really have SSE endpoints; a JSON-only contract would
    # make them undescribable.
    # Act
    transport = _route(transport="sse", idempotency=Idempotency(required=True)).transport
    # Assert
    assert transport == "sse"


def test_a_blank_handler_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        _route(handler="")


def test_a_shell_command_as_a_handler_is_refused():
    # Arrange — a declaration must not be able to carry a command line.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        _route(handler="rm -rf /tmp/x")


def test_a_filesystem_path_as_a_handler_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        _route(handler="/bin/sh")


def test_an_entry_point_style_handler_is_accepted():
    # Arrange — declared, never imported here.
    # Act
    handler = _route(handler="figrecipe._django.views:api_dispatch").handler
    # Assert
    assert handler == "figrecipe._django.views:api_dispatch"


# ─── ApiRoute: mutation must be idempotent-safe ────────────────────────────


def test_a_post_route_without_an_idempotency_key_is_refused():
    # Arrange — a retried POST would act twice.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        _route(methods=["POST"])


def test_a_post_route_with_a_required_idempotency_key_is_accepted():
    # Arrange
    # Act
    required = _route(methods=["POST"], idempotency=Idempotency(required=True)).idempotency.required
    # Assert
    assert required is True


def test_a_get_route_needs_no_idempotency_declaration():
    # Arrange
    # Act
    route = _route(methods=["GET"])
    # Assert
    assert route.methods == ("GET",)


def test_a_route_declaring_an_error_code_twice_is_refused():
    # Arrange
    errors = [
        ApiError(code="no_recipe", status=400, message="a"),
        ApiError(code="no_recipe", status=409, message="b"),
    ]
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        _route(errors=errors)


def test_route_keys_cover_every_declared_method():
    # Arrange
    route = _route(methods=["GET", "POST"], idempotency=Idempotency(required=True))
    # Act
    keys = route.route_keys()
    # Assert
    assert keys == (("recipes/save", "GET"), ("recipes/save", "POST"))


# ─── ApiRoute: the rate declaration is never assumed ───────────────────────


def test_a_route_that_omits_its_rate_declaration_is_refused():
    # Arrange — there is no implicit default: 'standard' is not assumed for a
    # route that never declared it, so construction refuses the omission.
    # Act
    # Assert
    with pytest.raises(TypeError, match="rate"):
        ApiRoute(
            path="recipes/save",
            methods=["GET"],
            handler="figrecipe.api:save_recipe",
            auth=_auth(),
        )


def test_a_rate_slot_that_is_not_a_rate_limit_is_refused():
    # Arrange — a bare class name must not reach the fragment renderer.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="expected a RateLimit"):
        _route(rate="standard")


def test_a_route_carries_the_rate_class_it_declared():
    # Arrange
    route = _route(rate=_rate(rate_class="bulk", compute_cost="heavy"))
    # Act
    rate_class = route.rate.rate_class
    # Assert
    assert rate_class == "bulk"


# ─── ApiPlugin ─────────────────────────────────────────────────────────────


def test_a_plugin_with_no_routes_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        ApiPlugin(id="figrecipe", title="FigRecipe", api_version="1", routes=[])


def test_a_non_dotted_api_version_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        _plugin(api_version="v1")


def test_a_blank_plugin_title_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        _plugin(title=" ")


def test_two_routes_claiming_one_path_and_method_are_refused():
    # Arrange — the host can compose only one, so the other would vanish.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        _plugin(routes=[_route(), _route(handler="figrecipe.api:other")])


def test_two_routes_on_one_path_with_different_methods_are_accepted():
    # Arrange
    routes = [_route(methods=["GET"]), _route(methods=["POST"], idempotency=Idempotency(required=True))]
    # Act
    plugin = _plugin(routes=routes)
    # Assert
    assert len(plugin.routes) == 2


def test_a_request_and_a_response_schema_sharing_a_name_are_refused():
    # Arrange — components are keyed by name, so one would overwrite the other.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="declares schema name 'SaveRequest' twice"):
        _plugin(routes=[
            _route(
                request=_schema(name="SaveRequest"),
                response=_schema(name="SaveRequest"),
            ),
        ])


def test_two_response_schemas_sharing_a_name_are_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="declares schema name 'RecipeState' twice"):
        _plugin(routes=[
            _route(response=_schema(name="RecipeState")),
            _route(path="recipes/export", handler="figrecipe.api:export", response=_schema(name="RecipeState")),
        ])


def test_a_schema_name_colliding_with_another_schemas_field_is_refused():
    # Arrange — the same flat namespace: a name that is a schema here and a
    # field there resolves to one thing a generator reads twice.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="already a declared FIELD"):
        _plugin(routes=[
            _route(response=_schema(name="RecipeState", fields=[_field(name="recipe_path")])),
            _route(
                path="recipes/export",
                handler="figrecipe.api:export",
                response=ApiSchema(name="recipe_path", fields=[_field(name="value")]),
            ),
        ])


def test_a_field_name_colliding_with_another_schemas_name_is_refused():
    # Arrange — the same rule, arrived at from the other side: a field named
    # after a schema that another route already published.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="already the NAME of"):
        _plugin(routes=[
            _route(response=_schema(name="RecipeState", fields=[_field(name="value")])),
            _route(
                path="recipes/export",
                handler="figrecipe.api:export",
                response=ApiSchema(name="ExportState", fields=[_field(name="RecipeState")]),
            ),
        ])


def test_two_schemas_sharing_a_field_name_are_accepted():
    # Arrange — fields are nested under their schema, so the same field name in
    # two schemas is normal, not a collision.
    # Act
    plugin = _plugin(routes=[
        _route(request=_schema(name="SaveRequest")),
        _route(path="recipes/export", handler="figrecipe.api:export", response=_schema(name="ExportState")),
    ])
    # Assert
    assert len(plugin.routes) == 2


def test_a_request_that_is_not_an_api_schema_is_refused():
    # Arrange — a string in a schema slot must not reach a name lookup.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="expected an ApiSchema or None"):
        _route(request="SaveRequest")


# ─── strict nested element types ───────────────────────────────────────────
#
# Every declared sequence must hold INSTANCES of its descriptor type. A
# duck-typed stand-in (a dict shaped like a field, an int where a method was
# meant) has to be refused HERE, by name, rather than surfacing later as an
# AttributeError inside a renderer.


def test_a_schema_field_that_is_not_an_api_field_is_refused():
    # Arrange — a bare string where the field descriptor was meant.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="element 0 is 'recipe_path'"):
        ApiSchema(name="SaveRequest", fields=_BAD_FIELDS)


def test_a_route_that_is_not_an_api_route_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="expected an instance of ApiRoute"):
        _plugin(routes=_BAD_ROUTES)


def test_a_dict_that_merely_looks_like_a_route_is_refused():
    # Arrange — duck typing would accept this and fail three frames deeper.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="expected an instance of ApiRoute"):
        _plugin(routes=[{"path": "recipes/save", "methods": ["GET"]}])


def test_a_non_boolean_route_element_is_refused():
    # Arrange — the error must name the element and its index, not the list.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="element 0 is 1"):
        _route(methods=_BAD_METHODS)


def test_a_non_string_scope_element_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="element 0 is 1"):
        AuthScope(project_scope="project", scopes=_BAD_SCOPES)


def test_a_non_api_error_element_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="element 0 is 1"):
        _route(errors=_BAD_ERRORS)


def test_a_non_string_enum_element_is_refused():
    # Arrange — naming the FIELD, so the offending declaration is findable.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="enum of field 'recipe_path'"):
        _field(enum=_BAD_ENUM)


def test_a_bare_string_where_a_sequence_is_declared_is_refused():
    # Arrange — "GET" must not be iterated character by character into ['G', ...].
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="must be a sequence of str"):
        _route(methods="GET")


# ─── the OpenAPI fragment ──────────────────────────────────────────────────


def test_the_fragment_exposes_the_declared_paths():
    # Arrange — the document is absolute even though the declaration is
    # relative to the mount: paths are keyed by what the host will serve.
    # Act
    fragment = _plugin().openapi_fragment()
    # Assert
    assert list(fragment["paths"]) == ["/recipes/save"]


def test_the_fragment_lowercases_the_operation_key():
    # Arrange
    # Act
    fragment = _plugin().openapi_fragment()
    # Assert
    assert list(fragment["paths"]["/recipes/save"]) == ["get"]


def test_the_fragment_carries_the_idempotency_header_extension():
    # Arrange
    routes = [_route(methods=["POST"], idempotency=Idempotency(required=True))]
    # Act
    fragment = _plugin(routes=routes).openapi_fragment()
    # Assert
    assert fragment["paths"]["/recipes/save"]["post"]["x-scitex-idempotency-key-header"] == "Idempotency-Key"


def test_the_fragment_carries_the_compute_cost_declaration():
    # Arrange
    routes = [_route(rate=RateLimit(rate_class="interactive", compute_cost="render"))]
    # Act
    fragment = _plugin(routes=routes).openapi_fragment()
    # Assert
    assert fragment["paths"]["/recipes/save"]["get"]["x-scitex-compute-cost"] == "render"


def test_the_fragment_marks_a_deprecation_with_its_sunset():
    # Arrange
    routes = [_route(deprecation=Deprecation(sunset_version="2"))]
    # Act
    fragment = _plugin(routes=routes).openapi_fragment()
    # Assert
    assert fragment["paths"]["/recipes/save"]["get"]["x-scitex-sunset-version"] == "2"


def test_the_fragment_marks_a_public_route_as_unsecured():
    # Arrange
    routes = [_route(auth=AuthScope(public=True, project_scope="none"))]
    # Act
    fragment = _plugin(routes=routes).openapi_fragment()
    # Assert
    assert fragment["paths"]["/recipes/save"]["get"]["security"] == []


def test_the_fragment_reports_scoped_routes_with_their_oauth_scopes():
    # Arrange
    # Act
    fragment = _plugin().openapi_fragment()
    # Assert
    assert fragment["paths"]["/recipes/save"]["get"]["x-scitex-oauth-scopes"] == ["recipes:write"]


def test_a_scoped_operation_declares_a_standard_security_requirement():
    # Arrange — a generic consumer reads `security`, not a vendor extension.
    # Act
    fragment = _plugin().openapi_fragment()
    # Assert
    assert fragment["paths"]["/recipes/save"]["get"]["security"] == [
        {OAUTH_SECURITY_SCHEME: ["recipes:write"]}
    ]


def test_the_fragment_declares_the_security_scheme_component():
    # Arrange — the requirement must name a scheme the document defines.
    # Act
    scheme = _plugin().openapi_fragment()["components"]["securitySchemes"][
        OAUTH_SECURITY_SCHEME
    ]
    # Assert
    assert list(scheme) == ["type", "description", "flows"]


def test_the_security_scheme_is_oauth2_because_the_requirement_carries_scopes():
    # Arrange — blocker 5: this arm used to pin `scheme == "bearer"`, i.e. an
    # http bearer component while every operation requirement carried an OAuth2
    # SCOPE ARRAY. A bearer scheme publishes no flows and no scope map, so the
    # document named scopes it never defined and showed no way to obtain a token.
    # Act
    scheme = _plugin().openapi_fragment()["components"]["securitySchemes"][
        OAUTH_SECURITY_SCHEME
    ]
    # Assert
    assert scheme["type"] == "oauth2"


def test_the_security_scheme_publishes_the_declared_flow_endpoints():
    # Arrange — the endpoints come from the DECLARATION, never from a renderer:
    # an invented production URL is a promise the leaf never made.
    # Act
    scheme = _plugin().openapi_fragment()["components"]["securitySchemes"][
        OAUTH_SECURITY_SCHEME
    ]
    # Assert
    assert scheme["flows"][OAUTH2_FLOW]["authorizationUrl"] == (
        "https://auth.scitex.example/oauth2/authorize"
    )


def test_the_security_scheme_publishes_the_declared_token_endpoint():
    # Arrange
    # Act
    scheme = _plugin().openapi_fragment()["components"]["securitySchemes"][
        OAUTH_SECURITY_SCHEME
    ]
    # Assert
    assert scheme["flows"][OAUTH2_FLOW]["tokenUrl"] == (
        "https://auth.scitex.example/oauth2/token"
    )


def test_the_scheme_scope_map_names_the_scopes_the_requirement_carries():
    # Arrange — the requirement and the scheme must agree: a scope named by an
    # operation but absent from the scheme's map resolves to nothing.
    # Act
    fragment = _plugin().openapi_fragment()
    declared = fragment["components"]["securitySchemes"][OAUTH_SECURITY_SCHEME][
        "flows"
    ][OAUTH2_FLOW]["scopes"]
    required = fragment["paths"]["/recipes/save"]["get"]["security"][0][
        OAUTH_SECURITY_SCHEME
    ]
    # Assert
    assert all(scope in declared for scope in required)


def test_a_scoped_plugin_without_an_oauth_provider_is_refused():
    # Arrange — a scope-carrying requirement is satisfied by an oauth2 scheme,
    # which cannot be emitted without the authorization/token endpoints.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="no OAuth provider"):
        _plugin(oauth=None)


def test_a_scope_the_provider_never_declares_is_refused():
    # Arrange — the requirement would name a scope the scheme's map omits.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="does not declare"):
        _plugin(oauth=_oauth(scopes={"other:scope": "Something else"}))


def test_a_scope_declaration_that_is_not_a_mapping_is_refused():
    # Arrange — a sequence of pairs is not the map OpenAPI requires.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="must be a mapping"):
        _oauth(scopes=[("recipes:write", "Write recipes")])


def test_an_empty_scope_map_is_refused():
    # Arrange — the validator accepts an empty map (measured), so the refusal
    # has to live here: a scheme defining no scope cannot back any requirement.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="declares none"):
        _oauth(scopes={})


def test_a_relative_authorization_url_is_refused():
    # Arrange — a flow endpoint a client must call has to name scheme and host.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="absolute http"):
        _oauth(authorization_url="/oauth2/authorize")


def test_a_non_string_scope_description_is_refused():
    # Arrange — the scheme's scope map is prose; a non-string is not.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="must be a non-blank string"):
        _oauth(scopes={"recipes:write": 5})


def test_a_public_only_plugin_needs_no_oauth_provider():
    # Arrange — a public route carries `security: []` and names no scope, so
    # there is nothing a provider would issue.
    # Act
    components = _plugin(
        routes=[_route(auth=AuthScope(project_scope="none", public=True))],
        oauth=None,
    ).openapi_fragment()["components"]
    # Assert
    assert components["securitySchemes"] == {}


def test_the_fragment_emits_a_path_parameter_for_every_placeholder():
    # Arrange
    routes = [_route(path="call/{call_id}", path_params=["call_id"])]
    # Act
    fragment = _plugin(routes=routes).openapi_fragment()
    # Assert
    assert fragment["paths"]["/call/{call_id}"]["get"]["parameters"][0]["name"] == "call_id"


def test_a_path_parameter_is_required_and_string_typed():
    # Arrange
    routes = [_route(path="call/{call_id}", path_params=["call_id"])]
    # Act
    parameter = _plugin(routes=routes).openapi_fragment()["paths"]["/call/{call_id}"][
        "get"
    ]["parameters"][0]
    # Assert
    assert (parameter["in"], parameter["required"], parameter["schema"]) == (
        "path",
        True,
        {"type": "string"},
    )


def test_a_placeholder_that_is_never_declared_is_refused():
    # Arrange — a client cannot send an argument nobody declared.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="not declared in path_params"):
        _route(path="call/{call_id}")


def test_a_declared_path_param_absent_from_the_path_is_refused():
    # Arrange — the route would promise a parameter it never receives.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="do not appear as"):
        _route(path="call", path_params=["call_id"])


def test_a_path_parameter_declared_twice_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="path parameter twice"):
        _route(path="{a}/{b}", path_params=["a", "a", "b"])


def test_a_non_string_path_param_element_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="element 0 is 1"):
        _route(path="call/{call_id}", path_params=[1])


def test_each_method_gets_its_own_operation_id():
    # Arrange — a deep-copied operation would give both methods one id, which
    # OpenAPI forbids.
    routes = [_route(methods=["GET", "POST"], idempotency=Idempotency(required=True))]
    # Act
    entry = _plugin(routes=routes).openapi_fragment()["paths"]["/recipes/save"]
    # Assert
    assert entry["get"]["operationId"] != entry["post"]["operationId"]


def test_each_method_gets_its_own_operation_object():
    # Arrange — method-specific metadata is built per method, not shared.
    routes = [_route(methods=["GET", "POST"], idempotency=Idempotency(required=True))]
    # Act
    entry = _plugin(routes=routes).openapi_fragment()["paths"]["/recipes/save"]
    # Assert
    assert entry["get"] is not entry["post"]


def test_the_operation_id_names_the_lowercased_method():
    # Arrange — the path is PERCENT-ENCODED into the id, not flattened: the old
    # `path.replace("/", "_")` form ("figrecipe.get.recipes_save") was lossy, and
    # `a/b_c` collapsed onto the same id as `a_b/c` (blocker 1). A slash inside a
    # path segment is spelled out, so the id cannot be confused with a path whose
    # segment happens to contain the character the old joiner used.
    # Act
    fragment = _plugin().openapi_fragment()
    # Assert
    assert fragment["paths"]["/recipes/save"]["get"]["operationId"] == (
        "figrecipe.get.recipes%2Fsave"
    )


def test_every_generated_schema_forbids_additional_properties():
    # Arrange — the declared fields ARE the body.
    # Act
    schemas = _plugin(routes=[_route(response=_schema(name="RecipeState"))]).openapi_fragment()[
        "components"
    ]["schemas"]
    # Assert
    assert schemas["RecipeState"]["additionalProperties"] is False


def test_the_fragment_emits_a_component_schema_for_a_declared_response():
    # Arrange
    routes = [_route(response=_schema(name="RecipeState"))]
    # Act
    fragment = _plugin(routes=routes).openapi_fragment()
    # Assert
    assert "RecipeState" in fragment["components"]["schemas"]


def test_the_fragment_references_the_response_schema():
    # Arrange
    routes = [_route(response=_schema(name="RecipeState"))]
    # Act
    fragment = _plugin(routes=routes).openapi_fragment()
    # Assert
    ref = fragment["paths"]["/recipes/save"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    assert ref == "#/components/schemas/RecipeState"


def test_the_fragment_uses_the_streaming_media_type_for_sse():
    # Arrange
    routes = [_route(transport="sse", response=_schema(name="ChatChunk"), idempotency=Idempotency(required=True))]
    # Act
    fragment = _plugin(routes=routes).openapi_fragment()
    # Assert
    content = fragment["paths"]["/recipes/save"]["get"]["responses"]["200"]["content"]
    assert list(content) == ["text/event-stream"]


def test_the_fragment_uses_the_binary_media_type_for_a_download():
    # Arrange
    routes = [_route(transport="binary", response=_schema(name="Download"))]
    # Act
    fragment = _plugin(routes=routes).openapi_fragment()
    # Assert
    content = fragment["paths"]["/recipes/save"]["get"]["responses"]["200"]["content"]
    assert list(content) == ["application/octet-stream"]


def test_the_fragment_reports_declared_errors_with_their_retryability():
    # Arrange
    errors = [ApiError(code="no_recipe", status=400, message="no recipe loaded", retryable=False)]
    # Act
    fragment = _plugin(routes=[_route(errors=errors)]).openapi_fragment()
    # Assert
    entry = fragment["paths"]["/recipes/save"]["get"]["responses"]["default"]["x-scitex-errors"][0]
    assert entry["retryable"] is False


def test_the_fragment_carries_the_pagination_bounds():
    # Arrange
    routes = [_route(pagination=Pagination(style="offset", default_limit=20, max_limit=100))]
    # Act
    fragment = _plugin(routes=routes).openapi_fragment()
    # Assert
    pagination = fragment["paths"]["/recipes/save"]["get"]["x-scitex-pagination"]
    assert pagination["max_limit"] == 100


def test_the_fragment_names_the_handler_for_the_composer():
    # Arrange
    # Act
    fragment = _plugin().openapi_fragment()
    # Assert
    assert fragment["paths"]["/recipes/save"]["get"]["x-scitex-handler"] == "figrecipe.api:save_recipe"


def test_every_declared_route_appears_in_the_fragment():
    # Arrange
    routes = [_route(path="recipes/save"), _route(path="recipes/export", handler="figrecipe.api:export")]
    # Act
    fragment = _plugin(routes=routes).openapi_fragment()
    # Assert
    assert sorted(fragment["paths"]) == ["/recipes/export", "/recipes/save"]


# ─── blocker 1: operationIds are INJECTIVE, not lossy ──────────────────────
#
# `a/b_c` and `a_b/c` are two different routes whose paths both flattened to
# `a_b_c` under the old `path.replace("/", "_")` slug, so the document carried
# one operationId for two operations and openapi-spec-validator reported
# `DuplicateOperationIDError`. Each arm below feeds that adversarial pair (or a
# sibling of it) in, and the last one pins the encoding itself.


def test_paths_that_flatten_to_one_slug_get_distinct_operation_ids():
    # Arrange — the adversarial pair a/b_c vs a_b/c.
    routes = [_route(path="a/b_c"), _route(path="a_b/c", handler="figrecipe.api:other")]
    # Act
    entry = _plugin(routes=routes).openapi_fragment()["paths"]
    # Assert
    assert entry["/a/b_c"]["get"]["operationId"] != entry["/a_b/c"]["get"]["operationId"]


def test_a_placeholder_path_does_not_collide_with_its_literal_sibling():
    # Arrange — the old id stripped the braces, so `call/{call_id}` and
    # `call/call_id` both became `call_call_id`.
    routes = [
        _route(path="call/{call_id}", path_params=["call_id"]),
        _route(path="call/call_id", handler="figrecipe.api:other"),
    ]
    # Act
    entry = _plugin(routes=routes).openapi_fragment()["paths"]
    # Assert
    assert (
        entry["/call/{call_id}"]["get"]["operationId"]
        != entry["/call/call_id"]["get"]["operationId"]
    )


def test_the_operation_id_escapes_a_dot_inside_a_path_segment():
    # Arrange — a declared segment may contain '.', which is the id's own field
    # separator: left raw, (plugin id, method, path) could not be split back.
    routes = [_route(path="get.a")]
    # Act
    operation_id = _plugin(routes=routes).openapi_fragment()["paths"]["/get.a"][
        "get"
    ]["operationId"]
    # Assert
    assert operation_id == "figrecipe.get.get%2Ea"


def test_the_operation_id_encoding_is_injective_over_the_adversarial_corpus():
    # Arrange — every pair here is one the lossy joiner conflated, fed through
    # the public surface: one single-route plugin per path.
    paths = [
        ("a/b_c", ()),
        ("a_b/c", ()),
        ("call/{call_id}", ("call_id",)),
        ("call/call_id", ()),
        ("a.b", ()),
        ("a_b", ()),
        ("x/y", ()),
        ("x_y", ()),
        ("things/{id}", ("id",)),
        ("things/{name}", ("name",)),
    ]
    ids = [
        _plugin(
            routes=[_route(path=path, path_params=list(params), handler="figrecipe.api:one")]
        ).openapi_fragment()["paths"][f"/{path}"]["get"]["operationId"]
        for path, params in paths
    ]
    # Act
    distinct = set(ids)
    # Assert
    assert len(distinct) == len(ids)


# ─── blocker 2: same-hierarchy templates are ONE OpenAPI path ──────────────
#
# `/things/{id}` and `/things/{name}` are the same path to OpenAPI, and
# openapi-spec-validator 0.9.0 does NOT catch it (pinned below): a host merging
# both would silently keep one operation. The refusal therefore has to happen at
# construction, against the CANONICAL (placeholder-name-free) path.


def test_two_same_hierarchy_templates_are_refused():
    # Arrange — different placeholder names, one path.
    routes = [
        _route(path="things/{id}", path_params=["id"]),
        _route(path="things/{name}", path_params=["name"], handler="figrecipe.api:other"),
    ]
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="twice"):
        _plugin(routes=routes)


def test_a_template_and_a_literal_sibling_are_still_distinct_routes():
    # Arrange — canonicalizing must not over-refuse: /things/{id} and /things/all
    # really are two paths.
    routes = [
        _route(path="things/{id}", path_params=["id"]),
        _route(path="things/all", handler="figrecipe.api:other"),
    ]
    # Act
    plugin = _plugin(routes=routes)
    # Assert
    assert len(plugin.routes) == 2


def test_a_dot_segment_in_a_path_is_refused():
    # Arrange — RFC 3986 removes '.' segments, so two declarations could differ
    # only by a segment the host discards.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match=r"has a '.' segment"):
        _route(path="recipes/./save")


def test_a_placeholder_repeated_in_one_path_is_refused():
    # Arrange — two segments constrained by one value would emit the same path
    # parameter twice, which is not a valid operation.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="more than once"):
        _route(path="{a}/{a}/x", path_params=["a"])


# ─── blocker 3: every nested descriptor is validated AT CONSTRUCTION ───────
#
# A dict that carries the right keys is not the descriptor. Before this, a dict
# `auth` was accepted and reached fragment generation as
# `AttributeError: 'dict' object has no attribute 'project_scope'` — an error
# naming the renderer instead of the declaration.


def test_a_dict_declared_where_the_auth_descriptor_belongs_is_refused():
    # Arrange — the shape a JSON-ish config produces.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="expected an instance of AuthScope"):
        _route(auth={"project_scope": "user", "scopes": ["recipes:write"]})


def test_a_dict_declared_where_the_idempotency_descriptor_belongs_is_refused():
    # Arrange — a mutating route whose retry promise is a plain dict.
    # Act
    # Assert
    with pytest.raises(
        ApiPluginContractError, match="expected an instance of Idempotency"
    ):
        _route(methods=["POST"], idempotency={"required": True})


def test_a_dict_declared_where_the_pagination_descriptor_belongs_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(
        ApiPluginContractError, match="expected an instance of Pagination"
    ):
        _route(pagination={"style": "offset", "default_limit": 20, "max_limit": 100})


def test_a_dict_declared_where_the_audit_descriptor_belongs_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="expected an instance of Audit"):
        _route(audit={"level": "full"})


def test_a_dict_declared_where_the_deprecation_descriptor_belongs_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="expected an instance of Deprecation"):
        _route(deprecation={"sunset_version": "2"})


def test_a_dict_declared_where_the_oauth_provider_belongs_is_refused():
    # Arrange — the provider is a descriptor too, and its URLs reach the
    # document: a dict would render as a flow with no endpoints.
    # Act
    # Assert
    with pytest.raises(
        ApiPluginContractError, match="expected an instance of OAuthProvider"
    ):
        _plugin(oauth={"authorization_url": "https://a.example/x"})


# ─── blocker 4: every value that reaches the document is a valid one ───────


def test_a_schema_name_with_a_slash_is_refused():
    # Arrange — measured: the validator rejects 'Bad/Name' on the component-key
    # pattern '^[a-zA-Z0-9._-]+$'.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="component name"):
        ApiSchema(name="Bad/Name", fields=[_field()])


def test_a_schema_name_with_a_tilde_is_refused():
    # Arrange — '~' is JSON-Pointer escaping and is not a component-key char.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="component name"):
        ApiSchema(name="Bad~Name", fields=[_field()])


def test_a_field_name_with_a_space_is_refused():
    # Arrange — schemas and fields share one namespace, so both take the
    # component-key alphabet rather than anything a JSON string allows.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="component name"):
        _field(name="recipe path")


def test_a_field_name_with_a_slash_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="component name"):
        _field(name="recipe/path")


def test_a_plugin_id_with_a_slash_is_refused():
    # Arrange — the id prefixes every operationId and names the plugin.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="component name"):
        _plugin(id="bad/id")


def test_a_component_name_using_dots_and_dashes_is_accepted():
    # Arrange — the rule is the specification's alphabet, not an over-strict one.
    # Act
    schema = ApiSchema(name="Recipe.State-1", fields=[_field()])
    # Assert
    assert schema.name == "Recipe.State-1"


def test_a_non_string_field_description_is_refused():
    # Arrange — a JSON-Schema description is a string; `5` reached the document
    # verbatim and made it invalid.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="must be a string"):
        _field(description=5)


def test_a_non_string_quota_note_is_refused():
    # Arrange — the same rule for the rate descriptor's prose.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="must be a string"):
        _rate(quota_note=5)


# ─── blocker 6: a reserved header cannot carry an idempotency key ──────────


def test_authorization_as_the_idempotency_header_is_refused():
    # Arrange — the client sends its credential in Authorization: one header
    # cannot carry both that and a replay key.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="RESERVED"):
        Idempotency(required=True, key_header="Authorization")


def test_the_reserved_header_check_ignores_case():
    # Arrange — HTTP field names are case-insensitive, so this is the same name.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="RESERVED"):
        Idempotency(required=True, key_header="authorization")


def test_proxy_authorization_as_the_idempotency_header_is_refused():
    # Arrange — the Proxy-Authorization family shares the case above.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="RESERVED"):
        Idempotency(required=True, key_header="Proxy-Authorization")


def test_cookie_as_the_idempotency_header_is_refused():
    # Arrange — Cookie carries session state, not a replay promise.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="RESERVED"):
        Idempotency(required=True, key_header="Cookie")


def test_set_cookie_as_the_idempotency_header_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="RESERVED"):
        Idempotency(required=True, key_header="Set-Cookie")


def test_host_as_the_idempotency_header_is_refused():
    # Arrange — Host is the request target, not a key a client may set.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="RESERVED"):
        Idempotency(required=True, key_header="Host")


def test_content_length_as_the_idempotency_header_is_refused():
    # Arrange — a framing field cannot also carry an application value.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="RESERVED"):
        Idempotency(required=True, key_header="Content-Length")


def test_content_type_as_the_idempotency_header_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="RESERVED"):
        Idempotency(required=True, key_header="Content-Type")


def test_transfer_encoding_as_the_idempotency_header_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="RESERVED"):
        Idempotency(required=True, key_header="Transfer-Encoding")


def test_connection_as_the_idempotency_header_is_refused():
    # Arrange — a hop-by-hop control is not the endpoint's to reinterpret.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="RESERVED"):
        Idempotency(required=True, key_header="Connection")


def test_the_reserved_set_covers_the_declared_families():
    # Arrange — calibration of the exported constant, so a silent narrowing of
    # the set cannot pass as "still refused".
    declared = {"authorization", "proxy-authorization", "cookie", "set-cookie", "host"}
    declared |= {"content-length", "content-type", "transfer-encoding", "connection"}
    # Act
    reserved = set(RESERVED_IDEMPOTENCY_HEADERS)
    # Assert
    assert declared <= reserved


# ─── blocker 7: declared sequences are deterministic, ordered inputs ───────
#
# `_require_elements` used to accept ANY iterable. A set's order is the hash
# seed's, and a generator is consumed by the first render, so one declaration
# could render two different documents (or none at all).


def test_a_set_of_methods_is_refused():
    # Arrange — a set is not ordered, so the declaration is not stable.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="a set"):
        _route(methods={"GET"})


def test_a_dict_of_methods_is_refused():
    # Arrange — a dict iterates its keys and means something other than a list.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="a dict"):
        _route(methods={"GET": True})


def test_a_set_of_scopes_is_refused():
    # Arrange — a scope list is ORDERED (it is copied into the requirement).
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="a set"):
        AuthScope(project_scope="project", scopes={"recipes:read", "recipes:write"})


def test_a_string_of_scopes_is_refused():
    # Arrange — the case to kill: "abc" must not become three one-character
    # scopes by being iterated.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="a str"):
        AuthScope(project_scope="project", scopes="abc")


def test_a_set_of_errors_is_refused():
    # Arrange
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="a set"):
        _route(errors={ApiError(code="no_recipe", status=400, message="x")})


def test_a_generator_of_enum_values_is_refused():
    # Arrange — a generator is consumed by the FIRST render; a second call would
    # see an empty enum and silently emit a document with no enum at all.
    enum = (name for name in ("csv", "png"))
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="a generator"):
        _field(enum=enum)


def test_a_tuple_of_methods_is_accepted_and_keeps_its_order():
    # Arrange — the strictness is about ORDER being declared, and a tuple
    # declares it.
    # Act
    methods = _route(methods=("GET", "POST"), idempotency=Idempotency(required=True)).methods
    # Assert
    assert methods == ("GET", "POST")


# ─── discovery: entry points are read, never imported ──────────────────────


def _ep(name: str, value: str) -> EntryPoint:
    return EntryPoint(name=name, value=value, group=API_ENTRY_POINT_GROUP)


def test_discovery_keeps_the_target_as_a_string():
    # Arrange — reading the group must not import leaf code (settings-time).
    entry_points = [_ep("figrecipe", "figrecipe.api:API_PLUGIN")]
    # Act
    found = discover_api_plugins(entry_points)
    # Assert
    assert found[0].target == "figrecipe.api:API_PLUGIN"


def test_discovery_sorts_by_entry_point_name():
    # Arrange
    entry_points = [_ep("writer", "writer.api:P"), _ep("figrecipe", "figrecipe.api:P")]
    # Act
    names = [ref.name for ref in discover_api_plugins(entry_points)]
    # Assert
    assert names == ["figrecipe", "writer"]


def test_discovery_refuses_a_duplicate_entry_point_name():
    # Arrange — "first wins" would ship the loser silently, and which one a
    # host loads would depend on install order.
    entry_points = [_ep("figrecipe", "figrecipe.api:P"), _ep("figrecipe", "other.api:P")]
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="entry point 'figrecipe'"):
        discover_api_plugins(entry_points)


def test_discovery_reports_the_distribution_when_there_is_one():
    # Arrange — a REAL installed entry point (from console_scripts, which
    # carries a distribution); EntryPoint is immutable in 3.12, so the dist
    # cannot be attached to a hand-made one.
    from importlib.metadata import entry_points

    real = next(iter(entry_points(group="console_scripts")))
    # Act
    distribution = discover_api_plugins([real])[0].distribution
    # Assert
    assert distribution != ""


def test_no_installed_package_publishes_this_group_yet():
    # Arrange — the declaration surface is new; discovery must be empty rather
    # than raise when nothing has adopted it (real measurement, no fixture).
    # Act
    found = discover_api_plugins()
    # Assert
    assert found == []


# ─── the fragment, validated by a real OpenAPI validator ───────────────────
#
# Asserting structure is still our own reading of the specification. These arms
# merge the fragment into a complete document and hand it to
# openapi-spec-validator (0.9.x, OpenAPI 3.1.0 — the validator supports 3.1), so
# the check is the one a host's own tooling performs. The adversarial arms prove
# the validator is really inspecting the document rather than accepting it.


def _validated_document(plugin: ApiPlugin) -> dict:
    """The plugin's fragment as a complete OpenAPI 3.1 document."""
    document: dict = {
        "openapi": "3.1.0",
        "info": {"title": plugin.title, "version": plugin.api_version},
    }
    document.update(plugin.openapi_fragment())
    return document


def test_a_plain_fragment_validates_as_an_openapi_31_document():
    # Arrange
    validate = pytest.importorskip("openapi_spec_validator").validate
    document = _validated_document(_plugin())
    # Act
    result = validate(document)
    # Assert
    assert result is None


def test_a_fully_declared_fragment_validates_as_an_openapi_31_document():
    # Arrange — one document carrying every descriptor the contract has: a path
    # parameter, a body in, a body out, structured errors, pagination, a sunset
    # window and a public streaming route.
    validate = pytest.importorskip("openapi_spec_validator").validate
    plugin = _plugin(routes=[
        _route(
            path="call/{call_id}",
            path_params=["call_id"],
            methods=["POST"],
            idempotency=Idempotency(required=True),
            request=_schema(name="CallRequest"),
            response=_schema(name="CallResult"),
            errors=[ApiError(code="no_call", status=404, message="no call", retryable=False)],
            pagination=Pagination(style="cursor", default_limit=20, max_limit=100),
            deprecation=Deprecation(sunset_version="2", replacement="call/{call_id}"),
        ),
        _route(
            path="recipes",
            methods=["GET"],
            auth=AuthScope(project_scope="none", public=True),
            transport="sse",
        ),
    ])
    document = _validated_document(plugin)
    # Act
    result = validate(document)
    # Assert
    assert result is None


def test_the_validator_refuses_duplicate_operation_ids_in_a_document():
    # Arrange — proves the validator inspects operationIds, and pins why they
    # are built per method rather than deep-copied.
    validate = pytest.importorskip("openapi_spec_validator").validate
    errors = pytest.importorskip("openapi_spec_validator.validation.exceptions")
    routes = [_route(methods=["GET", "POST"], idempotency=Idempotency(required=True))]
    document = _validated_document(_plugin(routes=routes))
    for operation in document["paths"]["/recipes/save"].values():
        operation["operationId"] = "figrecipe.duplicated"
    # Act
    # Assert
    with pytest.raises(errors.DuplicateOperationIDError):
        validate(document)


def test_the_validator_refuses_a_relative_path_key():
    # Arrange — pins why the generated keys carry a leading slash.
    validate = pytest.importorskip("openapi_spec_validator").validate
    errors = pytest.importorskip("openapi_spec_validator.validation.exceptions")
    document = _validated_document(_plugin())
    document["paths"] = {"recipes/save": document["paths"]["/recipes/save"]}
    # Act
    # Assert
    with pytest.raises(errors.OpenAPIValidationError):
        validate(document)


def test_the_validator_refuses_a_path_template_without_its_parameter():
    # Arrange — pins why every declared {param} is emitted: without the
    # parameter the document does not resolve at all.
    validate = pytest.importorskip("openapi_spec_validator").validate
    errors = pytest.importorskip("openapi_spec_validator.validation.exceptions")
    routes = [_route(path="call/{call_id}", path_params=["call_id"])]
    document = _validated_document(_plugin(routes=routes))
    document["paths"]["/call/{call_id}"]["get"].pop("parameters")
    # Act
    # Assert
    with pytest.raises(errors.UnresolvableParameterError):
        validate(document)


def test_the_validated_document_carries_the_declared_security_scheme():
    # Arrange — the requirement names a scheme the document itself defines, so
    # a validator resolves it instead of rejecting an unknown name.
    validate = pytest.importorskip("openapi_spec_validator").validate
    document = _validated_document(_plugin())
    # Act
    validate(document)
    # Assert
    assert list(document["components"]["securitySchemes"]) == [OAUTH_SECURITY_SCHEME]


def test_the_validator_accepts_the_document_for_the_two_flattening_paths():
    # Arrange — blocker 1, through the real validator: `a/b_c` and `a_b/c` are
    # distinct routes that the old lossy operationId collapsed into one, and the
    # validator refused the document with DuplicateOperationIDError. This is the
    # arm that failed before the fix.
    validate = pytest.importorskip("openapi_spec_validator").validate
    routes = [_route(path="a/b_c"), _route(path="a_b/c", handler="figrecipe.api:other")]
    document = _validated_document(_plugin(routes=routes))
    # Act
    result = validate(document)
    # Assert
    assert result is None


def test_the_validator_refuses_a_component_key_outside_the_alphabet():
    # Arrange — blocker 4, pinned against the validator rather than against a
    # literal regex: the contract's component-name rule IS this check, applied at
    # construction so the invalid document is never buildable. The document here
    # is built from a VALID declaration and then renamed by hand.
    validate = pytest.importorskip("openapi_spec_validator").validate
    errors = pytest.importorskip("openapi_spec_validator.validation.exceptions")
    routes = [_route(response=_schema(name="RecipeState"))]
    document = _validated_document(_plugin(routes=routes))
    schemas = document["components"]["schemas"]
    schemas["Bad/Name"] = schemas.pop("RecipeState")
    # Act
    # Assert
    with pytest.raises(errors.OpenAPIValidationError):
        validate(document)


def test_the_validator_does_not_catch_two_same_hierarchy_templates():
    # Arrange — blocker 2: fed the /things/{id} + /things/{name} document
    # DIRECTLY, openapi-spec-validator 0.9.0 accepts it. Nothing downstream
    # reports the conflict, so the refusal has to live in the contract (see
    # test_two_same_hierarchy_templates_are_refused) rather than in the check a
    # host runs on the merged document.
    validate = pytest.importorskip("openapi_spec_validator").validate

    def path_parameter(name: str) -> dict:
        return {
            "name": name,
            "in": "path",
            "required": True,
            "schema": {"type": "string"},
        }

    document = {
        "openapi": "3.1.0",
        "info": {"title": "t", "version": "1"},
        "paths": {
            "/things/{id}": {
                "get": {"operationId": "a", "parameters": [path_parameter("id")]}
            },
            "/things/{name}": {
                "get": {"operationId": "b", "parameters": [path_parameter("name")]}
            },
        },
    }
    # Act
    result = validate(document)
    # Assert
    assert result is None


def test_the_validator_accepts_the_document_of_a_public_only_plugin():
    # Arrange — a plugin with no provider emits no securitySchemes; the document
    # must still be complete rather than carry a dangling scheme.
    validate = pytest.importorskip("openapi_spec_validator").validate
    routes = [_route(auth=AuthScope(project_scope="none", public=True))]
    document = _validated_document(_plugin(routes=routes, oauth=None))
    # Act
    result = validate(document)
    # Assert
    assert result is None


# ─── the third review: MERGE one path, STORE what was validated ────────────
#
# Three blockers were reproduced at 1ad8269:
#
#  1. the public model accepted `GET x` and `POST x` as two separate routes while
#     openapi_fragment() REFUSED the second instead of merging both operations
#     into ONE Path Item;
#  2. ApiSchema(' Bad ', ...) constructed and then EMITTED the padded component
#     key, which openapi-spec-validator rejects;
#  3. a padded absolute OAuth authorization URL constructed and was emitted
#     unchanged.
#
# 2 and 3 are one defect class: a validator that returns the NORMALIZED value
# while the descriptor stores the DECLARED one. Every arm below asserts the
# EMITTED value, because "construction succeeded" is exactly what the review
# measured to be insufficient — a check whose result is not stored is not a
# check. (For the two OAuth endpoint URLs the fourth review closed the class
# harder still: the raw declaration is validated as a whole RFC 3986 URI and a
# padded one is refused, so the arms for them below are refusals.)


def test_two_routes_with_disjoint_methods_render_one_path_item():
    # Arrange — blocker 1: GET x and POST x are two operations on one URL.
    routes = [
        _route(),
        _route(methods=["POST"], idempotency=Idempotency(required=True)),
    ]
    # Act
    paths = _plugin(routes=routes).openapi_fragment()["paths"]
    # Assert
    assert (list(paths), sorted(paths["/recipes/save"])) == (
        ["/recipes/save"],
        ["get", "post"],
    )


def test_the_merged_path_item_gives_each_method_its_own_operation_id():
    # Arrange — one shared operation dict would publish one id for two methods,
    # which OpenAPI forbids.
    routes = [
        _route(),
        _route(methods=["POST"], idempotency=Idempotency(required=True)),
    ]
    # Act
    item = _plugin(routes=routes).openapi_fragment()["paths"]["/recipes/save"]
    # Assert
    assert item["get"]["operationId"] != item["post"]["operationId"]


def test_each_merged_operation_is_built_for_its_own_route():
    # Arrange — the merge must not let one method's metadata stand for the
    # other's: the POST here is the streaming one.
    routes = [
        _route(),
        _route(
            methods=["POST"],
            idempotency=Idempotency(required=True),
            transport="sse",
        ),
    ]
    # Act
    item = _plugin(routes=routes).openapi_fragment()["paths"]["/recipes/save"]
    # Assert
    assert (item["get"]["x-scitex-transport"], item["post"]["x-scitex-transport"]) == (
        "json",
        "sse",
    )


def test_two_routes_claiming_one_path_and_method_are_still_refused():
    # Arrange — the genuine collision: the host composes one operation there and
    # the loser disappears without a trace.
    routes = [_route(), _route(handler="figrecipe.api:other")]
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="twice"):
        _plugin(routes=routes)


def test_two_get_routes_on_one_path_are_refused_before_any_render():
    # Arrange — the arm that pins CONSTRUCTION, not rendering: the model and the
    # renderer must agree, so the refusal cannot wait for openapi_fragment().
    routes = [_route(), _route(handler="figrecipe.api:other")]
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="twice"):
        ApiPlugin(
            id="figrecipe",
            title="FigRecipe",
            api_version="1",
            routes=routes,
            oauth=_oauth(),
        )


def test_two_spellings_of_one_canonical_path_stay_refused_with_disjoint_methods():
    # Arrange — `things/{id}` and `things/{name}` are ONE OpenAPI path, so there
    # is no single template to merge two spellings under: the emitted item would
    # name one of them and the other operation's parameter would resolve to
    # nothing.
    routes = [
        _route(path="things/{id}", path_params=["id"]),
        _route(
            path="things/{name}",
            path_params=["name"],
            methods=["POST"],
            idempotency=Idempotency(required=True),
            handler="figrecipe.api:other",
        ),
    ]
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="ONE path"):
        _plugin(routes=routes)


def test_the_merged_path_document_validates():
    # Arrange — blocker 1 through the real validator, on the document a host
    # would merge.
    validate = pytest.importorskip("openapi_spec_validator").validate
    routes = [
        _route(),
        _route(methods=["POST"], idempotency=Idempotency(required=True)),
    ]
    document = _validated_document(_plugin(routes=routes))
    # Act
    result = validate(document)
    # Assert
    assert result is None


def test_a_padded_schema_name_is_emitted_stripped():
    # Arrange — blocker 2: the padded key is what openapi-spec-validator 0.9.0
    # refuses, and this arm reads the key the fragment actually carries.
    routes = [_route(response=_schema(name=" SaveRequest "))]
    # Act
    schemas = _plugin(routes=routes).openapi_fragment()["components"]["schemas"]
    # Assert
    assert list(schemas) == ["SaveRequest"]


def test_the_emitted_reference_names_the_stripped_schema_key():
    # Arrange — a stripped key with an unstripped $ref would be a dangling one.
    routes = [_route(response=_schema(name=" SaveRequest "))]
    # Act
    schema = _plugin(routes=routes).openapi_fragment()["paths"]["/recipes/save"][
        "get"
    ]["responses"]["200"]["content"]["application/json"]["schema"]
    # Assert
    assert schema == {"$ref": "#/components/schemas/SaveRequest"}


def test_the_document_of_a_padded_schema_name_validates():
    # Arrange — the fix, measured against the validator that rejects the padded
    # key (pinned below by test_the_validator_refuses_a_padded_component_key).
    validate = pytest.importorskip("openapi_spec_validator").validate
    document = _validated_document(
        _plugin(routes=[_route(response=_schema(name=" SaveRequest "))])
    )
    # Act
    result = validate(document)
    # Assert
    assert result is None


def test_a_padded_field_name_is_emitted_stripped():
    # Arrange — a JSON-Schema property name is read from the same flat namespace.
    routes = [_route(response=_schema(fields=[_field(name=" recipe_path ")]))]
    # Act
    properties = _plugin(routes=routes).openapi_fragment()["components"][
        "schemas"
    ]["SaveRequest"]["properties"]
    # Assert
    assert list(properties) == ["recipe_path"]


def test_a_padded_field_name_reaches_the_required_list_stripped():
    # Arrange — the required list is written from the same declared names.
    routes = [_route(response=_schema(fields=[_field(name=" recipe_path ")]))]
    # Act
    fragment = _plugin(routes=routes).openapi_fragment()["components"]["schemas"][
        "SaveRequest"
    ]
    # Assert
    assert fragment["required"] == ["recipe_path"]


def test_a_padded_enum_member_is_emitted_stripped():
    # Arrange — an enum member is a value a client matches on, not prose.
    routes = [
        _route(response=_schema(fields=[_field(name="fmt", enum=[" csv ", "png"])]))
    ]
    # Act
    entry = _plugin(routes=routes).openapi_fragment()["components"]["schemas"][
        "SaveRequest"
    ]["properties"]["fmt"]
    # Assert
    assert entry["enum"] == ["csv", "png"]


def test_a_padded_path_parameter_is_emitted_stripped():
    # Arrange — the emitted parameter name has to be the template's own name.
    routes = [_route(path="call/{call_id}", path_params=[" call_id "])]
    # Act
    fragment = _plugin(routes=routes).openapi_fragment()["paths"]["/call/{call_id}"][
        "get"
    ]
    # Assert
    assert fragment["parameters"][0]["name"] == "call_id"


def test_padded_route_scopes_are_stored_stripped():
    # Arrange — a scope is copied into the security requirement verbatim.
    # Act
    scopes = AuthScope(project_scope="project", scopes=[" recipes:write "]).scopes
    # Assert
    assert scopes == ("recipes:write",)


def test_a_padded_plugin_id_is_emitted_stripped():
    # Arrange — the id is the first field of every operationId, so a padded one
    # would publish ids that no host-generated id matches.
    # Act
    operation_id = _plugin(id=" figrecipe ").openapi_fragment()["paths"][
        "/recipes/save"
    ]["get"]["operationId"]
    # Assert
    assert operation_id == "figrecipe.get.recipes%2Fsave"


def test_a_padded_api_version_is_emitted_stripped():
    # Arrange
    # Act
    version = _plugin(api_version=" 1 ").openapi_fragment()["paths"]["/recipes/save"][
        "get"
    ]["x-scitex-api-version"]
    # Assert
    assert version == "1"


def test_a_padded_title_is_stored_stripped():
    # Arrange — the title becomes the document's `info.title` on the host side.
    # Act
    title = _plugin(title=" FigRecipe ").title
    # Assert
    assert title == "FigRecipe"


def test_a_padded_handler_is_emitted_stripped():
    # Arrange — the composer resolves exactly this declared string.
    # Act
    handler = _plugin(routes=[_route(handler=" figrecipe.api:save_recipe ")]) \
        .openapi_fragment()["paths"]["/recipes/save"]["get"]["x-scitex-handler"]
    # Assert
    assert handler == "figrecipe.api:save_recipe"


def test_a_padded_error_code_and_message_are_emitted_stripped():
    # Arrange — a client branches on the code and shows the message.
    errors = [ApiError(code=" no_recipe ", status=404, message=" no such recipe ")]
    # Act
    entry = _plugin(routes=[_route(errors=errors)]).openapi_fragment()["paths"][
        "/recipes/save"
    ]["get"]["responses"]["default"]["x-scitex-errors"][0]
    # Assert
    assert (entry["code"], entry["message"]) == ("no_recipe", "no such recipe")


def test_a_padded_rate_class_is_emitted_stripped():
    # Arrange
    # Act
    value = _plugin(routes=[_route(rate=_rate(rate_class=" standard "))]) \
        .openapi_fragment()["paths"]["/recipes/save"]["get"]["x-scitex-rate-class"]
    # Assert
    assert value == "standard"


def test_a_padded_compute_cost_is_emitted_stripped():
    # Arrange
    # Act
    value = _plugin(routes=[_route(rate=_rate(compute_cost=" heavy "))]) \
        .openapi_fragment()["paths"]["/recipes/save"]["get"]["x-scitex-compute-cost"]
    # Assert
    assert value == "heavy"


def test_a_padded_sunset_version_and_replacement_are_emitted_stripped():
    # Arrange — the sunset window is what tells a client when the route goes.
    routes = [
        _route(deprecation=Deprecation(sunset_version=" 2 ", replacement=" call/x "))
    ]
    # Act
    operation = _plugin(routes=routes).openapi_fragment()["paths"]["/recipes/save"][
        "get"
    ]
    # Assert
    assert (
        operation["x-scitex-sunset-version"],
        operation["x-scitex-replacement"],
    ) == ("2", "call/x")


def test_a_padded_authorization_url_is_refused():
    # Arrange — the third review closed blocker 3 by STORING the stripped URL;
    # it is stored stripped no longer. The fourth review validates the endpoint
    # as a WHOLE RFC 3986 URI against the RAW declaration, and no URI carries
    # padding, so the padded form is refused rather than normalized: the string
    # a client is handed is then always the string that was validated, and no
    # strip can be forgotten because there is no strip.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="whitespace"):
        _oauth(
            authorization_url=" https://auth.scitex.example/oauth2/authorize "
        )


def test_a_padded_token_url_is_refused():
    # Arrange — the same rule for the endpoint that issues the token.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="whitespace"):
        _oauth(token_url=" https://auth.scitex.example/oauth2/token ")


def test_a_padded_scope_name_is_emitted_stripped_in_the_flow_map():
    # Arrange — the map's KEY is the scope a requirement names.
    provider = _oauth(scopes={" recipes:write ": " Create and modify recipes "})
    # Act
    flows = _plugin(oauth=provider).openapi_fragment()["components"][
        "securitySchemes"
    ][OAUTH_SECURITY_SCHEME]["flows"]
    # Assert
    assert flows[OAUTH2_FLOW]["scopes"] == {
        "recipes:write": "Create and modify recipes"
    }


def test_a_padded_scope_name_resolves_in_the_operation_requirement():
    # Arrange — the route's spelling and the provider's spelling normalize to
    # one name, which is what makes the requirement resolvable rather than
    # naming a scope the scheme's map omits.
    routes = [
        _route(auth=AuthScope(project_scope="project", scopes=[" recipes:write "]))
    ]
    provider = _oauth(scopes={" recipes:write ": "Create and modify recipes"})
    # Act
    requirement = _plugin(routes=routes, oauth=provider).openapi_fragment()["paths"][
        "/recipes/save"
    ]["get"]["security"]
    # Assert
    assert requirement == [{OAUTH_SECURITY_SCHEME: ["recipes:write"]}]


def test_two_spellings_of_one_scope_are_refused():
    # Arrange — the map is keyed by name, so one spelling would be dropped and a
    # requirement naming it would resolve to nothing.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="twice"):
        _oauth(scopes={"recipes:write": "a", " recipes:write ": "b"})


def test_the_document_of_a_localhost_provider_validates():
    # Arrange — the endpoint forms the contract ACCEPTS have to be emittable
    # into a document the host's own tooling accepts, not merely constructible:
    # http, an explicit port and an IPv4-literal host are all legal here (a
    # localhost deployment is a deployment), while the padded provider this arm
    # used to carry is refused at construction since the fourth review.
    validate = pytest.importorskip("openapi_spec_validator").validate
    provider = _oauth(
        authorization_url="http://127.0.0.1:8443/oauth2/authorize",
        token_url="https://auth.scitex.example/oauth2/token",
    )
    document = _validated_document(_plugin(oauth=provider))
    # Act
    result = validate(document)
    # Assert
    assert result is None


def test_a_padded_choice_value_is_refused_rather_than_normalized():
    # Arrange — the store rule covers TEXT, not a closed set: `" json "` is not
    # a transport, and stripping it would invent a declaration nobody made.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError):
        _route(transport=" json ")


def test_the_validator_refuses_a_padded_component_key():
    # Arrange — pins WHY storing the normalized name is the fix rather than a
    # nicety: the document is built from a valid declaration and then padded by
    # hand, exactly as the padded key was emitted before the fix.
    validate = pytest.importorskip("openapi_spec_validator").validate
    errors = pytest.importorskip("openapi_spec_validator.validation.exceptions")
    routes = [_route(response=_schema(name="RecipeState"))]
    document = _validated_document(_plugin(routes=routes))
    schemas = document["components"]["schemas"]
    schemas[" RecipeState "] = schemas.pop("RecipeState")
    # Act
    # Assert
    with pytest.raises(errors.OpenAPIValidationError):
        validate(document)


# ─── the fourth review: the ENDPOINT URI is validated on the RAW string ────
#
# Three defects were reproduced at 1c5bcd3, all one defect class: every check
# ran against what `urlsplit` RETURNED, and `urlsplit` DELETES every C0
# control, every DEL and any leading whitespace from the string it parses
# (WHATWG-compatible, adopted by CPython). Measured at the reviewed head:
#
#   urlsplit("https://auth.example/oa\nuth").path   ==  "/oauth"   (the LF is gone)
#   urlsplit("https://auth .example/x").netloc      ==  "auth .example"
#
#  1. an `authorization_url`/`token_url` carrying an embedded \n, \r or \t
#     constructed — the parse hid the control — and was stored and EMITTED
#     unchanged, so the document carried a control character inside
#     `authorizationUrl`/`tokenUrl`;
#  2. a hostname containing a space constructed and was emitted with the space;
#  3. a fragment-bearing endpoint (RFC 6749 §3.1 forbids a fragment on an
#     endpoint URI) was accepted.
#
# The fix validates the WHOLE URI against the RAW string — controls, whitespace
# (padding included), non-ASCII characters, the URI alphabet, the authority's
# host and port grammar, the absence of a fragment — stores the raw string only
# when it passes, and then requires the parse to AGREE with the stored text.
# Every arm below reads the EMITTED value of BOTH
# `flows.authorizationCode.authorizationUrl` and `flows.authorizationCode.tokenUrl`,
# or the named refusal; "construction succeeded" is exactly what the review
# measured to be insufficient.


def test_both_endpoints_are_emitted_unchanged():
    # Arrange — the positive control for both fields at once: a URL that IS a
    # complete RFC 3986 URI reaches the document exactly as declared.
    provider = _oauth(
        authorization_url="https://auth.scitex.example/oauth2/authorize",
        token_url="https://auth.scitex.example/oauth2/token",
    )
    # Act
    flow = _plugin(oauth=provider).openapi_fragment()["components"][
        "securitySchemes"
    ][OAUTH_SECURITY_SCHEME]["flows"][OAUTH2_FLOW]
    # Assert
    assert (flow["authorizationUrl"], flow["tokenUrl"]) == (
        "https://auth.scitex.example/oauth2/authorize",
        "https://auth.scitex.example/oauth2/token",
    )


def test_a_localhost_http_endpoint_is_emitted_unchanged():
    # Arrange — http and an explicit port are accepted forms (a localhost
    # deployment is legitimate), and the emitted value is the declared one.
    provider = _oauth(token_url="http://127.0.0.1:8443/oauth2/token")
    # Act
    flow = _plugin(oauth=provider).openapi_fragment()["components"][
        "securitySchemes"
    ][OAUTH_SECURITY_SCHEME]["flows"][OAUTH2_FLOW]
    # Assert
    assert flow["tokenUrl"] == "http://127.0.0.1:8443/oauth2/token"


def test_a_bracketed_ipv6_endpoint_is_emitted_unchanged():
    # Arrange — the authority grammar's other host form: an IP-literal with a
    # port is emitted with its brackets, not with the parser's hostname.
    provider = _oauth(authorization_url="https://[::1]:8443/oauth2/authorize")
    # Act
    flow = _plugin(oauth=provider).openapi_fragment()["components"][
        "securitySchemes"
    ][OAUTH_SECURITY_SCHEME]["flows"][OAUTH2_FLOW]
    # Assert
    assert flow["authorizationUrl"] == "https://[::1]:8443/oauth2/authorize"


def test_a_case_differing_endpoint_is_emitted_verbatim():
    # Arrange — the RAW string is what is stored: RFC 3986 makes the scheme and
    # the host case-insensitive, so an uppercase declaration is legal and is
    # emitted as declared rather than lowercased into something nobody wrote.
    provider = _oauth(authorization_url="HTTPS://AUTH.Scitex.example/oauth2/authorize")
    # Act
    flow = _plugin(oauth=provider).openapi_fragment()["components"][
        "securitySchemes"
    ][OAUTH_SECURITY_SCHEME]["flows"][OAUTH2_FLOW]
    # Assert
    assert flow["authorizationUrl"] == "HTTPS://AUTH.Scitex.example/oauth2/authorize"


def test_an_embedded_newline_in_the_authorization_url_is_refused():
    # Arrange — blocker 1: urlsplit deleted the LF from its result, so the
    # START of the string was validated while the whole string was emitted.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="control character"):
        _oauth(
            authorization_url="https://auth.scitex.example/oa\nuth",
        )


def test_an_embedded_carriage_return_in_the_token_url_is_refused():
    # Arrange — the same for CR, which is the second half of a header-injection
    # pair once the emitted URL reaches a client.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="control character"):
        _oauth(token_url="https://auth.scitex.example/oauth2/to\rken")


def test_an_embedded_tab_in_the_authorization_url_is_refused():
    # Arrange — a tab is a C0 control urlsplit also deletes silently.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="control character"):
        _oauth(authorization_url="https://auth.scitex.example/oa\tuth")


def test_a_del_character_in_the_token_url_is_refused():
    # Arrange — DEL (0x7f) is the control urlsplit deletes but ord() < 0x20
    # alone would miss.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="control character"):
        _oauth(token_url="https://auth.scitex.example/oauth2/token\x7f")


def test_a_nul_byte_in_the_authorization_url_is_refused():
    # Arrange — a NUL is what a downstream C consumer truncates on, so a string
    # whose tail is invisible has to be refused rather than published.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="control character"):
        _oauth(authorization_url="https://auth.scitex.example/oauth2/authorize\x00")


def test_a_leading_space_in_the_authorization_url_is_refused():
    # Arrange — urlsplit lstrips a space before parsing, so a check written
    # against its result could not see this one either.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="whitespace"):
        _oauth(authorization_url=" https://auth.scitex.example/oauth2/authorize")


def test_a_trailing_space_in_the_token_url_is_refused():
    # Arrange — the same at the other end of the string.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="whitespace"):
        _oauth(token_url="https://auth.scitex.example/oauth2/token ")


def test_an_interior_space_in_the_authorization_url_is_refused():
    # Arrange — the case no strip and no lstrip can reach.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="whitespace"):
        _oauth(authorization_url="https://auth.scitex.example/oauth2/auth orize")


def test_a_space_inside_the_hostname_is_refused():
    # Arrange — blocker 2: the space stayed in `netloc` (urlsplit only removes
    # the padding around the whole string), so the host was emitted as
    # "auth .example" — a hostname no client can resolve.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="whitespace"):
        _oauth(authorization_url="https://auth .scitex.example/oauth2/authorize")


def test_a_fragment_in_the_authorization_url_is_refused():
    # Arrange — blocker 3: RFC 6749 §3.1 forbids a fragment on an endpoint URI,
    # and one would have a client call an address the server never described.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="fragment"):
        _oauth(
            authorization_url="https://auth.scitex.example/oauth2/authorize#grant",
        )


def test_a_fragment_in_the_token_url_is_refused():
    # Arrange — the same rule for the endpoint that issues the token.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="fragment"):
        _oauth(token_url="https://auth.scitex.example/oauth2/token#frag")


def test_a_host_character_outside_the_uri_alphabet_is_refused():
    # Arrange — a character no URI may carry anywhere; urlsplit keeps it in
    # `netloc`, so the authority has to be checked against RFC 3986 rather than
    # merely for being non-empty.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="nowhere in a URI"):
        _oauth(authorization_url="https://auth|scitex.example/oauth2/authorize")


def test_an_authority_naming_no_host_is_refused():
    # Arrange — a port with no host in front of it ('https://:8443/...') has a
    # non-empty authority, so only the host grammar itself refuses it.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="reg-name"):
        _oauth(token_url="https://:8443/oauth2/token")


def test_a_non_numeric_port_is_refused():
    # Arrange — a port the parser keeps and no client can dial.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="port"):
        _oauth(token_url="https://auth.scitex.example:oauth/oauth2/token")


def test_a_userinfo_credential_in_the_authorization_url_is_refused():
    # Arrange — the URL is PUBLISHED inside the generated document, so a
    # credential embedded in it is a leak, not an authentication.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="userinfo"):
        _oauth(
            authorization_url="https://client:secret@auth.scitex.example/oauth2/authorize",
        )


def test_a_non_ascii_character_in_the_token_url_is_refused():
    # Arrange — RFC 3986 URIs are ASCII, so an internationalised endpoint has
    # to be declared percent-encoded (or in punycode) to be callable.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="non-ASCII"):
        _oauth(token_url="https://auth.scitex.example/oauth2/tokén")


def test_a_pct_encoded_control_in_the_authorization_url_is_refused():
    # Arrange — a character refused RAW is refused encoded: %0a is the same
    # CR/LF pair as a literal one once a client's parser decodes it.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="pct-encodes"):
        _oauth(authorization_url="https://auth.scitex.example/oauth2/autho%0arize")


def test_a_bare_percent_in_the_token_url_is_refused():
    # Arrange — a '%' that begins no octet leaves the URI's escaping undefined.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="pct-encoded"):
        _oauth(token_url="https://auth.scitex.example/oauth2/tok%zen")


def test_a_bracket_outside_the_authority_is_refused():
    # Arrange — brackets delimit the authority's IP-literal and mean nothing in
    # a path, so one there is not the URI the declaration reads as.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="outside its authority"):
        _oauth(authorization_url="https://auth.scitex.example/[x]/authorize")


def test_a_blank_authorization_url_is_refused():
    # Arrange — whitespace-only is refused before any of the above: an endpoint
    # that is blank is indistinguishable from an undeclared one.
    # Act
    # Assert
    with pytest.raises(ApiPluginContractError, match="non-blank string"):
        _oauth(authorization_url="   ")


def test_the_validator_accepts_a_malformed_flow_url():
    # Arrange — pins WHY the refusal has to live in the descriptor: measured
    # with openapi-spec-validator 0.9.0, a flow URL carrying a control
    # character validates, so nothing downstream of the declaration would have
    # caught the defect this assignment closes (the document is built from a
    # valid declaration and then malformed by hand, exactly as the raw URL used
    # to be emitted).
    validate = pytest.importorskip("openapi_spec_validator").validate
    document = _validated_document(_plugin())
    flow = document["components"]["securitySchemes"][OAUTH_SECURITY_SCHEME]["flows"][
        OAUTH2_FLOW
    ]
    flow["tokenUrl"] = "https://auth.scitex.example/oauth2/token\n"
    # Act
    result = validate(document)
    # Assert
    assert result is None


# ─── fifth review: percent-triplet HEX CASE must not decide validity ───────
# A reg-name host may carry percent triplets, and RFC 3986 §2.1 makes their hex
# digits case-insensitive — but urlsplit preserves the case it was handed while
# the module lowercases the raw host for its grammar check, so
# `https://%41BC.example/…` was refused as "does not round-trip". These arms pin
# both directions: the URL is ACCEPTED and it is EMITTED VERBATIM (the raw
# declared string, not a lowercased hex form).

_UP_HEX_AUTH = "https://%41BC.example/oauth2/authorize"
_UP_HEX_TOKEN = "https://%41BC.example/oauth2/token"


def _up_hex_provider() -> OAuthProvider:
    """A provider whose reg-name host carries an UPPERCASE-hex triplet."""
    return OAuthProvider(
        authorization_url=_UP_HEX_AUTH,
        token_url=_UP_HEX_TOKEN,
        scopes={"recipes:write": "write"},
    )


def _up_hex_flow() -> dict:
    """The emitted authorizationCode flow of that provider."""
    plugin = ApiPlugin(
        id="figrecipe",
        title="FigRecipe",
        api_version="1",
        oauth=_up_hex_provider(),
        routes=[
            ApiRoute(
                path="recipes/save",
                methods=["GET"],
                handler="figrecipe.api:save_recipe",
                auth=AuthScope(scopes=["recipes:write"]),
                rate=RateLimit("interactive", "light"),
            )
        ],
    )
    schemes = plugin.openapi_fragment()["components"]["securitySchemes"]
    return schemes["scitexOAuth"]["flows"]["authorizationCode"]


def test_an_uppercase_hex_triplet_in_the_authorization_host_is_accepted():
    # Arrange — the fifth-review blocker: this used to be refused.
    # Act
    provider = _up_hex_provider()
    # Assert — construction succeeds and the RAW string is what is stored.
    assert provider.authorization_url == _UP_HEX_AUTH


def test_the_uppercase_hex_authorization_url_is_emitted_verbatim():
    # Arrange — emitted, not merely accepted (checking construction was the
    # gap in the round-four verification).
    # Act
    flow = _up_hex_flow()
    # Assert — the declared case survives into the document.
    assert flow["authorizationUrl"] == _UP_HEX_AUTH


def test_an_uppercase_hex_triplet_in_the_token_host_is_accepted():
    # Arrange
    # Act
    provider = _up_hex_provider()
    # Assert
    assert provider.token_url == _UP_HEX_TOKEN


def test_the_uppercase_hex_token_url_is_emitted_verbatim():
    # Arrange — the reviewer required regressions for token_url as well as
    # authorization_url.
    # Act
    flow = _up_hex_flow()
    # Assert
    assert flow["tokenUrl"] == _UP_HEX_TOKEN


def test_the_emitted_hex_url_still_validates_as_openapi():
    # Arrange — acceptance must not buy correctness: the document has to stand.
    validate = pytest.importorskip("openapi_spec_validator").validate
    document = {
        "openapi": "3.1.0",
        "info": {"title": "FigRecipe", "version": "1"},
        **_up_hex_flow_document(),
    }
    # Act
    result = validate(document)
    # Assert
    assert result is None


def _up_hex_flow_document() -> dict:
    """The fragment of the uppercase-hex provider's plugin."""
    plugin = ApiPlugin(
        id="figrecipe",
        title="FigRecipe",
        api_version="1",
        oauth=_up_hex_provider(),
        routes=[
            ApiRoute(
                path="recipes/save",
                methods=["GET"],
                handler="figrecipe.api:save_recipe",
                auth=AuthScope(scopes=["recipes:write"]),
                rate=RateLimit("interactive", "light"),
            )
        ],
    )
    return plugin.openapi_fragment()


def test_a_lowercase_hex_triplet_host_is_still_accepted():
    # Arrange — the control: folding hex case must not START refusing the form
    # that already worked.
    # Act
    provider = OAuthProvider(
        authorization_url="https://%41bc.example/oauth2/authorize",
        token_url="https://%41bc.example/oauth2/token",
        scopes={"recipes:write": "write"},
    )
    # Assert
    assert provider.authorization_url == "https://%41bc.example/oauth2/authorize"


# EOF
