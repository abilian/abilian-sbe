# Roadmap for Abilian SBE

<!-- toc -->

- [Upcoming Releases](#upcoming-releases)
  * [Version 1.2 (Q3 2026)](#version-12-q3-2026)
    + [Focus Areas:](#focus-areas)
  * [Version 1.3 (Q1 or Q2 2025)](#version-13-q1-or-q2-2025)
    + [Focus Areas:](#focus-areas-1)
    + [Tasks](#tasks)
  * [See also:](#see-also)
- [Completed Releases](#completed-releases)
  * [Version 1.1 (Q1 2024)](#version-11-q1-2024)
    + [Tasks](#tasks-1)
    + [Achievements:](#achievements)
  * [Version 1.1.x (Q2 2024)](#version-11x-q2-2024)
    + [Achievements:](#achievements-1)
  * [Version 1.1.x (Q3 2024)](#version-11x-q3-2024)
    + [Achievements:](#achievements-2)

<!-- tocstop -->

## Upcoming Releases

### Version 1.2 (Q3 2026)

#### Focus Areas:

1. **Codebase Refinement**:

   - [x] Enhance type annotations and adopt modern Python coding practices, such as replacing legacy formatting with f-strings.
   - [ ] Refactor the application class for simplicity and modularity.
   - [ ] Split the extensions module to improve maintainability and logical separation.

1. **Dependency Updates**:

   - [x] Upgrade critical dependencies like SQLAlchemy to their latest stable versions.
   - [x] Address vulnerabilities by removing deprecated or insecure dependencies, such as `sqlparse`.

1. **UI Modernization** (see [the Sept 2026 plan](../notes/plan-2026-09.md)):

   - [x] Transition to modern UI frameworks: [Flask-Vite](https://github.com/abilian/flask-vite), [Tailwind CSS](https://tailwindcss.com/) and [Alpine.js](https://alpinejs.dev/). htmx was not adopted (see: ADR 006).
   - [x] Streamline the front-end development process: `make front` builds the assets, and they ship in the wheel.
   - [x] Remove the LESS/Closure/flask-assets pipeline and the Bootstrap compatibility layer.
   - [x] Remove jQuery, its plugins, and every inline script and event handler.

1. **Pipeline and CI/CD Enhancements**:

   - [x] Support for additional Python versions (e.g., Python 3.12), ensuring long-term compatibility.
   - [x] Reactivate Alpine builds, add Rocky Linux.
   - [x] Optimize CI pipelines for better efficiency.
   - [x] Build and deploy w/ nixpacks.

1. **Open Source Compliance**:

   - [x] Ensure REUSE compliance across the project.
   - [x] Add copyright notices and improve licensing transparency.

1. **SlapOS Integration**

   - [ ] Update POC to MVP

1. **Documentation Enhancements**:

   - [x] Review and update existing Architecture Decision Records (ADRs).
   - [ ] Improve and expand documentation for both developers and end-users.


### Version 1.3 (Q1 or Q2 2025)

#### Focus Areas:

1. **Modular Architecture**:

   - [ ] Develop and implement a plugin system to allow customizable integrations.
   - [ ] Introduce pluggable components for storage (e.g., S3, MinIO) and search (e.g., Typesense, Elasticsearch) (see: ADR 005).

1. **Enhanced Security**:

   - [ ] Overhaul authentication and permission systems with OpenID Connect (OIDC), SCIM, and RBAC (see: ADR 001, ADR 002, ADR 003).

1. **UI and UX Improvements**:

   - [ ] Finalize the adoption of modern UI technologies to enhance usability and responsiveness.

1. **Community Engagement**:

   - [ ] Foster an active contributor base through detailed onboarding guides, workshops, and governance transparency.

1. **Release Planning**:

   - [ ] Prepare a streamlined process for ongoing feature releases and updates.

#### Tasks

- [ ] Plugin architecture.
  - [ ] Pluggable search indexes (e.g. Typesense, ElasticSearch, etc.)
  - [ ] Pluggable file storage (e.g. S3, MinIO, etc.)
    - See: [ADR 005](../notes/adrs/005-storage.md)
- [ ] Overhaul of the authentication and permissions system.
  - See: [ADR 001](../notes/adrs/001-oidc.md), [ADR 002](../notes/adrs/002-scim.md), [ADR 003](../notes/adrs/003-rbac.md), [ADR 004](../notes/adrs/004-permissions.md).


### See also:

A significant part of shaping the future of Abilian SBE involves participating in the creation and review of **[Architecture Decision Records](../notes/adrs) (ADRs)**. These documents capture major architectural decisions and guide the project’s long-term technical direction.


## Completed Releases

### Version 1.1 (Q1 2024)

#### Tasks

- [x] Replace Celery with Dramatiq.
- [x] Make POC for SlapOS port of Abilian SBE (cf. [HyperOpen X](https://abilian.com/fr/recherche-developpement/hyper-open-x/) project).
- [x] Write some doc.
- [x] Upgrade some core dependencies: Flask, WTForms, etc.
- [x] POC for SlapOS port of Abilian SBE.

#### Achievements:

1. **Code Modernization**:

   - [x] Replaced Celery with Dramatiq for task management.
   - [x] Conducted a significant cleanup of unused code and imports.
   - [x] Transitioned to f-strings and type annotations for better readability and maintainability.
   - [x] Removal of unused legacy code:
     - `BaseCriterion`, `TextSearchCriterion`, `TextCriterion`, and `TagCriterion`.
   - [x] Simplification of inheritance hierarchies and `CBVs`.
   - [x] Clean-up of imports across the project and removal of obsolete monkey patches.
   - [x] Ensuring consistency with modern Python standards (PEP 8, PEP 484).
   - [x] Enhanced use of `black`, `isort`, and `ruff` to enforce code quality.

1. **Dependency Upgrades**:

   - [x] Upgraded Flask, WTForms, SQLAlchemy, and related libraries.
   - [x] Addressed deprecated dependencies and ensured compatibility with Python 3.12.

1. **Database Transition**:

   - [x] Moved to a PostgreSQL-first architecture, aligned with the HyperOpen X initiative.

1. **SlapOS Integration**:

   - [x] Developed a proof of concept (POC) for deploying Abilian SBE on SlapOS, paving the way for future compatibility with edge computing solutions.

1. **CI/CD Enhancements**:

   - [x] Improved test pipelines for faster execution and stability.
   - [x] Dropped support for Python 3.9 to focus on supported versions.

### Version 1.1.x (Q2 2024)

#### Achievements:

1. **Stabilization**:

   - [x] Incremental updates (1.1.6–1.1.10) to address bugs and improve stability.
   - [x] Streamlined dependency management with `Nix` for reproducible builds.

1. **Security**:

   - [x] Protected sensitive configurations and secrets.
   - [x] Addressed security vulnerabilities in outdated libraries.

1. **Documentation**:

   - [x] Enhanced developer documentation, including initial ADRs and improved README.

### Version 1.1.x (Q3 2024)

#### Achievements:

1. **Documentation Overhaul**:

   - [x] Introduced a detailed contribution guide to lower the barrier for new contributors.
   - [x] Expanded ADRs to cover architectural decisions comprehensively.

1. **Governance and Transparency**:

   - [x] Published governance documentation to improve project transparency and community involvement.

1. **Developer Experience**:

   - [x] Adoption of `Nix` for reproducible environments.
   - [x] Modernized CI/CD workflows for better developer productivity.

1. **Modularity Preparations**:

   - [x] Began groundwork for a pluggable architecture to support future extensibility.
