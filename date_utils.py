"""
date_utils.py - Shared French date formatting helpers for the UI layer.
"""

from datetime import date, timedelta

DAYS_FR = (
    "Lundi",
    "Mardi",
    "Mercredi",
    "Jeudi",
    "Vendredi",
    "Samedi",
    "Dimanche",
)

MONTHS_FR = (
    "Janvier",
    "Fevrier",
    "Mars",
    "Avril",
    "Mai",
    "Juin",
    "Juillet",
    "Aout",
    "Septembre",
    "Octobre",
    "Novembre",
    "Decembre",
)

MONTHS_FR_LOWER = tuple(month.lower() for month in MONTHS_FR)

MONTHS_FR_SHORT = (
    "jan",
    "fev",
    "mar",
    "avr",
    "mai",
    "jun",
    "jul",
    "aou",
    "sep",
    "oct",
    "nov",
    "dec",
)


def start_of_week(day: date | None = None) -> date:
    day = day or date.today()
    return day - timedelta(days=day.weekday())


def format_weekday_label(day: date) -> str:
    return f"{DAYS_FR[day.weekday()]} {day.day}"


def format_long_date(day: date) -> str:
    return f"{DAYS_FR[day.weekday()]} {day.day} {MONTHS_FR_LOWER[day.month - 1]} {day.year}"


def format_week_label(start: date, short_months: bool = False) -> str:
    months = MONTHS_FR_SHORT if short_months else MONTHS_FR
    end = start + timedelta(days=6)
    return f"{start.day} {months[start.month - 1]} -> {end.day} {months[end.month - 1]} {end.year}"


def format_month_label(day: date) -> str:
    return f"{day.day} {MONTHS_FR[day.month - 1]}"
