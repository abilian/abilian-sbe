# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

SQLAlchemy 2.0, and a pass over who may reach what. Every route now refuses an anonymous visitor unless it is public on purpose, and the code below the views takes the user as a parameter instead of reading `current_user`, so the type checker can tell where a logged-in user is required.

### Upgrade steps

1. Install the new dependencies: SQLAlchemy 2.0 and Flask-SQLAlchemy 3.1. No migration: the schema is unchanged.
2. Remove `SOCIAL_REST_API` from the configuration, if set: the API it enabled is gone.
3. Downstream code: see the API changes below. Most of them are a new first parameter, the user.

### Security

- Anyone could fetch any image stored in the database, those of private communities' documents and attachments included, by counting ids at `/images/files/<id>`. The route is gone, and user photos need a login.
- Anonymous visitors could upload files, into one directory every anonymous visitor shared. Uploads need a login.
- The attachment, comment and tag views asked for no login.
- The tag management views (`/tags/manage/...`) were open to anyone; they are removed, since the admin tags panel does their job.
- Any logged-in user could edit the tags of any entity. It now takes write permission on the entity.
- Any logged-in user could open another user's profile editor, prefilled; only saving was refused.
- The admin pages answered 404 or 403 depending on whether the vocabulary in the URL existed, to anyone.
- Any logged-in user could see a private group's page, member list and photo, and join it by posting `action=join`, which the page does not offer. A private group is now seen only by its members and administrators, and only a public group can be joined.
- The communities' JSON list (`/communities/json2`) gave anyone, anonymous visitors included, the names of all communities, private ones too; nothing used it, and it is removed. `/communities/doc/<id>` told anyone which community a document is in; it is now a 404 unless the user may read the document. Every route of the community blueprints now needs a login.
- Two tests now request every route, one as an anonymous visitor and one as a logged-in user with no role and no membership, and fail on any route that does not refuse them and is not listed as open on purpose.

### Changed

- Search needs a login: everything worth finding is members-only.
- An anonymous visitor reaching a page that needs a user is sent to the login page.

### Removed

- The social REST API and its `SOCIAL_REST_API` setting. It was unused and broken, and, turned on, let any logged-in user change or delete any account.

### Breaking — framework API

| was | is |
|---|---|
| `can_manage(community, user=None)` | `can_manage(user, community)` |
| `is_member(community=None, user=None)` | `is_member(user, community=None)` |
| `check_membership(community=None, user=None)` | `check_membership(user, community=None)` |
| `forum.security.can_write(post, user=None)` | `can_write(user, post)` |
| `Lock.new()`, `lock.is_owner(user=None)`, `doc.set_lock(user=None)` | the user is required |
| `folder.filtered_children`, `.filtered_subfolders` (properties) | methods taking the user |
| `WikiPage(...)`, `page.create_revision(body_src, message)` | `WikiPage(..., author=user)`, `create_revision(author, body_src, message)` |
| `get_recent_entries(num, user=None, community=None)` | `get_recent_entries(user, num, actor=None, community=None)` |
| comments' and attachments' `can_read(entity)` and the like | `can_read(user, entity)` and the like |
| `indexing.search(q, ..., user=None)` | `user=` is required |
| `preferences.get_preferences(user=None)` and the like | the user is required |
| `LoginSession.new()` | `LoginSession.new(user)` |
| the document view helpers (`get_document`, `check_read_access`, ...) | the user first |
| `ScopedSession` | removed; use `db.session()` |

`abilian.core.extensions.login` adds `@authenticated`, which hands a view the logged-in user as its first argument, and `authenticated_user()` for class-based views and hooks. Its `current_user` is typed as the `User | AnonymousUser` it stands for. `security.has_permission` and `filter_with_permission` take a `User`; `has_role` still accepts an anonymous visitor.

Models declare their columns as `Mapped[...]`, and `db.Model` is built on a typed declarative base. `session_of(obj)` gives an object's session. `get_object_by_path` returns None for a missing path, as documented, instead of raising `StopIteration`.

### Fixed

