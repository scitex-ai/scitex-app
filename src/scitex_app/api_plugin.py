#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The leaf API-plugin contract: what an approved leaf DECLARES about its API.

A leaf app (FigRecipe, Writer, Scholar, ...) owns the behaviour of its own
endpoints. What it does not own is the SHAPE a client may rely on: the routes,
the request/response/error schemas, the auth scope, the idempotency promise,
the pagination style, the rate/quota class, the audit level, the API version
and the deprecation window. Those cross a package boundary — browser, agent,
and thin native clients all read them — so they are DECLARED here as data and
checked at construction, not discovered by reading an implementation.

WHY A DECLARATION RATHER THAN THE IMPLEMENTATION. The operator's model
(2026-09-16): the public SDK lets clients be built against approved APIs, while
server-side leaf endpoint plugins are a HIGHER-TRUST class requiring SciTeX
approval. A contract that must be approved is a contract that must be readable
without executing the leaf: everything below is plain data, importable and
comparable, and the handler is named as a string, never imported here.

WHAT IS DELIBERATELY ABSENT. No Hub ORM, no middleware, no root-route
registration, no raw shell/path/argv, and no framework object: a route path is
a RELATIVE declaration that is validated (see :func:`_validate_path`) so it
cannot escape its mount, and the handler reference is an entry-point-style
``module:attr`` string. Nothing in this module serves a request — the host
composes routes; this layer says what may be composed.

FAIL CLOSED. Every rule below refuses at construction, because each one would
otherwise present as a working API: an undeclared auth scope opens an endpoint,
a mutating method with no idempotency declaration double-creates on retry, an
unstructured error leaves a client nothing to branch on, and a deprecation with
no sunset never arrives. Strictness is the feature; the alternative is a client
that ships against a promise nobody made.

ZERO THIRD-PARTY DEPENDENCIES. scitex-app's base install is stdlib plus
click/rich/scitex-config, and this module must stay importable from the CLI, the
MCP surface and a test process alike. The descriptors are therefore frozen
stdlib dataclasses, NOT pydantic models: the declaration layer is data, and
validation of a live REQUEST is the serving host's job. Flagged as a decision
for the card's owner — see the note in :data:`DESCRIPTOR_IMPLEMENTATION`.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Optional
from typing import Sequence

#: How the descriptors are implemented, stated where a reader will look. The
#: alternative (pydantic v2 models) would add a hard dependency to a package
#: whose base install is stdlib-only, so it is a published-install-surface
#: change and therefore the card owner's ruling rather than a silent choice.
DESCRIPTOR_IMPLEMENTATION = "stdlib-frozen-dataclasses"

#: The entry-point group a leaf publishes its API plugin under. Parallel to the
#: ``scitex.apps`` group in :mod:`scitex_app.plugins`: the value is read as a
#: STRING (nothing is imported until the host deliberately loads it), which is
#: what makes an installed package "trusted" rather than "arbitrary code".
API_ENTRY_POINT_GROUP = "scitex.apis"

#: HTTP methods a route may declare — the closed set the approval surface can
#: reason about. Anything else (a custom verb, a bare ``*``) is refused.
HTTP_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")

#: Methods that CHANGE state. A route using one of these must declare its
#: idempotency behaviour: a retried POST with no declared key is the
#: double-create the operator called out.
MUTATING_METHODS = ("POST", "PUT", "PATCH", "DELETE")

#: How a route answers. ``sse`` and ``binary`` are first-class because leaves
#: genuinely have them (measured on FigRecipe: a streaming chat endpoint and
#: ``download/{fmt}``) — a contract that only models JSON would make those
#: endpoints undescribable, which is how they end up undocumented.
TRANSPORTS = ("json", "sse", "binary")

#: JSON Schema's primitive type names. Borrowed rather than invented so the
#: generated OpenAPI fragment needs no translation table.
FIELD_TYPES = ("string", "integer", "number", "boolean", "object", "array")

#: Who a route's data belongs to. ``user`` and ``project`` reuse the vocabulary
#: already fixed by :mod:`scitex_app._app_scope`; ``none`` means the response is
#: not scoped to an actor at all (a public listing).
PROJECT_SCOPES = ("none", "user", "project")

#: Whether and how much of a call is recorded. The minimal honest vocabulary:
#: an endpoint either is not audited, records that a call happened, or records
#: the call and its actor-visible arguments.
AUDIT_LEVELS = ("none", "metadata", "full")

#: Pagination styles a route may declare.
PAGINATION_STYLES = ("none", "offset", "cursor")

#: Default header a client sends its idempotency key in.
IDEMPOTENCY_KEY_HEADER = "Idempotency-Key"

