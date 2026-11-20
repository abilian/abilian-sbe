# Contributing

Thank you for your interest in Abilian SBE. Contributions of every size are welcome: a bug report, a fix to a page of this documentation, a translation, a new feature. Everyone taking part is expected to act with courtesy and respect.

## Ways to contribute

- **Report a bug or ask for a feature** on the [issue tracker](https://github.com/abilian/abilian-sbe-monorepo/issues). Say what you did, what you expected and what happened instead, with the version and, for a problem in the interface, a screenshot.
- **Improve the documentation.** It lives in `docs/`, in Markdown: the English pages in `docs/src/`, their French translations in `docs/i18n/fr/`.
- **Translate the interface.** The catalogs are in `src/abilian/sbe/translations/` and `src/abilian/translations/`, one per language.
- **Change the code**, through a [pull request](https://github.com/abilian/abilian-sbe-monorepo/pulls).

## Architecture Decision Records

Significant changes to the architecture are discussed and recorded as [Architecture Decision Records](https://github.com/abilian/abilian-sbe-monorepo/tree/main/notes/adrs) (ADRs), in `notes/adrs/`. Read the ones that touch your change before you start. A new feature or a change to how the parts fit together should refer to an ADR, or propose one.

## Making a change

1. **Discuss first** anything larger than a fix: open an issue, or comment on an existing one, so that the work is not done twice and the approach is agreed on.
2. **Fork the repository** and set it up as the [developer guide](index.md#setting-up) explains.
3. **Work on a branch** named after what it does, for instance `fix/upload-timeout` or `feat/calendar-export`.
4. **Add tests.** A new feature comes with tests; a bug fix comes with a test that fails without it. Unit tests go in `tests/a_unit/`, those that need the application or the database in `tests/b_integration/`, the browser tests in `tests/c_e2e/` and `e2e_playwright/`.
5. **Check your work** before you push:

    ```bash
    make format     # ruff format and ruff check --fix
    make lint       # the linters and the import contracts
    make test       # the test suite
    make test-e2e   # if you changed a page
    ```

    The pre-commit hooks, installed by `make install`, run the quick checks on every commit.

6. **Update the documentation** when your change shows in the interface or in the configuration, in English and, if you can, in French.
7. **Open the pull request.** Explain what it changes and why, and link the issue. Maintainers review it; expect questions and requests for changes.

## Conventions

- **Python 3.12** or later, with type hints on every function.
- **Formatting** is ruff's: run `make format` before you commit.
- **Linters** are not silenced: no `noqa`, no `type: ignore`. If a rule gets in the way, change the code, or discuss the rule.
- **Logging** goes through [loguru](https://loguru.readthedocs.io/): `from loguru import logger`.
- **Interface text** is written to be translated, with `_()` in Python and in templates, and the pages use the components of the Abilian Design System.
- **Commit messages** follow [Conventional Commits](https://www.conventionalcommits.org/): `fix(documents): keep the owner when moving a folder`. A short subject line, and if needed one paragraph that says why.

## Licence

Abilian SBE is licensed under the [LGPL v3](https://www.gnu.org/licenses/lgpl-3.0.html). By contributing, you agree that your contribution is released under the same licence. The project follows the [REUSE](https://reuse.software/) specification: `REUSE.toml` declares the copyright and licence of every file. A file that comes from elsewhere, under another licence, says so in a comment at its top.

## Questions

Ask on the [issue tracker](https://github.com/abilian/abilian-sbe-monorepo/issues). There is no wrong question.
