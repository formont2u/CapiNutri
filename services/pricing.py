"""
services/pricing.py — Logique métier pour le calcul des prix.
"""

def calculate_cost(buy_qty: float, buy_unit: str, ref_price: float, ref_unit: str) -> float:
    """Convertit l'unité de la recette vers l'unité du magasin pour calculer le prix exact."""
    b_u = (buy_unit or "").lower().strip()
    r_u = (ref_unit or "").lower().strip()
    
    if b_u == r_u: 
        return buy_qty * ref_price
    
    # Grammes -> Kilo
    if b_u in ['g', 'gr', 'gram'] and r_u in ['kg', 'kilo']: 
        return (buy_qty / 1000.0) * ref_price
    
    # Ml/Cl/Dl -> Litre
    if b_u in ['ml'] and r_u in ['l', 'litre']: return (buy_qty / 1000.0) * ref_price
    if b_u in ['cl'] and r_u in ['l', 'litre']: return (buy_qty / 100.0) * ref_price
    if b_u in ['dl'] and r_u in ['l', 'litre']: return (buy_qty / 10.0) * ref_price
    
    # Si on ne sait pas convertir, on applique le prix brut (Fallback)
    return buy_qty * ref_price