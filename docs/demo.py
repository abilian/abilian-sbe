# Copyright (c) 2026, Abilian SAS

"""Demo data for the documentation's screenshots, in English or French.

Run by shots.py through `flask script` on a throwaway instance, so it executes
inside the app context. `DEMO_LANG` picks the language (`en` or `fr`) and
`DEMO_OUT` the JSON file where it writes what the screenshots need: the
communities' slugs and a few ids.

People, communities and content are invented, and the same in both languages:
only the words change. Dates are relative to now, so the feed reads "2 hours
ago" whenever the screenshots are taken.
"""

from __future__ import annotations

import io
import json
import os
from datetime import datetime, timedelta

from PIL import Image, ImageDraw

from abilian.core.extensions import db
from abilian.core.models.subjects import User
from abilian.sbe.apps.calendar.models import Event
from abilian.sbe.apps.communities.models import (
    MANAGER,
    MEMBER,
    ON_REQUEST,
    OPEN,
    Community,
)
from abilian.sbe.apps.forum.models import Thread
from abilian.sbe.apps.wiki.models import WikiPage
from abilian.services import get_service
from abilian.services.activity.models import ActivityEntry
from abilian.services.security import ADMIN, security

LANG = os.environ.get("DEMO_LANG", "en")
OUT = os.environ["DEMO_OUT"]
NOW = datetime.utcnow().replace(microsecond=0)

#: Who appears, in both languages: first name, last name, job title and
#: organisation by language. The first one is the person the screenshots show
#: signed in.
PEOPLE = [
    ("Camille", "Martin", {"en": "Coordinator", "fr": "Coordinatrice"}),
    ("Léa", "Dubois", {"en": "Project manager", "fr": "Cheffe de projet"}),
    ("Thomas", "Bernard", {"en": "CTO", "fr": "Directeur technique"}),
    ("Sophie", "Laurent", {"en": "Lawyer", "fr": "Juriste"}),
    ("Karim", "Haddad", {"en": "Developer", "fr": "Développeur"}),
    ("Julie", "Moreau", {"en": "Communications", "fr": "Chargée de communication"}),
    ("Antoine", "Petit", {"en": "Founder", "fr": "Fondateur"}),
    ("Nadia", "Benali", {"en": "Treasurer", "fr": "Trésorière"}),
    ("Hugo", "Lefèvre", {"en": "Consultant", "fr": "Consultant"}),
    ("Emma", "Rousseau", {"en": "Events", "fr": "Événementiel"}),
]
ORGANISATIONS = ["Libre Cluster", "Acme Open", "Datalibre", "Coop Numérique"]

