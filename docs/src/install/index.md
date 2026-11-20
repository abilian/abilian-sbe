# Installing Abilian SBE

Abilian SBE is a Python web application. It needs:

- **Python** 3.12 or later, managed with [uv](https://docs.astral.sh/uv/);
- a database: **PostgreSQL** or **MariaDB**, on an equal footing;
- **Redis**, for its task queue;
- for previews and search inside documents: **Poppler**, **ImageMagick** and **LibreOffice**;
- optionally, **ClamAV**, to scan uploaded files.

It runs as three processes: the web application, a worker for background tasks (conversions, e-mails, indexing) and a scheduler (the daily summary).

## Three ways to run it

- **[On Hop3](hop3.md)**, a platform that builds and runs the application, its database and its Redis from the repository: the shortest way to a production site.
- **[On a server](server.md)**, step by step, on a Debian or Ubuntu machine.
- **For development**, on your own machine: see the [developer guide](../develop/index.md).

Whichever you choose, [Configuration](configuration.md) lists the settings.

## Moving an existing site

A site keeps two things: its **database** and its **files**, the folder `data/files` of its instance. To move a site to a new server, restore a dump of the database, copy the files, then run `flask db upgrade`, which brings the schema up to date, and `flask reindex`, which rebuilds the search index from the database.
