# Installer Abilian SBE

Abilian SBE est une application web en Python. Il lui faut :

- **Python** 3.12 ou plus récent, géré avec [uv](https://docs.astral.sh/uv/) ;
- une base de données : **PostgreSQL** ou **MariaDB**, à égalité ;
- **Redis**, pour sa file de tâches ;
- pour les aperçus et la recherche dans les documents : **Poppler**, **ImageMagick** et **LibreOffice** ;
- en option, **ClamAV**, pour analyser les fichiers déposés.

Il tourne sous la forme de trois processus : l'application web, un *worker* pour les tâches de fond (conversions, e-mails, indexation) et un ordonnanceur (le résumé quotidien).

## Trois façons de le faire tourner

- **[Sur Hop3](hop3.md)**, une plateforme qui exécute l'application à partir de son paquet PyPI, avec sa base de données et son Redis : le chemin le plus court vers un site en production.
- **[Sur un serveur](server.md)**, pas à pas, sur une machine Debian ou Ubuntu.
- **Pour le développement**, sur votre propre machine : voir le [guide du développeur](../develop/index.md).

Quel que soit votre choix, [Configuration](configuration.md) liste les paramètres.

## Déplacer un site existant

Un site conserve deux choses : sa **base de données** et ses **fichiers**, le dossier `data/files` de son instance. Pour déplacer un site vers un nouveau serveur, restaurez une sauvegarde de la base de données, copiez les fichiers, puis lancez `flask db upgrade` pour mettre le schéma à jour et `flask reindex` pour reconstruire l'index de recherche à partir de la base de données.
