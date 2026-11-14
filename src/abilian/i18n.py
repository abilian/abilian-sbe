# Copyright (c) 2012-2024, Abilian SAS

"""I18n.

To mark strings for translation::

    from abilian.i18n import _
    _(u'message to translate')

Use :data:`_` for gettext, :data:`_l` for lazy_gettext, :data:`_n` for
ngettext.

:data:`Babel extension<babel>` support multiple translation paths. This
allows to add more catalogs to search for translations, in LIFO
order. This feature can be used to override some translations in a
custom application, be providing a catalog with messages to override::

    current_app.extensions['babel'].add_translations('abilian.core')

See :meth:`add_translations<Babel.add_translations>`.

To extract messages to build the message catalog template (.pot), use the
following "`-k`" parameters:

.. code-block:: bash

    $ pybabel extract -F babel.cfg -k "_n:1,2" -k "_l" -o "msg.pot" "src"


This can be made easier by placing in `setup.cfg`:

.. code-block:: ini

    [extract_messages]
    mapping_file = babel.cfg
    keywords = _n:1,2 _l
    output-file = msg.pot
    input-dirs = src


And just type:

.. code-block:: bash

    $ python setup.py extract_messages
"""

from __future__ import annotations

import importlib
import os
import re
import unicodedata
from datetime import datetime, tzinfo
from gettext import GNUTranslations
from pathlib import Path
from typing import TYPE_CHECKING, Any

