# About

Abilian SBE (Social Business Engine) is developed by [Abilian](https://abilian.com/), a French company that builds and supports open source software. It has run in production since 2013, as the extranet of clusters of companies, professional networks and associations.

## Licence

Abilian SBE is free software, licensed under the [GNU Lesser General Public License, version 3](https://www.gnu.org/licenses/lgpl-3.0.html). You may use it, study it, change it and share it, including as part of a larger application. The project follows the [REUSE](https://reuse.software/) specification: `REUSE.toml` declares the copyright and licence of every file.

## How it is built

Abilian SBE is written in Python, on Flask and SQLAlchemy, and stores its data in PostgreSQL or MariaDB. Its pages are rendered on the server and styled with the [Abilian Design System](https://git.sr.ht/~sfermigier/abilian-ds), with a little JavaScript built by Vite. Background work (document conversion, e-mails, indexing) runs on Dramatiq, over Redis; search runs on Whoosh.

## Authors

- Stefane Fermigier (Abilian), founder and architect
- Jérôme Dumonteil (Abilian), lead developer
- Bertrand Mathieu, past lead developer
- Vincent Dardel, Yvon Bourbotte and Ahmed Amine Hamrouni, past developers

## Source code

The source code is on [GitHub](https://github.com/abilian/abilian-sbe-monorepo), where issues and contributions are welcome. The [developer guide](../develop/index.md) explains how to build and test it.