T = {
    "en": {
        "board": ("Board", "Decisions, meeting agendas and public positions."),
        "procurement": (
            "Public procurement",
            "Working group on open source in public tenders.",
        ),
        "comms": ("Communication", "Newsletter, website and social media."),
        "events": ("Events", "Organising the annual conference and meetups."),
        "training": ("Training", "Courses and workshops for members, open to all."),
        "threads": [
            (
                "board",
                "Agenda for the general assembly",
                "<p>Here is a first draft of the agenda. Anything to add before Friday?</p>",
                [
                    "<p>Could we add ten minutes on the membership fees?</p>",
                    "<p>Added. I also moved the budget vote before lunch.</p>",
                    "<p>Thanks, it reads well.</p>",
                ],
            ),
            (
                "procurement",
                "Answer to the consultation on public software procurement",
                "<p>The consultation closes at the end of the month. I suggest we answer as a group, from the notes of our last meeting.</p>",
                [
                    "<p>Agreed. I can draft the part on reversibility.</p>",
                    "<p>I will take the section on licences.</p>",
                ],
            ),
            (
                "comms",
                "Newsletter for December",
                "<p>Three topics so far: the conference, the new members, the procurement report. Other ideas?</p>",
                ["<p>A word on the training sessions in January?</p>"],
            ),
            (
                "board",
                "Budget 2027: first figures",
                "<p>The first figures are in the spreadsheet in the Finance folder.</p>",
                [],
            ),
        ],
        "folders": {"minutes": "Meeting minutes", "finance": "Finance"},
        "documents": [
            ("board", "minutes", "Minutes - Board meeting, November.pdf"),
            ("board", "minutes", "Minutes - Board meeting, October.pdf"),
            ("board", "finance", "Budget 2027.xlsx"),
            ("board", None, "Statutes.pdf"),
            ("board", None, "Membership form.docx"),
            ("procurement", None, "Report on public procurement.docx"),
            ("comms", None, "Conference poster.png"),
        ],
        "wiki": [
            (
                "Home",
                "# Welcome to the board's wiki\n\nWhat the board decided, and how it works.\n\n- [[How we work]]\n- [[Onboarding]]\n",
            ),
            (
                "How we work",
                "## Meetings\n\nThe board meets on the first Tuesday of the month. The agenda is posted a week before, in **Discussions**.\n\n## Decisions\n\nDecisions are recorded in the minutes, in **Documents**.\n",
            ),
            (
                "Onboarding",
                "## Your first week\n\n1. Read [[How we work]].\n2. Introduce yourself in Discussions.\n3. Ask Camille for access to the shared folders.\n",
            ),
        ],
        "calendar": [
            ("board", "Board meeting", 2, 10, "Room 2, Paris"),
            ("board", "General assembly", 9, 14, "Maison des associations"),
            ("events", "Open source conference", 21, 9, "Paris"),
            ("procurement", "Working group call", 4, 11, "Online"),
        ],
    },
    "fr": {
        "board": (
            "Bureau",
            "Décisions, ordres du jour des réunions, positions publiques.",
        ),
        "procurement": (
            "Commande publique",
            "Groupe de travail sur le logiciel libre dans les marchés publics.",
        ),
        "comms": (
            "Communication",
            "Lettre d'information, site web et réseaux sociaux.",
        ),
        "events": ("Événements", "Organisation du congrès annuel et des rencontres."),
        "training": (
            "Formation",
            "Cours et ateliers pour les membres, ouverts à tous.",
        ),
        "threads": [
            (
                "board",
                "Ordre du jour de l'assemblée générale",
                "<p>Voici une première version de l'ordre du jour. Des ajouts avant vendredi ?</p>",
                [
                    "<p>Peut-on ajouter dix minutes sur les cotisations ?</p>",
                    "<p>C'est ajouté. J'ai aussi avancé le vote du budget avant le déjeuner.</p>",
                    "<p>Merci, c'est très clair.</p>",
                ],
            ),
            (
                "procurement",
                "Réponse à la consultation sur la commande publique de logiciels",
                "<p>La consultation se termine à la fin du mois. Je propose une réponse commune, à partir des notes de notre dernière réunion.</p>",
                [
                    "<p>D'accord. Je peux rédiger la partie sur la réversibilité.</p>",
                    "<p>Je prends la section sur les licences.</p>",
                ],
            ),
            (
                "comms",
                "Lettre d'information de décembre",
                "<p>Trois sujets pour l'instant : le congrès, les nouveaux membres, le rapport sur la commande publique. D'autres idées ?</p>",
                ["<p>Un mot sur les formations de janvier ?</p>"],
            ),
            (
                "board",
                "Budget 2027 : premiers chiffres",
                "<p>Les premiers chiffres sont dans le tableur du dossier Finances.</p>",
                [],
            ),
        ],
        "folders": {"minutes": "Comptes rendus", "finance": "Finances"},
        "documents": [
            ("board", "minutes", "Compte rendu - Bureau de novembre.pdf"),
            ("board", "minutes", "Compte rendu - Bureau d'octobre.pdf"),
            ("board", "finance", "Budget 2027.xlsx"),
            ("board", None, "Statuts.pdf"),
            ("board", None, "Bulletin d'adhésion.docx"),
            ("procurement", None, "Rapport sur la commande publique.docx"),
            ("comms", None, "Affiche du congrès.png"),
        ],
        "wiki": [
            (
                "Accueil",
                "# Bienvenue sur le wiki du bureau\n\nCe que le bureau a décidé, et comment il fonctionne.\n\n- [[Notre fonctionnement]]\n- [[Arrivée d'un membre]]\n",
            ),
            (
                "Notre fonctionnement",
                "## Réunions\n\nLe bureau se réunit le premier mardi du mois. L'ordre du jour est publié une semaine avant, dans **Discussions**.\n\n## Décisions\n\nLes décisions sont consignées dans les comptes rendus, dans **Documents**.\n",
            ),
            (
                "Arrivée d'un membre",
                "## Votre première semaine\n\n1. Lisez [[Notre fonctionnement]].\n2. Présentez-vous dans Discussions.\n3. Demandez à Camille l'accès aux dossiers partagés.\n",
            ),
        ],
        "calendar": [
            ("board", "Réunion du bureau", 2, 10, "Salle 2, Paris"),
            ("board", "Assemblée générale", 9, 14, "Maison des associations"),
            ("events", "Congrès du logiciel libre", 21, 9, "Paris"),
            ("procurement", "Réunion du groupe de travail", 4, 11, "En ligne"),
        ],
    },
}[LANG]