#: The security scheme every scoped operation's requirement names, and the
#: component the fragment declares it as. OAuth/OIDC issues the bearer token, so
#: the scheme is a bearer one — a generic consumer that has never heard of SciTeX
#: still reads the requirement and sends the token — and a route's OAuth scopes
#: ride as the requirement's value.
OAUTH_SECURITY_SCHEME = "scitexOAuth"

#: RECOMMENDED rate/quota classes — examples for the approved deployments, NOT
#: a closed enum. The hub ruled (2026-09-17) that a leaf may declare its own
#: extensible class, so these are documentation constants: a third-party plugin
#: is not refused for naming a class this module has never heard of, and the
#: approval surface compares against the deployment's own list.
RECOMMENDED_RATE_CLASSES = ("interactive", "standard", "bulk")

#: RECOMMENDED compute-cost declarations, same standing as the rate classes:
#: examples that make a declaration readable, quoted by the docs, not enforced.
RECOMMENDED_COMPUTE_COSTS = ("light", "standard", "heavy")

_METHOD_RE = re.compile(r"^[A-Z]+$")
_VERSION_RE = re.compile(r"^\d+(\.\d+)*$")
_HANDLER_RE = re.compile(r"^[A-Za-z_][\w.]*:[A-Za-z_][\w.]*$")
_PATH_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")
_PLACEHOLDER_RE = re.compile(r"^\{[A-Za-z_][\w]*\}$")

#: RFC 7230 ``tchar`` — the ONLY characters an HTTP field name may contain.
#: A header name carrying CR, LF or any other control character lets a
#: declaration smuggle a second header past whatever client writes it, so the
#: whole token alphabet is enforced rather than only the obvious few.
_HTTP_TOKEN_RE = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")

#: Characters that must never appear in a declared path. A path is a
#: DECLARATION that a host will compose into a real route, so anything that
#: could escape the mount, reach a shell, or smuggle a scheme is refused here
#: rather than trusted downstream ("no raw shell/path/argv").
_FORBIDDEN_PATH_CHARS = ("..", "//", "\\", " ", "\t", "\n", "?", "#", "%")


class ApiPluginContractError(ValueError):
    """A leaf's API declaration is malformed.

    Raised at construction: every condition this catches would otherwise ship an
    endpoint whose promise differs from what a client was told.
    """


def _require_text(value: object, what: str) -> str:
    """Return ``value`` stripped, or raise when it is not non-blank text."""
    if not isinstance(value, str) or not value.strip():
        raise ApiPluginContractError(
            f"{what} must be a non-blank string (got {value!r}); an empty "
            f"{what} is indistinguishable from an undeclared one"
        )
    return value.strip()


def _require_choice(value: object, choices: Sequence[str], what: str) -> str:
    """Return ``value`` if it is one of ``choices``, else raise."""
    if value not in choices:
        raise ApiPluginContractError(
            f"{what} must be one of {tuple(choices)} (got {value!r}); a value "
            "outside the closed set cannot be rendered or enforced"
        )
    return str(value)


def _require_token(value: object, what: str) -> str:
    """Return ``value`` if it is a valid HTTP field-name token, else raise.

    Refuses CR, LF, every other control character, spaces and ``:`` by refusing
    any character outside RFC 7230 ``tchar``. Whitespace-only already fails the
    blank check; this is the injection case, where a "header name" is really a
    header name plus a second header.
    """
    text = _require_text(value, what)
    if not _HTTP_TOKEN_RE.match(text):
        raise ApiPluginContractError(
            f"{what} {value!r} is not a valid HTTP field name; it must be one "
            "or more RFC 7230 tchar and must not contain CR, LF or any other "
            "control character (a name that can carry one can smuggle a second "
            "header), nor a space or ':'"
        )
    return text


def _require_elements(value: object, element_type: type, what: str) -> tuple:
    """Return ``value`` as a tuple whose every element IS an ``element_type``.

    Strict on purpose, and strict by ``isinstance`` rather than by shape. A
    duck-typed stand-in (a dict that happens to carry ``name``/``type``, an
    ``int`` where a descriptor was meant, a bare string where a list was meant)
    would otherwise be accepted here and blow up later as an AttributeError
    three frames into a renderer — naming nothing the leaf can fix. The refusal
    below names the ELEMENT and its position, so the declaration site is
    obvious from the message alone.
    """
    if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
        raise ApiPluginContractError(
            f"{what} must be a sequence of {element_type.__name__} (got "
            f"{value!r}); a single value where a sequence was declared is "
            "refused rather than iterated element by element"
        )
    items = tuple(value)
    for index, item in enumerate(items):
        if not isinstance(item, element_type):
            raise ApiPluginContractError(
                f"{what} element {index} is {item!r}, a "
                f"{type(item).__name__}; expected an instance of "
                f"{element_type.__name__} — a value that merely looks like one "
                "is not one"
            )
    return items