- The "my groups" tab crashed.
- `Document.set_lock(user)` locked the document for the current user, whoever it was given.
- Changing the owner of documents to a missing or unknown user cleared their owner and reported success.
- Downloading or deleting a wiki attachment checked with `assert`s that it belonged to the page in the URL; with asserts disabled, any attachment was reachable through any page.
- Removing a community member with an unknown id, or a membership that is not the user's, was a 500.
- An unknown group or user in the social pages was a 500, not a 404.
- Removing a role on a folder was always a 500, and the role forms crashed on an unknown user or group.
- Listing the inherited roles of the repository root crashed: it read a parent the root does not have.
- An email reply to a deleted forum thread raised, and was retried twenty times; it is now logged and dropped.
- Logging in to an account with an empty password column was a 500.
- The query for a community's last views failed on PostgreSQL.
- A group or user form posted with a missing or unknown action was a 500, not a 400.
- Uploading or deleting a wiki attachment ended on the page's viewers list instead of the page.
- With Sentry configured for the browser, the Content Security Policy refused the reports sent to the DSN's host.

## [1.2.0] - 2026-11-15

The Tailwind front-end migration, an authorization convergence, MariaDB support and a type cleanup that found a score of bugs. Large, and it changes framework API that downstream applications may import.

### Upgrade steps

Run in this order. The backfills ship *with* this release, so they cannot run before it is installed — install, backfill, then serve traffic.

1. Run Python 3.12 or later. On PostgreSQL, install the `postgres` extra (`abilian-sbe[postgres]`): psycopg2 is no longer a required dependency, so without the extra the application has no PostgreSQL driver. MariaDB and MySQL use PyMySQL, which is required.
2. `flask db current`, then `flask db upgrade` — no new migrations in this release, but run it anyway. A database created by `flask initdb` records no version: `current` prints no revision and `upgrade` fails with `relation "sbe_event" already exists`, leaving the database unchanged. Run `flask db stamp head` once on such a database instead of `upgrade`. The two migrations date from 2017, and `initdb` already creates what they add.
3. `flask backfill-community-roles` — **required.** Community memberships used to be recorded only on the community's folder; permissions are now asked of the community itself. Until this runs, every existing community manager loses MANAGE on their community. Idempotent, and `--dry-run` lists what it would change.
4. `flask backfill-creator-memberships` — recommended. Makes each community's creator a MANAGER member. Skips creators who already hold a role, so a deliberate demotion is not undone.
5. Rebuild assets: the front end is Vite + Tailwind now, and `flask assets build` no longer does anything.
6. If `TRACKING_CODE` is set, make sure it loads its script by URL from an allowed origin: the Content Security Policy now refuses inline scripts.

### Security

- Any member of a community could edit any other member's forum post: the route enforced nothing, and the Edit link was merely hidden from them.
- Any member of a community could promote themselves to manager through the member wizard, which carried only a membership check.
- Group administration — including adding and removing administrators — was guarded by `assert`, which `python -O` removes entirely.
- The attachment and comment routes carried no authorization at all. Not exploitable, since no model is registered attachable or commentable, but they are now checked rather than left armed for whoever registers one.
- The policy engine had an off switch: `has_role`, `has_permission` and `query_entity_with_permission` returned True when the service was not running.
- Anonymous search raised rather than returning results.
- A community manager could not edit their own community's settings, nor moderate its forum. Both are theirs now.
- Anyone who could read a document could lock or unlock it, which stops others uploading a new version. It now takes write access.

### Breaking — framework API

