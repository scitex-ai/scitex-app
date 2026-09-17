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
    OAUTH_SECURITY_SCHEME,
    RECOMMENDED_COMPUTE_COSTS,
    RECOMMENDED_RATE_CLASSES,
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
    assert scheme["scheme"] == "bearer"


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
    # Arrange
    # Act
    fragment = _plugin().openapi_fragment()
    # Assert
    assert fragment["paths"]["/recipes/save"]["get"]["operationId"] == (
        "figrecipe.get.recipes_save"
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


# EOF
