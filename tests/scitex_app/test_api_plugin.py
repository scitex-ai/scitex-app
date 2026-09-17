#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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


def _route(**overrides) -> ApiRoute:
    base = {
        "path": "recipes/save",
        "methods": ["GET"],
        "handler": "figrecipe.api:save_recipe",
        "auth": _auth(),
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


def test_a_placeholder_segment_is_accepted():
    # Arrange
    # Act
    path = _route(path="call/{call_id}").path
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
    # Arrange
    # Act
    fragment = _plugin().openapi_fragment()
    # Assert
    assert list(fragment["paths"]) == ["recipes/save"]


def test_the_fragment_lowercases_the_operation_key():
    # Arrange
    # Act
    fragment = _plugin().openapi_fragment()
    # Assert
    assert list(fragment["paths"]["recipes/save"]) == ["get"]


def test_the_fragment_carries_the_idempotency_header_extension():
    # Arrange
    routes = [_route(methods=["POST"], idempotency=Idempotency(required=True))]
    # Act
    fragment = _plugin(routes=routes).openapi_fragment()
    # Assert
    assert fragment["paths"]["recipes/save"]["post"]["x-scitex-idempotency-key-header"] == "Idempotency-Key"


def test_the_fragment_carries_the_compute_cost_declaration():
    # Arrange
    routes = [_route(rate=RateLimit(rate_class="interactive", compute_cost="render"))]
    # Act
    fragment = _plugin(routes=routes).openapi_fragment()
    # Assert
    assert fragment["paths"]["recipes/save"]["get"]["x-scitex-compute-cost"] == "render"


def test_the_fragment_marks_a_deprecation_with_its_sunset():
    # Arrange
    routes = [_route(deprecation=Deprecation(sunset_version="2"))]
    # Act
    fragment = _plugin(routes=routes).openapi_fragment()
    # Assert
    assert fragment["paths"]["recipes/save"]["get"]["x-scitex-sunset-version"] == "2"


def test_the_fragment_marks_a_public_route_as_unsecured():
    # Arrange
    routes = [_route(auth=AuthScope(public=True, project_scope="none"))]
    # Act
    fragment = _plugin(routes=routes).openapi_fragment()
    # Assert
    assert fragment["paths"]["recipes/save"]["get"]["security"] == []


def test_the_fragment_reports_scoped_routes_with_their_oauth_scopes():
    # Arrange
    # Act
    fragment = _plugin().openapi_fragment()
    # Assert
    assert fragment["paths"]["recipes/save"]["get"]["x-scitex-oauth-scopes"] == ["recipes:write"]


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
    ref = fragment["paths"]["recipes/save"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    assert ref == "#/components/schemas/RecipeState"


def test_the_fragment_uses_the_streaming_media_type_for_sse():
    # Arrange
    routes = [_route(transport="sse", response=_schema(name="ChatChunk"), idempotency=Idempotency(required=True))]
    # Act
    fragment = _plugin(routes=routes).openapi_fragment()
    # Assert
    content = fragment["paths"]["recipes/save"]["get"]["responses"]["200"]["content"]
    assert list(content) == ["text/event-stream"]


def test_the_fragment_uses_the_binary_media_type_for_a_download():
    # Arrange
    routes = [_route(transport="binary", response=_schema(name="Download"))]
    # Act
    fragment = _plugin(routes=routes).openapi_fragment()
    # Assert
    content = fragment["paths"]["recipes/save"]["get"]["responses"]["200"]["content"]
    assert list(content) == ["application/octet-stream"]


def test_the_fragment_reports_declared_errors_with_their_retryability():
    # Arrange
    errors = [ApiError(code="no_recipe", status=400, message="no recipe loaded", retryable=False)]
    # Act
    fragment = _plugin(routes=[_route(errors=errors)]).openapi_fragment()
    # Assert
    entry = fragment["paths"]["recipes/save"]["get"]["responses"]["default"]["x-scitex-errors"][0]
    assert entry["retryable"] is False


def test_the_fragment_carries_the_pagination_bounds():
    # Arrange
    routes = [_route(pagination=Pagination(style="offset", default_limit=20, max_limit=100))]
    # Act
    fragment = _plugin(routes=routes).openapi_fragment()
    # Assert
    pagination = fragment["paths"]["recipes/save"]["get"]["x-scitex-pagination"]
    assert pagination["max_limit"] == 100


def test_the_fragment_names_the_handler_for_the_composer():
    # Arrange
    # Act
    fragment = _plugin().openapi_fragment()
    # Assert
    assert fragment["paths"]["recipes/save"]["get"]["x-scitex-handler"] == "figrecipe.api:save_recipe"


def test_every_declared_route_appears_in_the_fragment():
    # Arrange
    routes = [_route(path="recipes/save"), _route(path="recipes/export", handler="figrecipe.api:export")]
    # Act
    fragment = _plugin(routes=routes).openapi_fragment()
    # Assert
    assert sorted(fragment["paths"]) == ["recipes/export", "recipes/save"]


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


def test_discovery_keeps_the_first_entry_point_for_a_name():
    # Arrange
    entry_points = [_ep("figrecipe", "figrecipe.api:P"), _ep("figrecipe", "other.api:P")]
    # Act
    target = discover_api_plugins(entry_points)[0].target
    # Assert
    assert target == "figrecipe.api:P"


def test_discovery_reports_the_distribution_when_there_is_one():
    # Arrange — a REAL installed entry point (from console_scripts, which
    # carries a distribution); EntryPoint is immutable in 3.12, so the dist
    # cannot be attached to a hand-made one.
    from importlib.metadata import entry_points

    real = list(entry_points(group="console_scripts"))[0]
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


# EOF