| was | is |
|---|---|
| `is_manager(context, user)` | `can_manage(community, user)` |
| `@require_manage` | `@can_manage` |
| `@require_admin` | `@is_site_admin` |
| `@require_access` | removed — the community blueprint already gates every route |
| `has_access(community, user)` | `is_member(community, user)` |
| `check_access(...)` | `check_membership(...)` |
| `can_administrate(context)` | `is_admin(context)` |
| `AttachmentsManager.can_view` / `.can_edit` | `.can_read` / `.can_write` |
| template variable `is_manager` | `can_manage_community` |
| `Select2Field`, `Select2MultipleField`, `QuerySelect2Field` | `ChoiceField`, `MultipleChoiceField`, `QuerySelectField`: native selects |
| `JsonSelect2Field`, `Select2Ajax`, `Select2`, `Chosen`, `TagInput` | removed; pick a user with `<input data-picker="url">` |
| `{% deferJS %}`, `{% block js %}`, `form.js`, `window.Abilian` | removed; the scripts are ES modules in `vite/src/` |
| `g.is_manager` | removed — ask `is_site_admin()` or `can_manage(community)` |

`Community.has_permission(user, permission)` no longer raises for anything but MANAGE; it answers all five permissions. `AttachmentsManager.can_create` and `.can_delete` ask CREATE and DELETE rather than both asking WRITE — the same answer under the default role matrix, but now separable by a `PermissionAssignment`.

### Added

- MariaDB support. Listings sort empty values last without `NULLS LAST`, which MariaDB lacks.
- Dependencies upgraded: Flask 3.1, WTForms 3.3, Flask-WTF 1.3, Dramatiq 2.2, SQLAlchemy 1.4.54. Python 3.12 to 3.15 are tested.

### Front end

- Bootstrap and all 115 LESS files replaced by Tailwind v4 and Vite.
- Removed: jQuery, select2, bootstrap-tagsinput, DataTables, CKEditor, RequireJS, twitter typeahead, Hogan, bootstrap-switch, d3 3.5 and nvd3, the flask-assets pipeline, and the Bootstrap compatibility shim.
- No inline scripts or event handlers, and neither `'unsafe-inline'` nor `'unsafe-eval'` for scripts in the Content Security Policy. A normal page loads 97K of JavaScript.
- Charts are uPlot (24K) rather than d3 + nvd3 (147K gzipped); the admin dashboard was rebuilt on correct data.
- Modals are native `<dialog>`; live search is a native combobox.
- Static URLs are versioned and served with a far-future cache.
- `pandas` and `numpy` dropped from the dependencies.

### Fixed

- Selecting rows in a folder offers Download again. The action declared no permission, its check raised on the empty default, and the exception hid the button.
- A server error inside a community shows the error page again rather than a raw 500.
- The translation catalogs compile without errors: the French and Dutch SIRET messages used a placeholder that did not match the source.
- File uploads work again with WTForms 3.3, and downloads are sent without an ETag or a cache lifetime.
- The document views served a folder or document of another community under any community's URL, and crashed on the repository root. Both are now a 404. Access was still checked on the object itself, so nothing was disclosed.
- Saving a calendar event with a description crashed: it called bleach with an argument bleach 6 removed.
- The tag edit page (`/tags/entity/<id>/edit`) crashed on every request.
- An unknown vocabulary in an admin URL is a 404 rather than a 500.
- Forms with a missing field are a 400 rather than a 500: the folder role forms, the admin settings, the group admin's add and remove member, and the folder name check.
- `repr()` of a community membership raised `TypeError`.
- The security debug panel showed `{g.id}` literally instead of ids and emails.
- The wiki page and community tab actions resolve their URL like other actions; a wiki action given a callable URL returned the function itself.
- The antivirus scan of a path given as a string raised `TypeError`.

### Removed

Code that nothing reached, much of it broken:

- The WebDAV interface (`documents/webdav`) and the CMIS AtomPub interface (`documents/cmis`): neither blueprint was registered. CMIS's authentication hook was commented out. `lxml`, used only by CMIS, is no longer a dependency.
- The invite views (`social/views/invites.py`) and their `Invite` model, never imported.
- The entity tag list, add and remove views (`/tags/entity/<id>/list|add|remove`), which crashed on every request.
- Five conversion handlers never registered: Abiword (two), Unoconv, Cloudooo and wvWare.
- `BaseBlobDownload`, `IndexService` and `WhooshIndexService.search_for_class()`.
- A Flask-SQLAlchemy 2 driver override, `apply_driver_hacks`, that has not run since Flask-SQLAlchemy 3.0.
- The GitHub Actions workflow: CI runs on sourcehut.

