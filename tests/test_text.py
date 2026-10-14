from fractions import Fraction

import pytest

from dubguard.text import normalize, numeric_signatures, quantities, supported_numeric_syntax


@pytest.mark.parametrize("first,second", [
    ("60 seconds", "1 minute"), ("3600 s", "1 hour"),
    ("80 °C", "176 °F"), ("0 °C", "32 °F"), ("-40 °C", "-40 °F"),
    ("80 °C", "353.15 K"), ("2 to 4 bar", "200 to 400 kPa"),
    ("1 inch", "25.4 mm"), ("1 kg", "1000 g"), ("4 bolts", "4.0 bolts"),
])
def test_exact_numeric_conversions(first, second):
    assert numeric_signatures(first) == numeric_signatures(second)


@pytest.mark.parametrize("first,second", [
    ("60 seconds", "60 minutes"), ("80 °C", "80 °F"),
    ("below 80 °C", "at or below 80 °C"), ("at least 60 s", "at most 60 s"),
    ("2 to 4 bar", "4 to 2 bar"), ("10 mm", "10 seconds"),
])
def test_changed_numeric_meaning_differs(first, second):
    assert numeric_signatures(first) != numeric_signatures(second)


def test_fraction_math_is_exact():
    assert quantities("0.1 m")[0].lower == Fraction(1, 10)


def test_unit_case_and_sentence_punctuation():
    assert normalize("2 MPa.") != normalize("2 mPa.")
    assert not supported_numeric_syntax("2 mPa")
    assert quantities("Keep at most 80 °C.")[0].dimension == "temperature"
    assert numeric_signatures("2–4 bar") == numeric_signatures("2-4 bar")


def test_numeric_character_offsets():
    text = "Wait at least 60 seconds, then cool."
    q = quantities(text)[0]
    assert text[q.start:q.end] == "at least 60 seconds"
