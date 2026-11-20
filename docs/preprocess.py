"""Prepare every edition of the documentation for Zensical, and then its root.

Each language in zensical.toml's [[project.extra.alternate]] list is an edition
under its own /<lang>/, English first. English is src/, configured by
zensical.toml and built to site/en/. Every other edition gets:

- its pages, translated, in i18n/<lang>/. They are every page of src/ except
  develop/, whose detail is English only, and the two sets have to match: the
  language selector (src/assets/lang.js) sends a reader to the same path in
  the other edition. Each edition has its own i18n/<lang>/develop/index.md, one
  page introducing the section and linking to the English one;
- a copy of src/assets/, since Zensical does not follow a symlinked directory;
- zensical.<lang>.toml, generated from zensical.toml with that edition's paths,
  language and strings, and a nav whose Developers tab is that one page.

The root of the site belongs to no edition, and `--site-root` writes it once
they are all built: the chooser (index.html).

What each edition says in its own language is in editions.toml. Everything this
writes is gitignored.

`make build`, `make serve` and `make check` run it. On its own:

    uv run --project .. python preprocess.py
    uv run --project .. python preprocess.py --site-root     # after the builds
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

DOCS = Path(__file__).parent
CONFIG = DOCS / "zensical.toml"
STRINGS = tomllib.loads((DOCS / "editions.toml").read_text("utf-8"))
ASSETS = DOCS / "src" / "assets"
SITE = DOCS / "site"
CHOOSER = DOCS / "index.html"
# The section whose detail is not translated. Every edition has its own
# develop/index.md introducing it; the pages under that are English only.
ENGLISH_ONLY = "develop/"
COPYRIGHT = re.compile(r'^copyright = """.*?"""\n', re.MULTILINE | re.DOTALL)
NAV = re.compile(r"^nav = \[\n.*?^\]\n", re.MULTILINE | re.DOTALL)


@dataclass(frozen=True)
class Edition:
    lang: str
    link: str  # its address on the site, /<lang>/
    pages: Path  # its docs_dir
    config: Path

    @property
    def strings(self) -> dict:
        return STRINGS[self.lang]


def fail(msg: str) -> NoReturn:
    text = f"preprocess: {msg}"
    raise SystemExit(text)


def editions(config: str) -> list[Edition]:
    alternates = tomllib.loads(config)["project"]["extra"]["alternate"]
    links = {a["lang"]: a["link"] for a in alternates}
    if list(links)[:1] != ["en"]:
        fail("zensical.toml's first [[project.extra.alternate]] must be English")
    for lang, link in links.items():
        if link != f"/{lang}/":
            fail(f"the {lang} edition's link is {link}, and should be /{lang}/")
    missing = [lang for lang in list(links)[1:] if lang not in STRINGS]
    if missing:
        fail(f"editions.toml has no section for {', '.join(missing)}")
    return [
        Edition("en", links["en"], DOCS / "src", CONFIG),
        *(
            Edition(lang, link, DOCS / "i18n" / lang, DOCS / f"zensical.{lang}.toml")
            for lang, link in list(links.items())[1:]
        ),
    ]


def toml_entry(entry: dict, indent: str) -> str:
    ((label, value),) = entry.items()
    # json.dumps writes a valid TOML basic string, quotes and all.
    key = json.dumps(label, ensure_ascii=False)
    if isinstance(value, str):
        return f"{indent}{{ {key} = {json.dumps(value)} }},"
    inner = "\n".join(toml_entry(child, indent + "    ") for child in value)
    return f"{indent}{{ {key} = [\n{inner}\n{indent}]}},"


def toml_nav(nav: list[dict]) -> str:
    return "nav = [\n" + "\n".join(toml_entry(e, "    ") for e in nav) + "\n]\n"


def paths(value: str | list) -> list[str]:
    if isinstance(value, str):
        return [value]
    return [p for child in value for v in child.values() for p in paths(v)]


def translate_nav(english: list[dict], edition: Edition) -> list:
    labels = edition.strings["nav"]

    def t(label: str) -> str:
        if label not in labels:
            fail(f"editions.toml: [{edition.lang}.nav] has no {json.dumps(label)}")
        return labels[label]

    out: list[dict] = []
    for entry in english:
        ((label, value),) = entry.items()
        if all(p.startswith(ENGLISH_ONLY) for p in paths(value)):
            # The English sub-pages are not translated: the whole section is
            # the edition's own one-page introduction.
            out.append({t(label): f"{ENGLISH_ONLY}index.md"})
        elif isinstance(value, str):
            out.append({t(label): value})
        else:
            out.append({t(label): [{t(k): v} for c in value for k, v in c.items()]})
    return out


def pages(root: Path) -> set[str]:
    names = (p.relative_to(root).as_posix() for p in root.rglob("*.md"))
    return {n for n in names if not n.startswith(ENGLISH_ONLY)}


def replace_once(pattern: str | re.Pattern, new: str, text: str) -> str:
    regex = re.compile(re.escape(pattern) if isinstance(pattern, str) else pattern)
    if len(regex.findall(text)) != 1:
        fail(f"expected one {regex.pattern!r} in zensical.toml")
    return regex.sub(lambda _: new, text)


def edition_config(english: str, nav: list[dict], edition: Edition) -> str:
    lang, s = edition.lang, edition.strings
    text = english
    for old, new in [
        ('docs_dir = "src"', f'docs_dir = "i18n/{lang}"'),
        ('site_dir = "site/en"', f'site_dir = "site/{lang}"'),
        ('language = "en"', f'language = "{lang}"'),
        (
            'toggle.name = "Switch to dark mode"',
            f"toggle.name = {json.dumps(s['dark'], ensure_ascii=False)}",
        ),
        (
            'toggle.name = "Switch to light mode"',
            f"toggle.name = {json.dumps(s['light'], ensure_ascii=False)}",
        ),
    ]:
        text = replace_once(old, new, text)
    url = tomllib.loads(english)["project"]["site_url"]
    if not url.endswith("/en/"):
        fail(f"zensical.toml's site_url is {url}, and should end in /en/")
    text = replace_once(
        re.compile(r"^site_url = .*\n", re.MULTILINE),
        f'site_url = "{url.removesuffix("en/")}{lang}/"\n',
        text,
    )
    for key in ("site_name", "site_description"):
        value = json.dumps(s[key], ensure_ascii=False)
        text = replace_once(
            re.compile(rf"^{key} = .*\n", re.MULTILINE), f"{key} = {value}\n", text
        )
    text = replace_once(COPYRIGHT, f'copyright = """{s["copyright"]}"""\n', text)
    text = replace_once(NAV, toml_nav(nav), text)
    header = f"# Generated by preprocess.py from zensical.toml and editions.toml [{lang}].\n\n"
    return header + text


def publish_edition(edition: Edition, english: str) -> list[str]:
    """Everything one edition needs, and what is wrong with it."""
    problems = []
    expected, have = pages(DOCS / "src"), pages(edition.pages)
    for name in sorted(expected - have):
        problems.append(f"i18n/{edition.lang}/{name} is missing")
    for name in sorted(have - expected):
        problems.append(f"i18n/{edition.lang}/{name} has no English page")
    if not (edition.pages / ENGLISH_ONLY / "index.md").is_file():
        problems.append(f"i18n/{edition.lang}/{ENGLISH_ONLY}index.md is missing")

    shutil.rmtree(edition.pages / "assets", ignore_errors=True)
    shutil.copytree(ASSETS, edition.pages / "assets")

    english_nav = tomllib.loads(english)["project"]["nav"]
    nav = translate_nav(english_nav, edition)
    edition.config.write_text(edition_config(english, nav, edition), "utf-8")
    return problems


def write_site_root(all_editions: list[Edition]) -> None:
    """The chooser at the root, which belongs to no edition."""
    chooser = CHOOSER.read_text("utf-8")
    for edition in all_editions:
        if f'href="{edition.lang}/"' not in chooser:
            fail(f"index.html has no link to the {edition.lang} edition")
    SITE.mkdir(exist_ok=True)
    (SITE / "index.html").write_text(chooser, "utf-8")
    print("preprocess: site root")


def main() -> None:
    en, *others = editions(CONFIG.read_text("utf-8"))
    if sys.argv[1:] == ["--site-root"]:
        write_site_root([en, *others])
        return
    english = CONFIG.read_text("utf-8")
    problems = [p for e in others for p in publish_edition(e, english)]

    # A stale config, from an edition since dropped, would still build.
    wanted = {e.config for e in others}
    for config in DOCS.glob("zensical.*.toml"):
        if config not in wanted:
            config.unlink()

    if problems:
        fail("the editions do not match:\n  " + "\n  ".join(problems))
    print(f"preprocess: {', '.join(e.lang for e in (en, *others))}")


if __name__ == "__main__":
    main()