### Testing

- Playwright browser suite (97 tests) — `make test-e2e`, which now picks free ports rather than hardcoding 8899 and 6399.
- `pytest` no longer needs a Redis running on the machine.
- import-linter contracts keep Flask out of the policy engine and the domain models.
- `make test-postgres-docker` and `make test-mariadb-docker` run the suite against each database in Docker; run `make front` first.
- pyrefly checks against Python 3.12: 768 errors down to 348, and what is left is third-party typing.

## [1.1.16] - 2025-12-4

### Chore
- Update dependencies and SlapOS configuration files
- Update requirements.txt and sync dependencies
- Add requirements_no_dev.txt file

## [1.1.15] - 2025-09-12

### Bug Fixes
- Remove dependency on mmdb-writer and netaddr
- Fix mypy type checking issues

### Chore
- Update dependencies and SlapOS configuration files
- Extensive ruff configuration improvements and formatting
- Update requirements.txt and sync dependencies

### Refactor
- Add comprehensive type annotations
- Cast using strings instead of types
- Modernize code with dataclasses and improved patterns
- Move returns out of else clauses for cleaner code
- Use dataclasses and modernize code patterns

## [1.1.13] - 2024-11-04

### Bug Fixes
- Fix race conditions in task processing
- Update SlapOS configuration files
- Fix CLI commands and missing dependencies
- Fix typing issues and refactoring errors

### Features
- Add nixpacks support for deployment
- Add Nix support for development environment

### Documentation
- Add Architecture Decision Records (ADRs)
- Update roadmap and development documentation
- Add contribution guidelines and build badges
- Improve README and installation guides

### Chore
- Migrate from Poetry to UV package manager
- Remove ClamAV dependency
- Extensive dependency updates
- Improve CI/CD configuration
- Add REUSE compliance for licensing
- Remove unused modules and clean up imports

### Refactor
- Simplify application class with less inheritance
- Refactor services and app setup
- Extensive code modernization and cleanup
- Replace isort with ruff for import sorting
- Add comprehensive type annotations

## [1.1.12] - 2024-05-08

### Documentation
- Add governance documentation
- Update licensing information

### Chore
- Update dependencies
- Improve REUSE compliance

## [1.1.11] - 2024-05-06

### Features
- Add Nix support for development environment

### Chore
- Extensive dependency updates
- Protect secrets in configuration
- Code formatting improvements

## [1.1.10] - 2024-04-25

### Documentation
- Update TODO list

### Chore
- Add type annotations
- Multiple dependency updates

## [1.1.9] - 2024-04-04

### Chore
- Dependency updates

## [1.1.8] - 2024-04-04

### Bug Fixes
- Fix imports for SQLAlchemy 2.x compatibility

### Chore
- Update html2text dependency
- Modernize Flask-SQLAlchemy imports
- Code cleanup and dependency updates
- Silence ruff warnings and improve configuration

## [1.1.7] - 2024-03-27

### Chore
- Remove unused tailwind dependency

## [1.1.6] - 2024-03-27

### Bug Fixes
- Fix error on forum attachment uploads
- Fix "FolderishModel not mapped" test issue

### Refactor
- Remove unused code: BaseCriterion, TextSearchCriterion, TextCriterion, TagCriterion

### Chore
- Update dependencies and ruff configuration

## [1.1.2, 1.1.3, 1.1.4 and 1.1.5] - 2024-03-26

- Bugfix: fix live-search

## [1.1.2] - 2024-03-25

- Temp fix: deactivate live-search to fix issue on rich text editor

## [1.1.1] - 2024-03-25

- Cleanup "sysinfo" code.
- Cleanup imports
- Update PyPI metadata


## [1.1.0] - 2024-03-23

- Dropped support for Python < 3.10
- Upgrade many dependencies
- Switch from Celery to Dramatiq

## [1.0.5]

### Bug Fixes

