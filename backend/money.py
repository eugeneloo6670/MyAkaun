from decimal import Decimal, ROUND_HALF_UP

ZERO = Decimal("0")
MONEY_TOLERANCE = Decimal("0.005")
MONEY_PLACES = Decimal("0.01")
RATE_PLACES = Decimal("0.000001")
PERCENT_PLACES = Decimal("0.01")


def dec(value, default=ZERO) -> Decimal:
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def money(value) -> Decimal:
    return dec(value).quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)


def rate(value) -> Decimal:
    return dec(value).quantize(RATE_PLACES, rounding=ROUND_HALF_UP)


def percent(value) -> Decimal:
    return dec(value).quantize(PERCENT_PLACES, rounding=ROUND_HALF_UP)


def money_sum(values) -> Decimal:
    return money(sum((dec(v) for v in values), ZERO))