def _require_version(value: object, what: str) -> str:
    """Return a dotted version string, or raise."""
    text = _require_text(value, what)
    if not _VERSION_RE.match(text):
        raise ApiPluginContractError(
            f"{what} must be a dotted version such as '1' or '1.2' (got "
            f"{value!r}); a non-numeric version cannot be ordered against a "
            "sunset or a client's supported range"
        )
    return text


def _validate_path(path: object) -> str:
    """A route path declaration: relative, no traversal, no shell surface.

    Refused: a leading ``/`` (the host owns the mount prefix — a route that
    names an absolute path is claiming the root, which is exactly the "no root
    route registration" rule), ``..``, ``//``, backslashes, whitespace, query or
    fragment characters, percent-encoding, and any segment that is neither a
    plain name nor a ``{placeholder}``.
    """
    text = _require_text(path, "route path")
    if text.startswith("/"):
        raise ApiPluginContractError(
            f"route path {text!r} is absolute; declare it RELATIVE to the app "
            "(the host owns the mount prefix, and a leaf claiming a root route "
            "is the root-registration this contract forbids)"
        )
    for bad in _FORBIDDEN_PATH_CHARS:
        if bad in text:
            raise ApiPluginContractError(
                f"route path {text!r} contains {bad!r}; a declared path must "
                "not be able to encode traversal, a query, a fragment or a "
                "shell token"
            )
    if text.endswith("/"):
        raise ApiPluginContractError(
            f"route path {text!r} is not in NORMALIZED form: it ends in '/', so "
            f"two declarations of one endpoint would differ by a single "
            f"character and collide only downstream. Declare "
            f"{text.rstrip('/')!r} instead."
        )
    for segment in text.split("/"):
        if _PATH_SEGMENT_RE.match(segment) or _PLACEHOLDER_RE.match(segment):
            continue
        raise ApiPluginContractError(
            f"route path {text!r} has segment {segment!r}; expected a plain "
            "name or a {placeholder}"
        )
    return text


@dataclass(frozen=True)
class ApiField:
    """One declared field of a request or response body."""

    name: str
    type: str = "string"
    required: bool = True
    description: str = ""
    enum: Sequence[str] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _require_text(self.name, "field name")
        _require_choice(self.type, FIELD_TYPES, "field type")
        if not isinstance(self.required, bool):
            raise ApiPluginContractError(
                f"field {self.name!r} has a non-boolean required flag "
                f"({self.required!r})"
            )
        object.__setattr__(self, "enum", _require_elements(
            self.enum, str, f"enum of field {self.name!r}"
        ))
        for member in self.enum:
            _require_text(member, f"enum member of field {self.name!r}")


@dataclass(frozen=True)
class ApiSchema:
    """A named body schema: strict, and never empty.

    An empty schema is refused because it is ambiguous — "takes nothing" and
    "nobody wrote it down" read the same to a client generator.
    """

    name: str
    fields: Sequence[ApiField] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _require_text(self.name, "schema name")
        object.__setattr__(self, "fields", _require_elements(
            self.fields, ApiField, f"fields of schema {self.name!r}"
        ))
        if not self.fields:
            raise ApiPluginContractError(
                f"schema {self.name!r} declares no fields; an empty schema "
                "cannot be told apart from an undocumented body"
            )
        seen: list[str] = []
        for item in self.fields:
            if item.name in seen:
                raise ApiPluginContractError(
                    f"schema {self.name!r} declares field {item.name!r} twice"
                )
            seen.append(item.name)


@dataclass(frozen=True)
class ApiError:
    """One structured error a route may return.

    Structured on purpose: a bare ``{error: str}`` gives a client nothing to
    branch on, and leaves retry-vs-dont-retry to string matching (measured on
    FigRecipe's endpoints today).
    """

    code: str
    status: int
    message: str
    retryable: bool = False

    def __post_init__(self) -> None:
        _require_text(self.code, "error code")
        _require_text(self.message, "error message")
        if not isinstance(self.status, int) or isinstance(self.status, bool):
            raise ApiPluginContractError(
                f"error {self.code!r} has a non-integer status ({self.status!r})"
            )
        if not 400 <= self.status <= 599:
            raise ApiPluginContractError(
                f"error {self.code!r} declares status {self.status}; an error a "
                "client sees must be a 4xx or 5xx"
            )
        if not isinstance(self.retryable, bool):
            raise ApiPluginContractError(
                f"error {self.code!r} has a non-boolean retryable flag "
                f"({self.retryable!r}); a client cannot act on an ambiguous one"
            )


