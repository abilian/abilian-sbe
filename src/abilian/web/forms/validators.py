# Copyright (c) 2012-2024, Abilian SAS

"""Validators.

TODO: most of this is currently only stubs and needs to be implemented.

NOTE: the `rule` property is supposed to be useful for generating client-side
validation code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import Image
from wtforms import Field, Form, validators

from abilian.i18n import _, _n
from abilian.services import get_service

if TYPE_CHECKING:
    from collections.abc import Callable

    from werkzeug.datastructures import FileStorage

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg")
IMAGE_FORMATS = ("PNG", "JPEG")

__all__ = (
    "VALIDATORS",
    "anyof",
    "email",
    "equalto",
    "flaghidden",
    "ipaddress",
    "length",
    "macaddress",
    "noneof",
    "numberrange",
    "open_png_or_jpeg",
    "optional",
    "regexp",
    "renderempty",
    "required",
    "siret",
    "siret_validator",
    "url",
    "uuid",
)


class Rule:
    @property
    def rule(self) -> None:
        return None


class Email(validators.Email):
    def __call__(self, form, field):
        if self.message is None:
            self.message = field.gettext("Invalid email address.")

        if field.data:
            super().__call__(form, field)

    @property
    def rule(self):
        return {"email": True}


class CorrectInputRequired(validators.DataRequired):
    def __call__(self, form: Form, field: Field):
        if (
            field.data is None
            or (isinstance(field.data, str) and not field.data.strip())
            or (isinstance(field.data, (list, dict)) and not field.data)
        ):
            if self.message is None:
                message = field.gettext("This field is required.")
            else:
                message = self.message

            field.errors[:] = []
            raise validators.StopValidation(message)


class Required(CorrectInputRequired):
    field_flags = {"required": True}

    @property
    def rule(self):
        return {"required": True}


class EqualTo(validators.EqualTo, Rule):
    pass


class Length(Rule):
    """Validates the length of a string.

    :param min: The minimum required length of the string. If not provided, minimum
    length will not be checked.

    :param max:  The maximum length of the string. If not provided, maximum length
    will not be checked.

    :param message: Error message to raise in case of a validation error. Can be
    interpolated using `%(min)d` and `%(max)d` if desired. Useful defaults are
    provided depending on the existence of min and max.
    """

    def __init__(self, min=-1, max=-1, message=None) -> None:
        assert min != -1 or max != -1, (
            "At least one of `min` or `max` must be specified."
        )
        assert max == -1 or min <= max, "`min` cannot be more than `max`."
        self.min = min
        self.max = max
        self.message = message

    def __call__(self, form, field):
        field_data_length = len(field.data) if field.data else 0

        if field_data_length < self.min or (
            self.max != -1 and field_data_length > self.max
        ):
            message = self.message
            if message is None:
                if self.max == -1:
                    message = _n(
                        "Field must be at least %(min)d character long.",
                        "Field must be at least %(min)d characters long.",
                        self.min,
                        min=self.min,
                    )
                elif self.min == -1:
                    message = _n(
                        "Field cannot be longer than %(max)d character.",
                        "Field cannot be longer than %(max)d characters.",
                        self.max,
                        max=self.max,
                    )
                else:
                    message = _(
                        "Field must be between %(min)d and %(max)d characters long.",
                        min=self.min,
                        max=self.max,
                    )
            raise validators.ValidationError(
                message
                % {"min": self.min, "max": self.max, "length": field_data_length}
            )


class NumberRange(validators.NumberRange, Rule):
    pass


class Optional(validators.Optional, Rule):
    pass


class Regexp(validators.Regexp, Rule):
    pass


class IPAddress(validators.IPAddress, Rule):
    pass


class MacAddress(validators.MacAddress, Rule):
    pass


class URL(validators.URL):
    @property
    def rule(self):
        return {"url": True}


class UUID(validators.UUID, Rule):
    pass


class AnyOf(validators.AnyOf, Rule):
    pass


class NoneOf(validators.NoneOf, Rule):
    pass


class FlagHidden(Rule):
    """Flag the field as hidden."""

    field_flags = {"hidden": True}

    def __call__(self, form, field):
        pass


class AntiVirus(Rule):
    """Check content for viruses."""

    field_flags = {"antivirus": True}

    def __call__(self, form, field):
        service = get_service("antivirus")
        if not service:
            return

        res = service.scan(field.data)
        if res is False:
            raise validators.ValidationError(_("Virus detected!"))


class RenderEmpty:
    """Force display."""

    field_flags = {"render_empty": True}

    def __call__(self, form, field):
        pass


class SIRET(RenderEmpty):
    pass


def luhn(n: str) -> bool:
    """Validate that a string made of numeric characters verify Luhn test. Used
    by siret validator.

    from
    http://rosettacode.org/wiki/Luhn_test_of_credit_card_numbers#Python
    https://en.wikipedia.org/wiki/Luhn_algorithm
    """
    r = [int(ch) for ch in str(n)][::-1]
    return (sum(r[0::2]) + sum(sum(divmod(d * 2, 10)) for d in r[1::2])) % 10 == 0


# specific SIRET like for MONACO, i.e MONACOCONFO001
# -  Principauté de Monaco "001"
# - la Guadeloupe "458"
# - la Martinique "462"
# - la Guyane "496"
# - la Réunion "372
SIRET_CODES = ("001", "458", "462", "496", "372")


def siret_validator() -> Callable:
    """Validate a SIRET: check its length (14), its final code, and pass it
    through the Luhn algorithm."""

    def _validate_siret(form: Form, field: Field, siret: str = "") -> None:
        """SIRET validator.

        A WTForm validator wants a form and a field as parameters. We
        also want to give directly a siret, for a scripting use.
        """
        if field is not None:
            siret = (field.data or "").strip()

        if len(siret) != 14:
            msg = _("SIRET must have exactly 14 characters ({count})").format(
                count=len(siret)
            )
            raise validators.ValidationError(msg)

        if not all(("0" <= c <= "9") for c in siret):
            if not siret[-3:] in SIRET_CODES:
                msg = _(
                    "SIRET looks like special SIRET but geographical "
                    "code seems invalid (%(code)s)",
                    code=siret[-3:],
                )
                raise validators.ValidationError(msg)

        elif not luhn(siret):
            msg = _("SIRET number is invalid (length is ok: verify numbers)")
            raise validators.ValidationError(msg)

    return _validate_siret


# These are the canonical names that should be used.
equalto = EqualTo


def open_png_or_jpeg(data: FileStorage) -> Image.Image:
    """Decode an uploaded PNG or JPEG image, or raise a validation error.

    The format is read from the decoded image itself: the filename is checked
    too, but only because it is what the user sees.
    """
    not_accepted = _("Only PNG or JPG image files are accepted")
    if not data.filename or not data.filename.lower().endswith(IMAGE_EXTENSIONS):
        raise validators.ValidationError(not_accepted)

    try:
        image = Image.open(data)
        image.load()
    except Exception as e:
        raise validators.ValidationError(_("Could not decode image file")) from e
    if image.format not in IMAGE_FORMATS:
        raise validators.ValidationError(not_accepted)

    data.seek(0)
    return image


length = Length
numberrange = NumberRange
optional = Optional
required = Required
regexp = Regexp
email = Email
ipaddress = IPAddress
macaddress = MacAddress
url = URL
siret = SIRET
uuid = UUID
anyof = AnyOf
noneof = NoneOf
flaghidden = FlagHidden
renderempty = RenderEmpty

VALIDATORS = {
    "email": email,
    "url": url,
    "uuid": uuid,
    "renderempty": renderempty,
    "siret": siret,
    "required": required,
    "optional": optional,
}
