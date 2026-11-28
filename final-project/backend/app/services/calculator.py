"""The pocket calculator: exact arithmetic on what a person types.

A tiny recursive-descent parser over :class:`~decimal.Decimal` — nothing is ever
handed to ``eval``. Decimals mean money adds up the way it does on paper
(``0.1 + 0.2`` is ``0.3``).

Understood: numbers, ``+ - * /`` (also ``× ÷ −``), parentheses, a leading minus
and a trailing ``%`` ("15%" is 0.15, so ``200 × 15%`` is 30). Numbers may use a
comma or a point for decimals, with the other as thousands separator, exactly
like the amount boxes: ``1.234,56`` and ``1,234.56`` are both 1234.56.
"""

from __future__ import annotations

import re
from decimal import Decimal, DivisionByZero, InvalidOperation, localcontext

MAX_LENGTH = 200
MAX_DEPTH = 40
#: Results are shown to this many decimal places at most.
PLACES = Decimal("1e-10")
#: Beyond this the display stops being useful — and it bounds the work done.
LIMIT = Decimal("1e15")

_SYMBOLS = {"×": "*", "x": "*", "X": "*", "÷": "/", ":": "/", "−": "-", "–": "-", "€": ""}
_TOKEN = re.compile(r"\d[\d.,]*|[.,]\d+|[-+*/()%]")


class CalculatorError(ValueError):
    """The expression cannot be worked out; the message is shown to the user."""


def _number(text: str) -> Decimal:
    """Read a typed number the way the amount boxes do."""
    if text.rfind(",") > text.rfind("."):
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", "")
    try:
        return Decimal(text)
    except InvalidOperation:
        raise CalculatorError(f"“{text}” is not a number") from None


def tokenize(expression: str) -> list[str]:
    text = expression
    for symbol, plain in _SYMBOLS.items():
        text = text.replace(symbol, plain)
    text = re.sub(r"\s+", "", text)
    if not text:
        raise CalculatorError("Type a calculation, e.g. 1650 + 300")
    if len(text) > MAX_LENGTH:
        raise CalculatorError("That calculation is too long")
    tokens = _TOKEN.findall(text)
    if "".join(tokens) != text:
        raise CalculatorError("Only numbers and + − × ÷ ( ) % are understood")
    return tokens


class _Parser:
    def __init__(self, tokens: list[str]):
        self.tokens = tokens
        self.pos = 0
        self.depth = 0

    def peek(self) -> str | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def take(self) -> str:
        token = self.tokens[self.pos]
        self.pos += 1
        return token

    def expression(self) -> Decimal:
        value = self.term()
        while self.peek() in ("+", "-"):
            if self.take() == "+":
                value += self.term()
            else:
                value -= self.term()
        return value

    def term(self) -> Decimal:
        value = self.factor()
        while self.peek() in ("*", "/"):
            if self.take() == "*":
                value *= self.factor()
            else:
                divisor = self.factor()
                if divisor == 0:
                    raise CalculatorError("Cannot divide by zero")
                value /= divisor
            if abs(value) > LIMIT:
                raise CalculatorError("That number is too large")
        return value

    def factor(self) -> Decimal:
        token = self.peek()
        if token in ("+", "-"):
            self.depth += 1
            if self.depth > MAX_DEPTH:
                raise CalculatorError("That calculation is nested too deeply")
            self.take()
            value = self.factor()
            self.depth -= 1
            return -value if token == "-" else value
        value = self.primary()
        while self.peek() == "%":
            self.take()
            value /= 100
        return value

    def primary(self) -> Decimal:
        token = self.peek()
        if token is None:
            raise CalculatorError("The calculation is not finished")
        if token == "(":
            self.depth += 1
            if self.depth > MAX_DEPTH:
                raise CalculatorError("That calculation is nested too deeply")
            self.take()
            value = self.expression()
            if self.peek() != ")":
                raise CalculatorError("A bracket is not closed")
            self.take()
            self.depth -= 1
            return value
        if token[0].isdigit() or token[0] in ".,":
            return _number(self.take())
        raise CalculatorError("The calculation is not finished" if token == ")" else f"Unexpected “{token}”")


def _plain(value: Decimal) -> str:
    """``1927.51``, never ``1.92751E+3`` and never ``-0``."""
    text = format(value.quantize(PLACES).normalize(), "f")
    return "0" if text in ("-0", "0") else text


def evaluate(expression: str) -> dict[str, object]:
    """Work out ``expression``. Raises :class:`CalculatorError` with a message
    a person can act on when it cannot be done."""
    parser = _Parser(tokenize(expression))
    try:
        with localcontext() as ctx:
            ctx.prec = 34
            value = parser.expression()
            if parser.peek() is not None:
                raise CalculatorError(
                    "A bracket is closed that was never opened" if parser.peek() == ")" else "The calculation is not finished"
                )
            if abs(value) > LIMIT:
                raise CalculatorError("That number is too large")
            text = _plain(value)
    except (DivisionByZero, InvalidOperation, RecursionError):
        raise CalculatorError("That cannot be calculated") from None
    return {"expression": expression.strip(), "result": float(text), "text": text}