- Adapt `_vocabularies()` function to `sqlalchemy` v1.3.24.
- Monkeypatch tests for `dramatiq` use (forum, wiki, communities, documents).
- If root user (user 0) not present, create it during initialization.
- Make sure only one LibreOffice process is running at any time to fix conversion failure (via locking).
- Better detection of `lessc`, permit to configure its path with `FLASK_LESS_BIN`.

### Continuous Integration

- Update pre-commit dependencies.
- Ensure `pip_audit` is updated in `tox.ini`.
- Update `adt` command in `tox.ini` (adt security-check -> adt audit).
- Remove `git-cliff`.

### Documentation

- Add `example_config` folder with step by step install procedure.
- Add Nua config example.
- Add SlapOS config example.

### Features

- Task scheduler crontab can be configured through `flask.config` (or `.env`).

### Refactor

- Update Python to version 3.12.
- Move logging system to `Loguru`.
- Complete removal of `Celery`, use now `Dramatiq` task manager.
- `Dramatiq` configured with: `flask-dramatiq`, `dramatiq-abort`, `apscheduler`.
- Add `honcho` dependency, provide a default `Procfile`.
- Provide a `.env` example (named `dot_env.example`).
- Provide an explicit `wsgi.py` file in extranet package.
- Permit flask configuration from environment, using `.from_prefixed_env()`.
- Update dependencies.

## [1.0.2] - 2023-10-04

### Bug Fixes

- Remove duplicate dependency.
- App.json was malformed.

### Documentation

- Update README (esp. install procedure).
- Add "npm install" step.
- Start using git-cliff.

### Refactor

- Simplify configuration management.

## [1.0.1] - 2023-06-06

### Bug Fixes

- Downgrade SQLAlchemy to 1.2.* to workaround some bugs.
- Use env variables for prod too.
- Workaround production bug.
- Celery config.
- Celery fixes.
- Celery debug
- Add missing dependency on toml.
- Remove debug instruction.
- Don't fail too hard when attachment is not available.
- Run all tests.
- Typing issue.
- Html.
- Revert tailwind experiment.
- Work under Python 3.11.
- Use new keyword for tox.

### Continuous Integration

- Add GH workflow config.
- Circleci config.
- Add missing safety module.
- Config (fix 'safety' target)
- Silence all flake8 warnings.
- Debug CI failure.
- Faster and cleaner tox config.
- Add safety check to default tox target.
- Don't use cache.
- Fix failure on Circle.
- Sourcehut config.
- Try using Alpine
- Alpine tweak.
- Tweak alpine and add ubuntu.
- Fix ubuntu build (?)
- Alpine fix
- Fix builds (?)
- Change task order.
- Another fix.
- Another fix.
- Update CircleCI and tox scripts.
- Don't run "safety" job for now.
- Fix tox config.
- Fix github action config.
- Another fix

### DevOps/Deployment

- Try to deploy on Heroku.
- Not need for setup.py
- Workaround platform issue.
- Remove debug code.

### Documentation

- Add a TODO.

### Features

- Add '-y' option to dropdb.
- Start dockerizing.

### Refactor

- Cleanup imports.
- Fix some typing issues.
- Cleanup / typing.
- Import the future (annotations)
- Remove unneeded injected arg.
- We don't need these injections.
- More deprecation updates.
- Upgrade celery and fix issues.
- Configuration + celery
- Simplify celery tasks.
- Modernize annotations (Python 3.8+)
- Simplify tests fixtures.
- Cleanup imports.
- Modernize (use `super()`).
- Rename "repository" service to "blob_store".
- Rename blob storage service + modernize tests.
- Rename class.
- Fix some warnings.
- Remove unneeded arguments.
- Add flask-tailwind files.
- Remove old IE support (was broken anyway)
- Remove deprecated macros.
- Use honcho.
- Drop python3.8 support and test against py3.11.
- Use contextlib.suppress.
- Simplify if statements.
- Use f-strings

### CI

- Ci lint build

### Misc

- Investigate failing test.

<!-- generated by git-cliff -->
