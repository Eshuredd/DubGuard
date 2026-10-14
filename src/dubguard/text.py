"""Deliberately narrow normalization and auditable numeric parsing."""

from dataclasses import dataclass
from fractions import Fraction
import re
import unicodedata


def normalize(text: str) -> str:
    # Keep punctuation inside a sentence, decimal points, signs, and unit symbols.
    # Preserve case of tokens following a numeral: SI prefix case can change a
    # quantity by orders of magnitude (MPa versus mPa). Numeric rules explicitly
    # handle supported aliases; generic case folding must not clear these.
    text = re.sub(r"(?<=\d)(\s*[°]?\s*)([A-Za-z]+)",
                  lambda m: m.group(1) + "<unit:" + "_".join(str(ord(c)) for c in m.group(2)) + ">", text)
    # A question mark may change an imperative into an uncertain question.
    return " ".join(unicodedata.normalize("NFC", text).casefold().split()).rstrip(".!")


# dimension, multiplier, offset into a common base unit; exact rational arithmetic.
UNITS: dict[str, tuple[str, Fraction, Fraction]] = {}


def _units(names: str, dimension: str, scale=1, offset=0) -> None:
    for name in names.split("|"):
        UNITS[name] = (dimension, Fraction(scale), Fraction(offset))


_units("s|sec|secs|second|seconds", "time")
_units("min|mins|minute|minutes", "time", 60)
_units("h|hr|hrs|hour|hours", "time", 3600)
_units("°c|° c|c|celsius|degrees celsius", "temperature", 1, Fraction(27315, 100))
_units("°f|° f|f|fahrenheit|degrees fahrenheit", "temperature", Fraction(5, 9), Fraction(45967, 180))
_units("k|kelvin", "temperature")
_units("pa|pascal|pascals", "pressure")
_units("kpa", "pressure", 1000)
_units("mpa", "pressure", 1000000)
_units("bar", "pressure", 100000)
_units("psi", "pressure", Fraction("6894.757293168"))
_units("m|meter|meters|metre|metres", "length")
_units("cm", "length", Fraction(1, 100))
_units("mm", "length", Fraction(1, 1000))
_units("inch|inches|in", "length", Fraction("0.0254"))
_units("kg|kilogram|kilograms", "mass")
_units("g|gram|grams", "mass", Fraction(1, 1000))
_units("%|percent", "percentage")
_units("rpm", "rotation")
_units("v|volt|volts", "voltage")
_units("a|amp|amps|ampere|amperes", "current")

NUMBER = r"[-+]?(?:\d+(?:\.\d+)?|\.\d+)"
UNIT = "|".join(re.escape(u) for u in sorted(UNITS, key=len, reverse=True))
OPERATORS = {
    "at or below": "<=", "at most": "<=", "no more than": "<=", "up to": "<=",
    "below": "<", "less than": "<", "under": "<",
    "at or above": ">=", "at least": ">=", "no less than": ">=",
    "above": ">", "more than": ">", "over": ">", "exactly": "=",
}
OP = "|".join(re.escape(o) for o in sorted(OPERATORS, key=len, reverse=True))
SYMBOL_CASE = {"pa": {"Pa"}, "kpa": {"kPa"}, "mpa": {"MPa"},
               "m": {"m"}, "cm": {"cm"}, "mm": {"mm"}, "kg": {"kg"},
               "g": {"g"}, "v": {"V"}, "a": {"A"}, "k": {"K"},
               "s": {"s"}, "h": {"h"}}
QUANTITY = re.compile(
    rf"(?<![\w.])(?:(?P<op>{OP})\s+)?(?P<lo>{NUMBER})"
    rf"(?:\s*(?:to|–|—|-)\s*(?P<hi>{NUMBER}))?"
    rf"(?:\s*(?P<unit>{UNIT}))?(?!\w|\.\d)", re.I,
)


@dataclass(frozen=True)
class Quantity:
    start: int
    end: int
    dimension: str
    lower: Fraction
    upper: Fraction | None
    operator: str

    @property
    def signature(self) -> tuple:
        return self.dimension, self.lower, self.upper, self.operator


def quantities(text: str) -> list[Quantity]:
    result = []
    for match in QUANTITY.finditer(text):
        unit = (match.group("unit") or "").casefold()
        dimension, scale, offset = UNITS.get(unit, ("count", Fraction(1), Fraction(0)))
        lo = Fraction(match.group("lo")) * scale + offset
        hi = Fraction(match.group("hi")) * scale + offset if match.group("hi") else None
        result.append(Quantity(match.start(), match.end(), dimension, lo, hi,
                               OPERATORS.get((match.group("op") or "").casefold(), "=")))
    return result


def numeric_frame(text: str) -> str:
    return normalize(QUANTITY.sub(" <quantity> ", text))


def numeric_signatures(text: str) -> list[tuple]:
    return [q.signature for q in quantities(text)]


def supported_numeric_syntax(text: str) -> bool:
    # Explicitly unsupported: grouping commas, scientific notation, and between
    # ranges. These must not accidentally become different independent numbers.
    if re.search(r"\d,\d|\d[eE][+-]?\d|\bbetween\b|[<>≤≥]", text, re.I):
        return False
    for match in QUANTITY.finditer(text):
        raw_unit = match.group("unit") or ""
        if raw_unit.casefold() in SYMBOL_CASE and raw_unit not in SYMBOL_CASE[raw_unit.casefold()]:
            return False
    return True


def phrase_replace(text: str, phrase: str, replacement: str) -> str:
    return re.sub(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", replacement, text)


def contains_phrase(text: str, phrase: str) -> bool:
    return phrase_replace(normalize(text), normalize(phrase), "<matched>") != normalize(text)