@dataclass(frozen=True)
class AuthScope:
    """What a caller must present, and whose data the route touches.

    ``scopes`` are OAuth/OIDC scope strings. A route with NO scope is refused
    unless it says so explicitly with ``public=True``: forgetting to declare a
    scope must not silently open an endpoint, which is the fail-closed rule this
    whole contract rests on. ``public=True`` in turn REQUIRES
    ``project_scope="none"``: a public route is not user- or project-scoped, and
    a public declaration that claims to be would tell a client that a listing is
    filtered by an actor when it is not. Native clients authenticate with
    authorization-code + PKCE against these scopes — the contract never carries
    a client secret, because nothing here can hold one.
    """

    project_scope: str = "user"
    scopes: Sequence[str] = field(default_factory=tuple)
    public: bool = False

    def __post_init__(self) -> None:
        _require_choice(self.project_scope, PROJECT_SCOPES, "auth project_scope")
        object.__setattr__(self, "scopes", _require_elements(
            self.scopes, str, "auth scopes"
        ))
        for scope in self.scopes:
            _require_text(scope, "auth scope")
        if not isinstance(self.public, bool):
            raise ApiPluginContractError(
                f"auth public flag must be a boolean (got {self.public!r})"
            )
        if not self.public and not self.scopes:
            raise ApiPluginContractError(
                "an auth scope declares neither scopes nor public=True; a route "
                "whose auth was never stated must not be treated as open. "
                "Declare the OAuth scopes it needs, or say public=True out loud."
            )
        if self.public and self.scopes:
            raise ApiPluginContractError(
                f"auth declares public=True together with scopes "
                f"{tuple(self.scopes)}; exactly one of the two describes it"
            )
        if self.public and self.project_scope != "none":
            raise ApiPluginContractError(
                f"auth declares public=True with project_scope="
                f"{self.project_scope!r}; a public route is not scoped to an "
                "actor or a project at all, so declare project_scope='none' — "
                "anything else advertises a listing as filtered when it is not"
            )


@dataclass(frozen=True)
class Idempotency:
    """The route's retry promise.

    ``required=True`` means the caller MUST send a key (default header
    :data:`IDEMPOTENCY_KEY_HEADER`) and the endpoint guarantees no second
    effect for a replayed key. ``key_header`` must be a valid HTTP field name:
    a name carrying CR, LF or any other control character would let the
    declaration smuggle a second header into the request the client writes.
    """

    required: bool = False
    key_header: str = IDEMPOTENCY_KEY_HEADER

    def __post_init__(self) -> None:
        if not isinstance(self.required, bool):
            raise ApiPluginContractError(
                f"idempotency required flag must be a boolean (got {self.required!r})"
            )
        object.__setattr__(
            self,
            "key_header",
            _require_token(self.key_header, "idempotency key header"),
        )


@dataclass(frozen=True)
class Pagination:
    """The route's list-envelope promise."""

    style: str = "none"
    default_limit: Optional[int] = None
    max_limit: Optional[int] = None

    def __post_init__(self) -> None:
        _require_choice(self.style, PAGINATION_STYLES, "pagination style")
        for label, value in (("default_limit", self.default_limit), ("max_limit", self.max_limit)):
            if value is None:
                continue
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ApiPluginContractError(
                    f"pagination {label} must be a positive integer (got {value!r})"
                )
        if self.style == "none":
            if self.default_limit is not None or self.max_limit is not None:
                raise ApiPluginContractError(
                    "pagination declares limits with style='none'; the route "
                    "would advertise a page size it does not implement"
                )
            return
        if self.default_limit is None or self.max_limit is None:
            raise ApiPluginContractError(
                f"pagination style {self.style!r} needs BOTH default_limit and "
                "max_limit; an unbounded page size is what makes a list "
                "endpoint unbounded for the client that builds against it"
            )
        if self.default_limit > self.max_limit:
            raise ApiPluginContractError(
                f"pagination default_limit {self.default_limit} exceeds "
                f"max_limit {self.max_limit}"
            )


@dataclass(frozen=True)
class RateLimit:
    """The route's rate/quota class and its declared compute cost.

    Both are REQUIRED and non-blank, and whitespace-only is refused — but the
    vocabulary is EXTENSIBLE rather than closed, per the hub's ruling
    (2026-09-17): a third-party plugin must not be rejected for naming a class
    this module has never heard of, so the approval surface compares a
    declaration against the DEPLOYMENT's own approved list.
    :data:`RECOMMENDED_RATE_CLASSES` and :data:`RECOMMENDED_COMPUTE_COSTS` are
    the documented examples a leaf should reach for first, and the ones the
    generated OpenAPI fragment's ``x-scitex-rate-class`` /
    ``x-scitex-compute-cost`` extensions will carry.
    """

    rate_class: str
    compute_cost: str
    quota_note: str = ""

    def __post_init__(self) -> None:
        _require_text(self.rate_class, "rate_class")
        _require_text(self.compute_cost, "compute_cost")


@dataclass(frozen=True)
class Audit:
    """Whether a call is recorded, and how much of it."""

    level: str = "metadata"

    def __post_init__(self) -> None:
        _require_choice(self.level, AUDIT_LEVELS, "audit level")


