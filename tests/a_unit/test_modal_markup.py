# Copyright (c) 2012-2024, Abilian SAS

"""Guard the one modal mechanism.

Modals are native `<dialog>` opened by `data-modal-open="#id"`, which
vite/src/modals.js binds. Every earlier mechanism failed silently -- a
`data-toggle="modal"` left behind after Bootstrap's JS went, an `open-modal`
event with no listener, a selector pointing at an id that no longer existed.
Nothing in the build or the page source says a button has stopped working, so
the check has to be here.
"""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).parent.parent.parent / "src"

#: Idioms belonging to plugins that are no longer shipped.
DEAD = {
    r'data-toggle="(?:modal|dropdown|collapse|tab)"': "use data-modal-open, or Alpine",
    r'data-dismiss="(?:modal|alert)"': "use data-modal-close",
    r"\b(?:show|shown|hide|hidden)\.bs\.modal\b": (
        "use the `modal:open` event, or <dialog>'s native `close`"
    ),
}

TRIGGER = re.compile(r'data-modal-open="#(?P<id>[^"]+)"')
DIALOG = re.compile(r'<dialog\b[^>]*\bid="(?P<id>[^"]+)"')
#: Some dialogs are built by a macro, given their id first (`documents/_dialogs.html`,
#: `wiki/macros.html`), with its variable part spelled `%d` there and `{{ … }}` in the
#: trigger: both count as one placeholder.
DIALOG_MACRO = re.compile(r'(?:form_)?dialog\(\s*"(?P<id>[^"]+)"')
VARIABLE = re.compile(r"\{\{.*?\}\}|%[ds]")


def _id(text: str) -> str:
    return VARIABLE.sub("*", text)


def _templates() -> list[Path]:
    return [p for p in SRC.rglob("*.html") if "static" not in p.parts]


def _markup_sources() -> list[Path]:
    """Templates, plus the Python that renders markup of its own."""
    return _templates() + [p for p in SRC.rglob("*.py") if "static" not in p.parts]


def test_no_bootstrap_plugin_idioms_left() -> None:
    offences = [
        f"{path.relative_to(SRC.parent)}:{text[: m.start()].count(chr(10)) + 1}:"
        f" {m.group(0)} -- {hint}"
        for path in _markup_sources()
        for text in [path.read_text(errors="ignore")]
        for pattern, hint in DEAD.items()
        for m in re.finditer(pattern, text)
    ]

    assert not offences, "markup bound by plugins we no longer ship:\n" + "\n".join(
        offences
    )


def test_every_modal_trigger_has_a_dialog() -> None:
    """A trigger naming a missing id is a button that does nothing."""
    triggers: dict[str, str] = {}
    dialogs: set[str] = set()

    for path in _templates():
        text = path.read_text(errors="ignore")
        for m in TRIGGER.finditer(text):
            triggers.setdefault(_id(m.group("id")), str(path.relative_to(SRC.parent)))
        dialogs.update(_id(m.group("id")) for m in DIALOG.finditer(text))
        dialogs.update(_id(m.group("id")) for m in DIALOG_MACRO.finditer(text))

    missing = {name: where for name, where in triggers.items() if name not in dialogs}

    assert not missing, f"modal triggers with no <dialog> of that id: {missing}"


INCLUDE = re.compile(r'{%-?\s*include\s+"(?P<name>[^"]+)"')


def _by_template_name() -> dict[str, Path]:
    """Map the name an `{% include %}` uses to the file it resolves to."""
    names = {}
    for path in _templates():
        parts = path.parts
        root = len(parts) - 1 - parts[::-1].index("templates")
        names["/".join(parts[root + 1 :])] = path
    return names


def _closure(path: Path, by_name: dict[str, Path]) -> set[Path]:
    """`path` plus every template it pulls in, transitively."""
    seen = {path}
    stack = [path]
    while stack:
        text = stack.pop().read_text(errors="ignore")
        for m in INCLUDE.finditer(text):
            included = by_name.get(m.group("name"))
            if included and included not in seen:
                seen.add(included)
                stack.append(included)
    return seen


def test_every_close_button_is_inside_a_dialog() -> None:
    """`data-modal-close` closes `closest("dialog")`; outside one that throws."""
    strays: list[str] = []

    for path in _templates():
        text = path.read_text(errors="ignore")
        for m in re.finditer(r"data-modal-close", text):
            before = text[: m.start()]
            depth = len(re.findall(r"<dialog\b", before)) - before.count("</dialog>")
            if depth <= 0:
                line = before.count("\n") + 1
                strays.append(f"{path.relative_to(SRC.parent)}:{line}")

    assert not strays, "data-modal-close outside any <dialog>:\n" + "\n".join(strays)


def test_modal_ids_are_unique_within_a_page() -> None:
    """Two dialogs shared the id `modal-edit`, so Edit opened the wrong one.

    Ids only have to be unique among the templates that end up on the same
    page, which is what the include closure approximates -- `modal-delete`
    legitimately exists in wiki, forum and documents, which never meet.
    """
    by_name = _by_template_name()
    clashes: list[str] = []

    for path in _templates():
        seen: dict[str, str] = {}
        for member in sorted(_closure(path, by_name)):
            rel = str(member.relative_to(SRC.parent))
            for m in DIALOG.finditer(member.read_text(errors="ignore")):
                name = m.group("id")
                if name in seen and seen[name] != rel:
                    clashes.append(
                        f"{path.name} pulls in {name} from both {seen[name]} and {rel}"
                    )
                seen.setdefault(name, rel)

    assert not clashes, "<dialog> ids that collide on one page:\n" + "\n".join(clashes)
