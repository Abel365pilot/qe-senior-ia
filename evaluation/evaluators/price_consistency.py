"""Validación determinista de precios mencionados contra el contexto."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


_PRICE_PATTERN = re.compile(
    r"(?:(?P<prefix>S/\.?|PEN|USD|\$)\s*(?P<amount1>\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?))"
    r"|(?:(?P<amount2>\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)\s*(?P<suffix>PEN|USD))",
    re.IGNORECASE,
)


@dataclass(frozen=True, order=True)
class Price:
    currency: str
    amount: Decimal

    def render(self) -> str:
        return f"{self.currency} {self.amount.quantize(Decimal('0.01'))}"


def _currency_family(raw: str) -> str:
    token = raw.upper().replace(".", "")
    return "PEN" if token in {"S/", "PEN"} else "USD"


def _decimal_amount(raw: str) -> Decimal:
    value = raw.strip()
    if "," in value and "." in value:
        decimal_separator = "," if value.rfind(",") > value.rfind(".") else "."
        thousands_separator = "." if decimal_separator == "," else ","
        value = value.replace(thousands_separator, "").replace(decimal_separator, ".")
    elif "," in value or "." in value:
        separator = "," if "," in value else "."
        head, tail = value.rsplit(separator, 1)
        if len(tail) == 3 and len(head.replace(separator, "")) <= 3:
            value = value.replace(separator, "")
        else:
            value = value.replace(separator, ".")
    try:
        return Decimal(value).quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise ValueError(f"Importe monetario inválido: {raw!r}") from exc


def extract_prices(text: str | None) -> set[Price]:
    prices: set[Price] = set()
    for match in _PRICE_PATTERN.finditer(text or ""):
        currency = match.group("prefix") or match.group("suffix")
        amount = match.group("amount1") or match.group("amount2")
        prices.add(Price(_currency_family(currency), _decimal_amount(amount)))
    return prices


class PriceConsistencyEvaluator:
    """Falla si la respuesta introduce un precio que no aparece en el contexto."""

    def __call__(self, *, response: str, context: str, **kwargs: object) -> dict[str, object]:
        response_prices = extract_prices(response)
        context_prices = extract_prices(context)
        unsupported = sorted(response_prices - context_prices)
        passed = not unsupported
        return {
            "price_consistency": int(passed),
            "price_consistency_result": "pass" if passed else "fail",
            "price_consistency_reason": (
                "Todos los precios de la respuesta están sustentados por el contexto."
                if passed
                else "Precios no sustentados: " + ", ".join(price.render() for price in unsupported)
            ),
            "response_prices": [price.render() for price in sorted(response_prices)],
            "context_prices": [price.render() for price in sorted(context_prices)],
        }