@dataclass(frozen=True)
class Deprecation:
    """The route's version window: when it goes, and what replaces it.

    A deprecation with a sunset but no replacement is allowed (an endpoint can
    simply end); a deprecation with no sunset is refused, because it is the
    announcement that never arrives at the client.
    """

    sunset_version: str
    replacement: Optional[str] = None

    def __post_init__(self) -> None:
        _require_version(self.sunset_version, "deprecation sunset_version")
        if self.replacement is not None:
            _require_text(self.replacement, "deprecation replacement")


@dataclass(frozen=True)
class ApiRoute:
    """One declared endpoint: what it takes, returns, needs and promises.

    ``rate`` is REQUIRED and has no default on purpose. An omitted rate class
    would be filled in by whoever reads the missing value — the deployment's
    most permissive bucket, or its most expensive one — and the leaf would never
    have agreed to it. Every route states its own class and compute cost.
    """

    path: str
    methods: Sequence[str]
    rate: RateLimit
    path_params: Sequence[str] = field(default_factory=tuple)
    request: Optional[ApiSchema] = None
    response: Optional[ApiSchema] = None
    errors: Sequence[ApiError] = field(default_factory=tuple)
    auth: AuthScope = field(default_factory=AuthScope)
    idempotency: Idempotency = field(default_factory=Idempotency)
    pagination: Pagination = field(default_factory=Pagination)
    audit: Audit = field(default_factory=Audit)
    transport: str = "json"
    handler: str = ""
    deprecation: Optional[Deprecation] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", _validate_path(self.path))
        if not isinstance(self.rate, RateLimit):
            raise ApiPluginContractError(
                f"route {self.path!r} declares rate {self.rate!r}, a "
                f"{type(self.rate).__name__}; expected a RateLimit"
            )
        object.__setattr__(self, "path_params", _require_elements(
            self.path_params, str, f"path_params of route {self.path!r}"
        ))
        methods = _require_elements(
            self.methods, str, f"methods of route {self.path!r}"
        )
        if not methods:
            raise ApiPluginContractError(
                f"route {self.path!r} declares no methods"
            )
        for method in methods:
            if not _METHOD_RE.match(method):
                raise ApiPluginContractError(
                    f"route {self.path!r} declares method {method!r}; expected "
                    f"an uppercase HTTP method from {HTTP_METHODS}"
                )
            _require_choice(method, HTTP_METHODS, f"method of route {self.path!r}")
        if len(set(methods)) != len(methods):
            raise ApiPluginContractError(
                f"route {self.path!r} declares a method twice"
            )
        object.__setattr__(self, "methods", methods)
        _require_choice(self.transport, TRANSPORTS, f"transport of route {self.path!r}")
        for slot, schema in (("request", self.request), ("response", self.response)):
            if schema is not None and not isinstance(schema, ApiSchema):
                raise ApiPluginContractError(
                    f"{slot} of route {self.path!r} is {schema!r}, a "
                    f"{type(schema).__name__}; expected an ApiSchema or None"
                )
        object.__setattr__(self, "errors", _require_elements(
            self.errors, ApiError, f"errors of route {self.path!r}"
        ))
        _require_text(self.handler, f"handler of route {self.path!r}")
        if not _HANDLER_RE.match(self.handler):
            raise ApiPluginContractError(
                f"route {self.path!r} declares handler {self.handler!r}; expected "
                "an entry-point-style 'module.path:attr' — a declaration, never "
                "a shell command, a filesystem path or argv"
            )
        self._refuse_undeclared_mutation()
        self._refuse_duplicate_errors()
        self._refuse_undeclared_path_params()

    def _refuse_undeclared_path_params(self) -> None:
        """The declared ``path_params`` and the path's ``{placeholders}`` match.

        A ``{param}`` nobody declared is a parameter no client can supply and no
        generator can name; a declaration with no ``{param}`` behind it is a
        parameter the route claims to take and can never receive. Refusing both
        keeps the fragment's ``parameters`` list exactly equal to the path
        template the host will serve.
        """
        declared = list(self.path_params)
        for name in declared:
            _require_text(name, f"path parameter of route {self.path!r}")
        if len(set(declared)) != len(declared):
            raise ApiPluginContractError(
                f"route {self.path!r} declares a path parameter twice; one "
                "parameter cannot be described two ways"
            )
        in_path = _path_placeholders(self.path)
        missing = [name for name in in_path if name not in declared]
        if missing:
            raise ApiPluginContractError(
                f"route {self.path!r} uses placeholder(s) {tuple(missing)} that "
                "are not declared in path_params; an undeclared path parameter "
                "reaches a client as an argument it was never told to send"
            )
        extra = [name for name in declared if name not in in_path]
        if extra:
            raise ApiPluginContractError(
                f"route {self.path!r} declares path_params {tuple(extra)} that "
                "do not appear as {placeholder} segments in its path; the route "
                "would promise a parameter it can never receive"
            )

    def _refuse_undeclared_mutation(self) -> None:
        """A mutating route must state its idempotency behaviour.

        Silence here is the expensive kind: a retried POST creates a second
        object, and the client had no way to know it was unsafe.
        """
        mutating = [m for m in self.methods if m in MUTATING_METHODS]
        if mutating and not self.idempotency.required:
            raise ApiPluginContractError(
                f"route {self.path!r} accepts {tuple(mutating)} but declares no "
                "required idempotency key; a retried mutating call would act "
                "twice. Declare Idempotency(required=True) and honour the key, "
                "or drop the mutating method."
            )

    def _refuse_duplicate_errors(self) -> None:
        """Two errors with one code cannot be told apart by a client."""
        seen: list[str] = []
        for error in self.errors:
            if error.code in seen:
                raise ApiPluginContractError(
                    f"route {self.path!r} declares error code {error.code!r} "
                    "twice; a client branches on the code"
                )
            seen.append(error.code)

    @property
    def key(self) -> tuple[str, str]:
        """``(path, method)`` pairs are declared one at a time: see ``route_keys``."""
        return (self.path, self.methods[0])

    def route_keys(self) -> tuple[tuple[str, str], ...]:
        """Every ``(path, method)`` this route claims — the uniqueness unit."""
        return tuple((self.path, method) for method in self.methods)


