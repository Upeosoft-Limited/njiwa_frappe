"""Turning what somebody typed into a number WhatsApp can reach.

People write a number the way they say it: 0712 345 678, (071) 234-5678,
+254 712 345 678. WhatsApp needs one form, so the punctuation comes off rather
than the number being refused for having it.

Nothing here guesses a country. The WooCommerce plugin can, because every
WooCommerce order carries a billing country; an ERPNext document does not, and
the country on a Customer's address is often the company's own. Njiwa already
reads a local number against the sending number's own country, which is the
same answer arrived at by somebody who knows, so a leading zero is passed
through as typed instead.
"""

from __future__ import annotations

import re

# How long an msisdn is, taken from Njiwa's own normalise.py. api.py repeats
# these for the test button so that button refuses a number for the same
# reason the API would; keeping the two in step matters more than either of
# them being clever.
MIN_MSISDN_DIGITS = 7
MAX_MSISDN_DIGITS = 15

# How a number is written down, and nothing else. A full stop is in here
# because people type 0712.345.678.
PUNCTUATION = re.compile(r"[\s+()\-.]")

# What separates one number from the next when somebody has typed several.
SEPARATORS = re.compile(r"[,;/\n\r]+")


def to_msisdn(raw: str | None) -> str:
    """One number, digits only, or '' when there is nothing usable.

    Everything that is not a phone number comes back empty, and that includes
    the one value that matters most: a JID ending @g.us is a WhatsApp *group*,
    and Njiwa reads it as one without looking at the rest. A number field
    holding a group would turn one submitted invoice into a message to
    hundreds of people from the shop's own number, so nothing but digits is
    ever allowed through.
    """
    number = PUNCTUATION.sub("", str(raw or ""))
    if not number:
        return ""

    # 00 is how much of the world dials out, and what is left is the whole
    # international number.
    if number.startswith("00"):
        number = number[2:]

    if not re.fullmatch(r"[0-9]+", number):
        return ""
    if not (MIN_MSISDN_DIGITS <= len(number) <= MAX_MSISDN_DIGITS):
        return ""

    return number


def first_msisdn(raw: str | None) -> str:
    """The first usable number in a field somebody has put several in.

    A Customer's Mobile No is one box, and people put two numbers in it:
    "0712345678 / 0722000111", or the same with a comma. Stripping the
    punctuation out of that and sending what is left would dial a number that
    belongs to nobody, so the field is split first and the first number that
    survives is the one used.
    """
    for piece in SEPARATORS.split(str(raw or "")):
        number = to_msisdn(piece)
        if number:
            return number
    return ""


def parse_list(raw: str | None) -> list[str]:
    """Several numbers typed by the shop owner, in the order they typed them.

    Separated by commas, semicolons, slashes or lines. Anything that is not a
    number is dropped rather than sent to, and a number typed twice is sent to
    once.
    """
    numbers: list[str] = []
    for piece in SEPARATORS.split(str(raw or "")):
        number = to_msisdn(piece)
        if number and number not in numbers:
            numbers.append(number)
    return numbers