def picture(colour: str, accent: str) -> bytes:
    """A small image, so a document has a thumbnail without any converter."""
    image = Image.new("RGB", (640, 400), colour)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 260, 640, 400), fill=accent)
    draw.ellipse((420, 60, 560, 200), fill="#ffffff")
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


def activity(actor: User, verb: str, obj, community: Community, when: datetime) -> None:
    db.session.add(
        ActivityEntry(
            actor=actor,
            verb=verb,
            object=obj,
            object_type=obj.entity_type,
            target=community,
            target_type=community.entity_type,
            happened_at=when,
        )
    )


def owned(obj, user: User, when: datetime):
    obj.creator = obj.owner = user
    obj.created_at = when
    return obj


# People
people = []
for n, (first, last, titles) in enumerate(PEOPLE):
    user = User(
        first_name=first,
        last_name=last,
        email=f"{first}.{last}@example.org".lower().replace("é", "e").replace("è", "e"),
        job_title=titles[LANG],
        organization=ORGANISATIONS[n % len(ORGANISATIONS)],
        can_login=True,
        locale=LANG,
        last_active=NOW - timedelta(hours=n * 5),
    )
    db.session.add(user)
    people.append(user)
db.session.flush()
camille = people[0]
camille.set_password("demo-password")
# Camille is a member like any other: the screenshots show what a member sees.
# Antoine runs the site, for the administration's screenshot.
antoine = people[6]
antoine.set_password("demo-password")
security.grant_role(antoine, ADMIN)

# Communities: Camille runs the board and the procurement group, and is a member
# of communication. She is in neither events, open on request, nor training,
# open to all: those are the two she can discover.
KEYS = ("board", "procurement", "comms", "events", "training")
#: Who runs each community besides Camille, by index in PEOPLE.
MANAGERS = {"board": 6, "procurement": 3, "comms": 5, "events": 9, "training": 8}
communities = {}
for key in KEYS:
    name, description = T[key]
    community = Community(name=name, description=description, type="participative")
    db.session.add(community)
    db.session.flush()
    communities[key] = community
communities["events"].visibility = ON_REQUEST
communities["training"].visibility = OPEN
for key, role in (("board", MANAGER), ("procurement", MANAGER), ("comms", MEMBER)):
    communities[key].set_membership(camille, role)