def _normalize_path(path: str) -> str:
    """The COMPARISON form of a declared path: trailing slashes stripped.

    A declared path is already required to be normalized (a trailing ``/`` is
    refused by :func:`_validate_path`), so two keys that differ here cannot both
    exist. Normalizing anyway keeps the uniqueness rule below independent of
    which spelling a future declaration used.
    """
    return path.rstrip("/")


def _path_placeholders(path: str) -> tuple[str, ...]:
    """Every ``{param}`` a declared path uses, in declaration order."""
    return tuple(
        segment[1:-1] for segment in path.split("/") if _PLACEHOLDER_RE.match(segment)
    )


def _declared_schemas(route: ApiRoute) -> tuple[tuple[str, ApiSchema], ...]:
    """``(role, schema)`` for every body ``route`` declares, absent ones dropped."""
    pairs = (("request", route.request), ("response", route.response))
    return tuple((role, schema) for role, schema in pairs if schema is not None)


@dataclass(frozen=True)
class ApiPlugin:
    """One leaf's whole API declaration, published under an entry point."""

    id: str
    title: str
    api_version: str
    routes: Sequence[ApiRoute] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _require_text(self.id, "plugin id")
        _require_text(self.title, "plugin title")
        _require_version(self.api_version, "api_version")
        object.__setattr__(self, "routes", _require_elements(
            self.routes, ApiRoute, f"routes of api plugin {self.id!r}"
        ))
        if not self.routes:
            raise ApiPluginContractError(
                f"api plugin {self.id!r} declares no routes; an empty plugin "
                "cannot be distinguished from one that failed to load"
            )
        self._refuse_duplicate_route_keys()
        self._refuse_duplicate_schema_names()

    def _refuse_duplicate_route_keys(self) -> None:
        """Refuse two routes claiming the same path+method.

        The host can only compose one, so the loser would be dropped silently —
        an endpoint the leaf believes it published and no client can reach. The
        comparison is on the NORMALIZED path, so a spelling that differs only by
        a trailing slash cannot slip past as a "different" route.
        """
        seen: list[tuple[str, str]] = []
        for route in self.routes:
            for key in route.route_keys():
                normalized = (_normalize_path(key[0]), key[1])
                if normalized in seen:
                    raise ApiPluginContractError(
                        f"api plugin {self.id!r} declares {key[1]} {normalized[0]} "
                        "twice; the host can compose only one of them, so the "
                        "other would vanish without a trace"
                    )
                seen.append(normalized)

    def _refuse_duplicate_schema_names(self) -> None:
        """One flat component namespace: a name may describe only one thing.

        OpenAPI keys components by NAME, so two schemas sharing one would
        silently overwrite each other and the survivor would ship the other's
        shape. A schema's name and another schema's FIELD name are read from the
        same flat namespace by a generator, so that collision is refused by this
        same rule rather than by a weaker second one. Two schemas sharing a
        field NAME is not a collision — fields are nested under their schema —
        and stays legal.
        """
        schema_names: dict[str, str] = {}
        field_names: dict[str, str] = {}
        for route in self.routes:
            for role, schema in _declared_schemas(route):
                owner = f"{role} schema of route {route.path!r}"
                if schema.name in schema_names:
                    raise ApiPluginContractError(
                        f"api plugin {self.id!r} declares schema name "
                        f"{schema.name!r} twice ({schema_names[schema.name]} and "
                        f"{owner}); components are keyed by name, so one of the "
                        "two would silently overwrite the other"
                    )
                if schema.name in field_names:
                    raise ApiPluginContractError(
                        f"api plugin {self.id!r} names {owner} "
                        f"{schema.name!r}, which is already a declared FIELD "
                        f"({field_names[schema.name]}); a name is one thing in "
                        "this namespace, not a schema here and a field there"
                    )
                for item in schema.fields:
                    if item.name in schema_names:
                        raise ApiPluginContractError(
                            f"api plugin {self.id!r} declares field "
                            f"{item.name!r} on {owner}, which is already the "
                            f"NAME of {schema_names[item.name]}; a name is one "
                            "thing in this namespace, not a schema here and a "
                            "field there"
                        )
                    field_names.setdefault(item.name, owner)
                schema_names[schema.name] = owner

    def openapi_fragment(self) -> dict[str, Any]:
        """An OpenAPI 3.1 fragment a host can merge into its own document.

        This is a VALID document, not an approximation of one: paths are keyed
        by the absolute path the host will serve (the declaration is relative to
        the mount, the document is not), every declared ``{param}`` is emitted
        as an ``in: path`` parameter, each operation is built for its OWN method
        (so operationIds are unique and the metadata is method-specific), scoped
        routes carry a standard ``security`` requirement naming
        :data:`OAUTH_SECURITY_SCHEME`, and every generated schema closes itself
        with ``additionalProperties: false``.

        Declared metadata OpenAPI has no field for (idempotency, rate/quota
        class, audit level, project scope, transport, compute cost) rides in
        ``x-scitex-*`` extensions, which is where a specification-compliant
        consumer ignores them rather than rejects the document.
        """
        paths: dict[str, Any] = {}
        schemas: dict[str, Any] = {}
        for route in self.routes:
            entry = paths.setdefault(f"/{route.path}", {})
            for method in route.methods:
                entry[method.lower()] = self._operation(route, method, schemas)
        return {
            "paths": paths,
            "components": {
                "schemas": schemas,
                "securitySchemes": {OAUTH_SECURITY_SCHEME: _security_scheme_fragment()},
            },
        }

    def _operation(
        self, route: ApiRoute, method: str, schemas: dict[str, Any]
    ) -> dict[str, Any]:
        """The operation for ONE ``(route, method)`` pair.

        Built per method rather than deep-copied: one shared dict would give a
        GET and a POST the same ``operationId`` (which OpenAPI forbids) and let
        one method's ``parameters`` stand in for the other's.
        """
        operation: dict[str, Any] = {
            "operationId": self._operation_id(route, method),
            "x-scitex-transport": route.transport,
            "x-scitex-project-scope": route.auth.project_scope,
            "x-scitex-audit": route.audit.level,
            "x-scitex-rate-class": route.rate.rate_class,
            "x-scitex-compute-cost": route.rate.compute_cost,
            "x-scitex-api-version": self.api_version,
        }
        if route.path_params:
            operation["parameters"] = [
                {
                    "name": name,
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                }
                for name in route.path_params
            ]
        if route.auth.public:
            operation["security"] = []
        elif route.auth.scopes:
            operation["security"] = [{OAUTH_SECURITY_SCHEME: list(route.auth.scopes)}]
            operation["x-scitex-oauth-scopes"] = list(route.auth.scopes)
        if route.idempotency.required:
            operation["x-scitex-idempotency-key-header"] = route.idempotency.key_header
        if route.pagination.style != "none":
            operation["x-scitex-pagination"] = {
                "style": route.pagination.style,
                "default_limit": route.pagination.default_limit,
                "max_limit": route.pagination.max_limit,
            }
        if route.deprecation is not None:
            operation["deprecated"] = True
            operation["x-scitex-sunset-version"] = route.deprecation.sunset_version
            if route.deprecation.replacement:
                operation["x-scitex-replacement"] = route.deprecation.replacement
        if route.handler:
            operation["x-scitex-handler"] = route.handler
        if route.response is not None:
            schemas[route.response.name] = _schema_fragment(route.response)
            operation["responses"] = {
                "200": {
                    "description": route.response.name,
                    "content": {
                        _media_type(route.transport): {
                            "schema": {"$ref": f"#/components/schemas/{route.response.name}"}
                        }
                    },
                }
            }
        if route.errors:
            operation.setdefault("responses", {})["default"] = {
                "description": "declared errors",
                "x-scitex-errors": [
                    {
                        "code": error.code,
                        "status": error.status,
                        "message": error.message,
                        "retryable": error.retryable,
                    }
                    for error in route.errors
                ],
            }
        if route.request is not None:
            schemas[route.request.name] = _schema_fragment(route.request)
            operation["requestBody"] = {
                "content": {
                    _media_type(route.transport): {
                        "schema": {"$ref": f"#/components/schemas/{route.request.name}"}
                    }
                }
            }
        return operation

    def _operation_id(self, route: ApiRoute, method: str) -> str:
        """A document-unique ``operationId`` that NAMES its method.

        OpenAPI requires operationIds to be unique across the whole document, so
        the lowercased method is part of the id: without it, a route declaring
        both GET and POST would publish two operations under one id.
        """
        slug = route.path.replace("/", "_").replace("{", "").replace("}", "")
        return f"{self.id}.{method.lower()}.{slug}"


