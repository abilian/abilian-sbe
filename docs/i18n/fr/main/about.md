# À propos

Abilian SBE (Social Business Engine) est développé par [Abilian](https://abilian.com/), une entreprise française qui conçoit et maintient des logiciels open source. Il est en production depuis 2013 comme extranet de pôles de compétitivité, de réseaux professionnels et d'associations.

## Licence

Abilian SBE est un logiciel libre, publié sous la [GNU Lesser General Public License, version 3](https://www.gnu.org/licenses/lgpl-3.0.html). Vous pouvez l'utiliser, l'étudier, le modifier et le partager, y compris au sein d'une application plus grande. Le projet suit la spécification [REUSE](https://reuse.software/) : `REUSE.toml` déclare le copyright et la licence de chaque fichier.

## Sa construction

Abilian SBE est écrit en Python, avec Flask et SQLAlchemy. Il stocke ses données dans PostgreSQL ou MariaDB. Ses pages sont rendues sur le serveur et mises en forme avec l'[Abilian Design System](https://git.sr.ht/~sfermigier/abilian-ds), avec un peu de JavaScript construit par Vite. Les tâches de fond (conversion des documents, e-mails, indexation) tournent sur Dramatiq, au-dessus de Redis ; la recherche repose sur Whoosh.

## Auteurs

- Stefane Fermigier (Abilian), fondateur et architecte
- Jérôme Dumonteil (Abilian), développeur principal
- Bertrand Mathieu, ancien développeur principal
- Vincent Dardel, Yvon Bourbotte et Ahmed Amine Hamrouni, anciens développeurs

## Code source

Le code source se trouve sur [GitHub](https://github.com/abilian/abilian-sbe-monorepo), où les tickets et les contributions sont les bienvenus. Le [guide du développeur](../develop/index.md) explique comment le construire et le tester.
