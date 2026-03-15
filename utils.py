"""
utils.py — Fonctions utilitaires génériques.
Aucune dépendance aux modèles ou à la base de données.
"""
from typing import Any, Optional
import unicodedata
import re

def _f(val: Any) -> Optional[float]:
    """Convertit une valeur en float de manière sécurisée."""
    try:
        v = float(val)
        return v if v >= 0 else None
    except (ValueError, TypeError):
        return None

def normalize_string(s: str) -> str:
    """Normalise une chaîne (minuscules, sans accents, caractères alphanumériques purs)."""
    if not s: 
        return ""
    s = s.strip().lower()
    # Remplacement spécifique pour les langues nordiques avant de retirer les accents
    s = s.replace("æ", "ae").replace("ø", "o").replace("å", "a")
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9 ]", "", s)
    return re.sub(r"\s+", " ", s).strip()