for n, person in enumerate(people[1:], start=1):
    for c, key in enumerate(KEYS):
        if MANAGERS[key] == n:
            communities[key].set_membership(person, MANAGER)
        elif (n + c) % 3 != 0:
            communities[key].set_membership(person, MEMBER)
db.session.commit()

# Discussions, each with its replies, the latest a few hours ago.
threads = []
for n, (key, title, body, replies) in enumerate(T["threads"]):
    community = communities[key]
    started = NOW - timedelta(days=3 - n * 0.6, hours=2)
    author = people[1 + n % 4]
    thread = owned(Thread(title=title, community=community), author, started)
    db.session.add(thread)
    owned(thread.create_post(body_html=body), author, started)
    activity(author, "post", thread, community, started)
    for m, reply in enumerate(replies):
        when = started + timedelta(hours=3 + m * 5)
        replier = people[(m + n + 2) % len(people)]
        owned(thread.create_post(body_html=reply), replier, when)
        activity(replier, "post", thread, community, when)
    thread.updated_at = thread.last_post_at = thread.posts[-1].created_at
    threads.append(thread)
db.session.commit()

# Documents, a few in folders, all as images so that each has a thumbnail.
folders = {}
for key in ("minutes", "finance"):
    folder = communities["board"].folder.create_subfolder(T["folders"][key])
    owned(folder, camille, NOW - timedelta(days=30))
    folders[key] = folder
colours = ["#066fd1", "#00808a", "#c2405b", "#6a4fb8", "#a35f10", "#3b7d46", "#4a6175"]
documents = []
for n, (key, folder_key, title) in enumerate(T["documents"]):
    community = communities[key]
    parent = folders[folder_key] if folder_key else community.folder
    doc = parent.create_document(title=title)
    doc.set_content(picture(colours[n], "#f59e0b"), "image/png")
    when = NOW - timedelta(days=n * 1.5, hours=4)
    owned(doc, people[n % 5], when)
    doc.updated_at = when
    activity(people[n % 5], "post", doc, community, when)
    documents.append(doc)
db.session.commit()

# The board's wiki.
for n, (title, body) in enumerate(T["wiki"]):
    page = WikiPage(title=title, body_src=body, community=communities["board"])
    owned(page, people[n], NOW - timedelta(days=10 - n))
    page.updated_at = page.revisions[0].created_at = NOW - timedelta(days=4 - n)
    db.session.add(page)
    activity(people[n], "post", page, communities["board"], NOW - timedelta(days=4 - n))
db.session.commit()

# Events to come.
events = []
for key, title, days, hour, location in T["calendar"]:
    start = (NOW + timedelta(days=days)).replace(hour=hour, minute=0, second=0)
    event = Event(
        title=title,
        community=communities[key],
        start=start,
        end=start + timedelta(hours=2),
        location=location,
        description=f"<p>{title}.</p>",
    )
    owned(event, camille, NOW - timedelta(days=1))
    db.session.add(event)
    events.append(event)
db.session.commit()

# Each community's last activity is its latest entry, not the time of the seed.
for community in communities.values():
    latest = (
        ActivityEntry.query.filter(ActivityEntry.target_id == community.id)
        .order_by(ActivityEntry.happened_at.desc())
        .first()
    )
    community.last_active_at = latest.happened_at if latest else NOW - timedelta(days=6)
db.session.commit()

# What Camille has read: what came in the last day is new to her.
get_service("preferences").set_preferences(
    camille, **{"feed:read_until": (NOW - timedelta(days=3)).isoformat()}
)
db.session.commit()

with open(OUT, "w", encoding="utf-8") as out:
    json.dump(
        {
            "email": camille.email,
            "admin": antoine.email,
            "password": "demo-password",
            "communities": {k: c.slug for k, c in communities.items()},
            "thread": threads[0].id,
            "document": documents[0].id,
            "wiki": T["wiki"][1][0],
            "event": events[1].id,
        },
        out,
    )
print(f"demo data ({LANG}) for {camille.email}")