def _media_type(transport: str) -> str:
    """The OpenAPI media type for a declared transport."""
    return {
        "json": "application/json",
        "sse": "text/event-stream",
        "binary": "application/octet-stream",
    }[transport]


def _security_scheme_fragment() -> dict[str, Any]:
    """The ``components.securitySchemes`` entry for :data:`OAUTH_SECURITY_SCHEME`.

    A fresh dict per call: the fragment is handed to a host that merges it, and
    a shared module-level object would let one merge mutate every later one.
    """
    return {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": (
            "SciTeX OIDC-issued bearer access token; a deployment may express "
            "the same scheme as openIdConnect. Scopes are declared per operation."
        ),
    }


def _schema_fragment(schema: ApiSchema) -> dict[str, Any]:
    """A JSON-Schema object for a declared ``ApiSchema``.

    Closed with ``additionalProperties: false``: the declared fields ARE the
    body, so a consumer can rely on the shape instead of accepting whatever a
    client (or a mistyped field name) sends alongside it.
    """
    properties: dict[str, Any] = {}
    required: list[str] = []
    for item in schema.fields:
        entry: dict[str, Any] = {"type": item.type}
        if item.description:
            entry["description"] = item.description
        if item.enum:
            entry["enum"] = list(item.enum)
        properties[item.name] = entry
        if item.required:
            required.append(item.name)
    fragment: dict[str, Any] = {
        "title": schema.name,
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        fragment["required"] = required
    return fragment


@dataclass(frozen=True)
class ApiPluginRef:
    """One ``scitex.apis`` entry point, read WITHOUT importing it."""

    name: str
    target: str
    distribution: str = ""


def discover_api_plugins(entry_points: Optional[Iterable] = None) -> list[ApiPluginRef]:
    """Every installed ``scitex.apis`` entry point, sorted by name.

    Mirrors :func:`scitex_app.plugins.discover_plugin_apps` deliberately: the
    value is kept as a STRING, so discovery never imports a leaf's code (a host
    reads this at settings time, and an import here would run every installed
    leaf inside the host's configuration phase).

    A duplicate NAME is REFUSED rather than resolved. Two distributions claiming
    one plugin name would make the loaded plugin a function of install order,
    and "the first one wins" ships the loser silently — exactly the failure a
    host cannot see and an operator cannot debug.
    """
    if entry_points is None:
        from importlib.metadata import entry_points as _entry_points

        entry_points = _entry_points(group=API_ENTRY_POINT_GROUP)
    found: dict[str, ApiPluginRef] = {}
    for ep in entry_points:
        if ep.name in found:
            raise ApiPluginContractError(
                f"two installed distributions publish the "
                f"{API_ENTRY_POINT_GROUP} entry point {ep.name!r} "
                f"({found[ep.name].target!r} from "
                f"{found[ep.name].distribution!r} and {ep.value!r}); whichever "
                "one a host loads would depend on install order, so give each "
                "plugin a distinct name"
            )
        dist = getattr(getattr(ep, "dist", None), "name", "") or ""
        found[ep.name] = ApiPluginRef(ep.name, ep.value, dist)
    return [found[key] for key in sorted(found)]


__all__ = [
    "API_ENTRY_POINT_GROUP",
    "AUDIT_LEVELS",
    "DESCRIPTOR_IMPLEMENTATION",
    "FIELD_TYPES",
    "HTTP_METHODS",
    "IDEMPOTENCY_KEY_HEADER",
    "MUTATING_METHODS",
    "OAUTH_SECURITY_SCHEME",
    "PAGINATION_STYLES",
    "PROJECT_SCOPES",
    "RECOMMENDED_COMPUTE_COSTS",
    "RECOMMENDED_RATE_CLASSES",
    "TRANSPORTS",
    "ApiError",
    "ApiField",
    "ApiPlugin",
    "ApiPluginContractError",
    "ApiPluginRef",
    "ApiRoute",
    "ApiSchema",
    "Audit",
    "AuthScope",
    "Deprecation",
    "Idempotency",
    "Pagination",
    "RateLimit",
    "discover_api_plugins",
]

# EOF
