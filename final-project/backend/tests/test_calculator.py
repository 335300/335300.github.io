"""The pocket calculator: exact arithmetic, and clear refusals."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.app import create_app
from app.services import calculator


@pytest.mark.parametrize(
    "expression, text",
    [
        ("1+2", "3"),
        ("0.1 + 0.2", "0.3"),                      # exact, unlike binary floats
        ("1650 + 300 - 22.49", "1927.51"),
        ("12,5 + 7.5 × 2", "27.5"),                # comma decimals, × sign, precedence
        ("(1650 + 300) ÷ 3", "650"),
        ("200 × 15%", "30"),
        ("15%", "0.15"),
        ("−5 + 2", "-3"),                          # a typographic minus
        ("-(3 - 5) * 2", "4"),
        ("1.234,56 + 1,234.56", "2469.12"),        # either thousands style
        ("€ 2 170 000 / 6536", "332.0073439412"),  # euro sign and spaces are ignored
        ("10 / 4", "2.5"),
        ("1/3", "0.3333333333"),
        ("5 - 5", "0"),
        ("0 * -1", "0"),                           # never "-0"
        ("2 x 3 : 4", "1.5"),
        (".5 + ,5", "1"),
    ],
)
def test_evaluate(expression, text):
    out = calculator.evaluate(expression)
    assert out["text"] == text and out["result"] == float(text)


@pytest.mark.parametrize(
    "expression",
    [
        "", "   ", "12 +", "(1 + 2", "1 + 2)", "1 / 0", "5 / (2 - 2)", "2 ** 8", "abc", "1e9",
        "__import__('os')", "1 + + ", "()", "3 4 +", "%5", "1.2.3", "9" * 201, "9" * 16 + "* 9",
    ],
)
def test_refuses_what_it_cannot_calculate(expression):
    with pytest.raises(calculator.CalculatorError) as error:
        calculator.evaluate(expression)
    assert str(error.value)                        # always says why


def test_spaces_inside_a_number_are_joined():
    assert calculator.evaluate("3 4 + 1")["text"] == "35"


def test_deep_nesting_is_refused_not_crashed():
    with pytest.raises(calculator.CalculatorError):
        calculator.evaluate("(" * 60 + "1" + ")" * 60)
    with pytest.raises(calculator.CalculatorError):
        calculator.evaluate("-" * 60 + "1")


def test_api():
    client = TestClient(create_app())
    ok = client.post("/api/calc", json={"expression": "1650 + 300 − 22,49"})
    assert ok.status_code == 200 and ok.json() == {"expression": "1650 + 300 − 22,49", "result": 1927.51, "text": "1927.51"}
    bad = client.post("/api/calc", json={"expression": "12 +"})
    assert bad.status_code == 422 and bad.json()["detail"] == "The calculation is not finished"
    assert client.post("/api/calc", json={"expression": "1 / 0"}).json()["detail"] == "Cannot divide by zero"
    assert client.post("/api/calc", json={}).status_code == 422