import flask_babel
import pytz
from babel import Locale
from babel.dates import LOCALTZ, get_timezone, get_timezone_gmt
from babel.localedata import locale_identifiers
from babel.support import Translations as BaseTranslations
from flask import Flask, current_app, g, render_template, request
from flask_babel import (
    Babel as BabelBase,
    LazyString,
    force_locale,
    gettext,
    lazy_gettext,
    ngettext,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

__all__ = [
    "VALID_LANGUAGES_CODE",
    "_",
    "_l",
    "_n",
    "babel",
    "get_default_locale",
    "gettext",
    "lazy_country_name",
    "lazy_gettext",
    "localeselector",
    "ngettext",
    "render_template_i18n",
    "timezoneselector",
]

#: gettext alias
_ = gettext
if TYPE_CHECKING:

    def _l(string: str, **variables: Any) -> str:
        """lazy_gettext, typed as returning the `str` it stands for.

        Its `LazyString` translates itself when used and passes every string
        operation through, so it goes wherever a `str` is expected: form labels,
        titles and the like.
        """

else:
    #: lazy_gettext alias
    _l = lazy_gettext
#: ngettext alias
_n = ngettext

#: accepted languages codes
VALID_LANGUAGES_CODE = frozenset(
    _lang for _lang in locale_identifiers() if len(_lang) == 2
)


def get_default_locale() -> Locale:
    return current_app.extensions["babel"].default_locale


def _get_locale() -> Locale:
    locale = flask_babel.get_locale()
    if locale is None:
        locale = get_default_locale()
    return locale


def _gettext_territory(code):
    locale = _get_locale()
    return locale.territories.get(code) or get_default_locale().territories.get(code)


#: get localized territory name
def country_name(code):
    return _gettext_territory(code)


#: lazy version of :func:`country_name`
def lazy_country_name(code):
    return LazyString(_gettext_territory, code)


def default_country() -> str:
    return current_app.config.get("DEFAULT_COUNTRY", "")


def country_choices(
    first: str = "", default_country_first: bool = True
) -> list[tuple[str, str]]:
    """Return a list of (code, countries), alphabetically sorted on localized
    country name.

    :param first: Country code to be placed at the top
    :param default_country_first:
    :type default_country_first: bool
    """
    locale = _get_locale()
    territories = [
        (code, name) for code, name in locale.territories.items() if len(code) == 2
    ]  # skip 3-digit regions

    if first == "" and default_country_first:
        first = default_country()

    def sortkey(item: tuple[str, str]) -> str:
        if first is not None and item[0] == first:
            return "0"
        return to_lower_ascii(item[1])

    territories.sort(key=sortkey)
    return territories


def supported_app_locales() -> Iterator[tuple[Locale, str]]:
    """Language codes and labels supported by current application.

    :return: an iterable of `(:class:`babel.Locale`, label)`, label being the
    locale language human name in current locale.
    """
    locale = _get_locale()
    codes = current_app.config["BABEL_ACCEPT_LANGUAGES"]
    return ((Locale.parse(code), locale.languages.get(code, code)) for code in codes)


def timezones_choices():
    """Timezones values and their labels for current locale.

    :return: an iterable of `(code, label)`, code being a timezone code and label
    the timezone name in current locale.
    """
    utcnow = pytz.utc.localize(datetime.utcnow())
    locale = _get_locale()
    for tz in sorted(pytz.common_timezones):
        tz = get_timezone(tz)
        now = tz.normalize(utcnow.astimezone(tz))
        label = f"({get_timezone_gmt(now, locale=locale)}) {tz.zone}"
        yield (tz, label)  # get_timezone_name(tz, locale=locale))


class Babel(BabelBase):
    """Allow to load translations from other modules."""

    _translations_paths: list[tuple[str, str]]

    def init_app(
        self,
        app: Flask,
        locale_selector: Callable | None = None,
        timezone_selector: Callable | None = None,
    ) -> None:
        if locale_selector is None:
            locale_selector = localeselector
        if timezone_selector is None:
            timezone_selector = timezoneselector
        if hasattr(self, "localeselector"):
            # Old Babel version
            super().init_app(app)
            self.localeselector(locale_selector)
            self.timezoneselector(timezone_selector)
        else:
            # recent Babel version
            super().init_app(
                app,
                locale_selector=locale_selector,
                timezone_selector=timezone_selector,
            )
        assert app.root_path
        self._translations_paths = [
            (os.path.join(app.root_path, "translations"), "messages")
        ]

    def add_translations(
        self,
        module_name: str,
        translations_dir: str = "translations",
        domain: str = "messages",
    ) -> None:
        """Add translations from external module.

        For example::

            babel.add_translations('abilian.core')

        Will add translations files from `abilian.core` module.
        """
        module = importlib.import_module(module_name)
        for path in (Path(p, translations_dir) for p in module.__path__):
            if not (path.exists() and path.is_dir()):
                continue

            if not os.access(str(path), os.R_OK):
                self.app.logger.warning(
                    "Babel translations: read access not allowed {path}, skipping.",
                    path=str(path),
                )
                continue

            self._translations_paths.append((str(path), domain))


class Translations(BaseTranslations):
    """Merge only non-empty translations.

    This avoids having uncomplete catalog that "clear" existing
    translations, when used with :func:`_get_translations_multi_paths`.
    """

    def merge(self, translations: Translations) -> Translations:
        if isinstance(translations, GNUTranslations):
            for msgkey, msgstr in translations._catalog.items():
                msgid = msgkey

                if isinstance(msgkey, tuple):
                    msgid = msgkey[0]

                msgstr = msgstr.strip()
                if msgkey in self._catalog and (msgid == msgstr):
                    # when msgstr is empty, compile_catalog sets msgstr = msgid
                    # so this is probable an existing translation that would
                    # be "erased" by msgid string: skip it.

                    # logger.debug('Catalog: %r, skip msgkey: %r, existing: %r',
                    # translations, msgkey, self._catalog[msgkey])
                    continue

                self._catalog[msgkey] = msgstr

            if isinstance(translations, BaseTranslations):
                self.files.extend(translations.files)

        return self


def _get_translations_multi_paths() -> Translations | None:
    """Return the correct gettext translations that should be used for this
    request.

    This will never fail and return a dummy translation object if used
    outside of the request or if a translation cannot be found.
    """
    if not request:
        return None

    translations = getattr(g, "babel_translations", None)
    if translations is None:
        babel_ext = current_app.extensions["babel"]
        translations = None
        trs = None

        # reverse order: thus the application catalog is loaded last, so that
        # translations from libraries can be overriden
        for dirname, domain in reversed(babel_ext._translations_paths):
            trs = Translations.load(
                dirname, locales=[flask_babel.get_locale()], domain=domain
            )

            # babel.support.Translations is a subclass of
            # babel.support.NullTranslations, so we test if object has a 'merge'
            # method

            if not trs or not hasattr(trs, "merge"):
                # got None or NullTranslations instance
                continue

            if translations is not None and hasattr(translations, "merge"):
                translations.merge(trs)
            else:
                translations = trs

        # ensure translations is at least a NullTranslations object
        if translations is None:
            translations = trs

        g.babel_translations = translations

    return translations


# monkey patch flask-babel
flask_babel.get_translations = _get_translations_multi_paths

#: importable instance of :class:`Babel`
babel = Babel()


def localeselector() -> str | None:
    """Default locale selector used in abilian applications."""
    # if a user is logged in, use the locale from the user settings
    user = getattr(g, "user", None)
    if user is not None:
        locale = getattr(user, "locale", None)
        if locale:
            return locale

    # Otherwise, try to guess the language from the user accept header the browser
    # transmits.  By default we support en/fr. The best match wins.
    return request.accept_languages.best_match(
        current_app.config["BABEL_ACCEPT_LANGUAGES"]
    )


def timezoneselector() -> tzinfo:
    """Default timezone selector used in abilian applications."""
    return LOCALTZ


def get_template_i18n(template_name: str, locale: Locale) -> list[str]:
    """Build template list with preceding locale if found."""
    if locale is None:
        return [template_name]

    template_list = []
    parts = template_name.rsplit(".", 1)
    root = parts[0]
    suffix = parts[1]

    if locale.territory is not None:
        locale_string = f"{locale.language}_{locale.territory}"
        localized_template_path = f"{root}.{locale_string}.{suffix}"
        template_list.append(localized_template_path)

    localized_template_path = f"{root}.{locale.language}.{suffix}"
    template_list.append(localized_template_path)

    # append the default
    template_list.append(template_name)
    return template_list


class ensure_request_context:
    """Context manager that ensures a request context is set up."""

    _rq_ctx = None

    def __enter__(self):
        if not request:
            ctx = self._rq_ctx = current_app.test_request_context()
            ctx.__enter__()

    def __exit__(self, *args: object):
        ctx = self._rq_ctx
        self._rq_ctx = None

        if ctx is not None:
            ctx.__exit__(*args)


def render_template_i18n(template_name_or_list: str, **context: Any) -> str:
    """Try to build an ordered list of template to satisfy the current
    locale."""
    template_list: list[str] = []
    # Use locale if present in **context
    if "locale" in context:
        locale = Locale.parse(context["locale"])
    else:
        # Use get_locale() or default_locale
        locale = flask_babel.get_locale()

    if isinstance(template_name_or_list, str):
        template_list = get_template_i18n(template_name_or_list, locale)
    else:
        # Search for locale for each member of the list, do not bypass
        for template in template_name_or_list:
            template_list.extend(get_template_i18n(template, locale))

    with ensure_request_context(), force_locale(locale):
        return render_template(template_list, **context)


_NOT_WORD_RE = re.compile(r"[^\w\s]+", flags=re.UNICODE)


def to_lower_ascii(value: str) -> str:
    value = str(value)
    value = _NOT_WORD_RE.sub(" ", value)
    value = unicodedata.normalize("NFKD", value)
    value_b = value.encode("ascii", "ignore")
    value = value_b.decode("ascii")
    value = value.strip().lower()
    value = re.sub(r"[_\s]+", " ", value)
    return value
