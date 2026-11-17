# Copyright (c) 2012-2024, Abilian SAS

"""A predicate's name is a claim about its body.

`is_x` reduces to `has_role(user, X, obj)`; `can_x` reduces to
`has_permission(user, X, obj)`. So the suffix is not a word chosen for how it
reads -- it is the name of a role or of a permission, and this test says so.

Two things it buys. A `can_` name asserts that its permission exists, which
would have rejected `can_view` and `can_edit` (there is no VIEW or EDIT
permission; the questions are READ and WRITE) on the day they were written. And
it makes the reverse visible: `can_delete` asking WRITE means anyone who may
write an attachment may delete it, which the name denies.

**What this does not check.** It compares the name against the vocabulary, not
the name against the body. `can_manage` passes here because MANAGE is a real
permission, while its body is two role tests -- which is exactly the gap open
decision 2 closes, by granting community roles on the Community object so the
body can become `has_permission(user, MANAGE, community)`. Checking bodies
statically is not worth the false positives; that clause is reviewed, not
enforced.

See notes/plan-authorization.md, "Naming: what a predicate's name promises".
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from abilian.services.security.models import Permission, Role

SRC = Path(__file__).resolve().parents[2] / "src" / "abilian"

#: Modules whose job is deciding who may do what. Authorization predicates
#: belong in one of these: `is_admin` came to mean two different things because
#: two *view* modules each grew their own.
AUTHZ_MODULES = [
    "services/security/service.py",
    "services/auth/service.py",
    "sbe/apps/communities/security.py",
    "sbe/apps/communities/decorators.py",
    "sbe/apps/forum/actions.py",
    "sbe/apps/forum/security.py",
    "sbe/apps/wiki/actions.py",
    "sbe/apps/calendar/actions.py",
    "sbe/apps/documents/actions.py",
    "web/attachments/extension.py",
    "web/comments/extension.py",
]

#: "site" says *globally, with no object*; it is a scope, not part of the name.
SCOPE_PREFIXES = ("site_",)

#: What makes a function an *authorization* predicate rather than a state one.
#: `is_closed` and `is_filtered` share a module with `can_moderate` and are not
#: governed by this rule; what separates them is that they ask nobody. A
#: predicate is in scope when its body reaches one of these, directly.
AUTHZ_PRIMITIVES = frozenset(
    {
        "has_role",
        "has_permission",
        "is_site_admin",
        "can_manage",
        "has_access",
        "check_access",
        "get_role",
    }
)

#: Canaries: if the body test above stops recognising these, it has stopped
#: working, and a rule that silently governs nothing is worse than no rule.
MUST_BE_IN_SCOPE = {
    ("sbe/apps/communities/security.py", "can_manage"),
    ("sbe/apps/forum/actions.py", "can_moderate"),
    ("sbe/apps/forum/security.py", "can_write"),
    ("sbe/apps/communities/security.py", "is_member"),
    ("web/attachments/extension.py", "can_delete"),
    ("web/comments/extension.py", "can_write"),
    ("services/auth/service.py", "is_admin"),
}

#: Capabilities named before their permission exists. Each entry names the
#: capability it currently stands in for, so introducing the real permission is
#: one line rather than a hunt. An entry that never resolves is visible debt.
PENDING_PERMISSIONS = {
    "moderate": "manage",  # forum moderation; body is can_manage(thread.community)
}

#: Predicates that do not satisfy the rule yet. This list only shrinks; every
#: row says what it should become. Deleting a row is the definition of done.
KNOWN_VIOLATIONS: set[tuple[str, str]] = set()


def _asks_authorization(node: ast.AST) -> bool:
    """Does this function body reach an authorization primitive?"""
    for child in ast.walk(node):
        called = None
        if isinstance(child, ast.Name):
            called = child.id
        elif isinstance(child, ast.Attribute):
            called = child.attr
        if called and called.lstrip("_") in AUTHZ_PRIMITIVES:
            return True
    return False


def _predicates(module: str) -> list[tuple[str, int]]:
    """Every `is_*` / `can_*` in `module` that asks an authorization question."""
    tree = ast.parse((SRC / module).read_text(), filename=module)
    found = []
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith(("is_", "can_"))
            and _asks_authorization(node)
        ):
            found.append((node.name, node.lineno))
    return found


def _suffix(name: str) -> str:
    suffix = name.split("_", 1)[1]
    for scope in SCOPE_PREFIXES:
        suffix = suffix.removeprefix(scope)
    return suffix


ALL_PREDICATES = [
    (module, name, line)
    for module in AUTHZ_MODULES
    for name, line in _predicates(module)
]


def test_the_authorization_modules_are_where_we_think() -> None:
    for module in AUTHZ_MODULES:
        assert (SRC / module).is_file(), f"{module} moved; fix AUTHZ_MODULES"


def test_the_scan_finds_the_predicates_we_know_are_there() -> None:
    """A scan that silently matches nothing proves nothing."""
    found = {(module, name) for module, name, _ in ALL_PREDICATES}
    assert found >= MUST_BE_IN_SCOPE, (
        f"the body test stopped recognising {sorted(MUST_BE_IN_SCOPE - found)}"
    )


@pytest.mark.parametrize(
    ("module", "name", "line"),
    [p for p in ALL_PREDICATES if (p[0], p[1]) not in KNOWN_VIOLATIONS],
    ids=str,
)
def test_a_predicate_is_named_for_a_real_role_or_permission(
    module: str, name: str, line: int
) -> None:
    suffix = _suffix(name)

    if name.startswith("is_"):
        known = set(Role.__instances__)
        assert suffix in known, (
            f"{module}:{line} `{name}` -- `is_` promises a role, and {suffix!r} "
            f"is not one of {sorted(known)}"
        )
        return

    known = set(Permission.__instances__)
    if suffix in PENDING_PERMISSIONS:
        assert PENDING_PERMISSIONS[suffix] in known, (
            f"{module}:{line} `{name}` stands in for "
            f"{PENDING_PERMISSIONS[suffix]!r}, which is not a permission either"
        )
        return

    assert suffix in known, (
        f"{module}:{line} `{name}` -- `can_` promises a permission, and "
        f"{suffix!r} is not one of {sorted(known)}. If the permission is meant "
        f"to exist later, add it to PENDING_PERMISSIONS with the capability it "
        f"currently stands in for."
    )


def test_the_ledger_has_no_stale_rows() -> None:
    """A violation that was fixed must be struck off, or the list stops meaning
    anything."""
    live = {(module, name) for module, name, _ in ALL_PREDICATES}
    stale = KNOWN_VIOLATIONS - live
    assert not stale, f"these no longer exist: {sorted(stale)}"


#: Asking "is this a site administrator" by hand. Twelve sites across social,
#: documents, webdav and auth each wrote one of these; `is_site_admin` is the
#: answer, and writing it out again is how the spellings multiplied.
HAND_ROLLED_SITE_ADMIN = re.compile(
    r"""has_role\(\s*(current_user|user)\s*,\s*(ADMIN|["']admin["'])"""
)


def test_nobody_asks_for_site_admin_by_hand() -> None:
    offenders = []
    for path in SRC.rglob("*.py"):
        if path.name == "service.py" and "security" in path.parts:
            continue  # `is_site_admin` itself, and the `has_role` it delegates to
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            # Prose quotes the old spelling to explain why it went; only code
            # counts, so drop anything inside backticks first.
            if HAND_ROLLED_SITE_ADMIN.search(re.sub(r"`[^`]*`", "", line)):
                offenders.append(f"{path.relative_to(SRC)}:{lineno} {stripped}")

    assert not offenders, (
        "call is_site_admin() instead of writing the role check out:\n  "
        + "\n  ".join(offenders)
    )


def test_a_capability_asks_the_permission_it_is_named_for() -> None:
    """The one place the name/body agreement is cheap to check statically.

    `AttachmentsManager` is a flat set of one-line delegates, so each
    `can_x` must pass the permission `X` to `has_permission`. It did not:
    `can_create` and `can_delete` both asked WRITE, and the three permissions
    share a default role set, so nothing distinguished "may add" from "may
    remove" while the names claimed to.
    """
    module = SRC / "web/attachments/extension.py"
    tree = ast.parse(module.read_text(), filename=str(module))

    checked = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith("can_"):
            continue
        wanted = _suffix(node.name).upper()
        asked = {
            arg.id
            for call in ast.walk(node)
            if isinstance(call, ast.Call)
            for arg in call.args
            if isinstance(arg, ast.Name)
        }
        assert wanted in asked, (
            f"{node.name} promises {wanted} and asks {sorted(asked)}"
        )
        checked += 1

    assert checked == 4, f"expected four capabilities, scanned {checked}"


# --- and the same question asked from a template ------------------------------

#: Every `is_*` / `can_*` / `may_*` name a template uses, and where it comes
#: from. A name not listed here fails the test rather than sliding in: both
#: production defects in this area were a template reading a name that nobody
#: had guaranteed would be there.
#:
#: Jinja raises when you *call* an undefined, which is loud. It does not raise
#: when you *read* one -- an undefined is falsy under `{% if x %}` and, being
#: not equal to False, truthy under `{% if x == False %}`. That asymmetry is
#: why the read column is the one that needs guaranteeing.
TEMPLATE_NAMES = {
    # called: registered globals, so a missing registration is a 500, not a lie
    "is_site_admin": "global, setup/extensions.py",
    "can_manage": "context processor, sbe/extension.py: inject_template_utils",
    "can_write_post": "context processor, sbe/extension.py: inject_template_utils",
    # read: supplied app-wide by a context processor, so never undefined
    "can_manage_community": "context processor, communities/views/views.py",
    # read: supplied by the single view that renders social/group.html
    "is_admin": "social/views/groups.py: group_home",
    # read: supplied by the views that render a folder and a document
    "may_write": "documents/views: folder_view, document_view",
    "may_manage": "documents/views: folder_view, document_view",
    "may_replace": "documents/views/documents.py: document_view",
    "may_comment": "documents/views/documents.py: document_view",
    "may_edit": "social/views/users.py: user",
    # read, and not authorization at all -- state and form plumbing
    "is_closed": "not authorization: thread state",
    "is_active": "not authorization: search facet",
}

TEMPLATE_NAME_RE = re.compile(r"(?<![.\w])((?:is|can|may)_[a-z_]+)")
JINJA_COMMENT_RE = re.compile(r"\{#.*?#\}", re.DOTALL)
JINJA_SET_RE = re.compile(r"\{%-?\s*set\s+([a-z_]+)\s*=")


def _template_names() -> dict[str, set[str]]:
    """Name -> templates using it, ignoring comments and locally-set names."""
    used: dict[str, set[str]] = {}
    for path in SRC.rglob("*.html"):
        text = JINJA_COMMENT_RE.sub("", path.read_text())
        local = set(JINJA_SET_RE.findall(text))
        for name in TEMPLATE_NAME_RE.findall(text):
            if name not in local:
                used.setdefault(name, set()).add(str(path.relative_to(SRC)))
    return used


def test_every_authorization_name_a_template_uses_is_declared() -> None:
    used = _template_names()
    undeclared = {
        name: sorted(files)
        for name, files in used.items()
        if name not in TEMPLATE_NAMES
    }
    assert not undeclared, (
        "declare where these come from in TEMPLATE_NAMES, and whether they are "
        f"authorization at all: {undeclared}"
    )


def test_the_declaration_has_no_stale_entries() -> None:
    used = _template_names()
    stale = sorted(set(TEMPLATE_NAMES) - set(used))
    assert not stale, f"no template uses these any more: {stale}"
