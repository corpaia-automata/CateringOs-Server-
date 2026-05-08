"""
Convert Ingredient.unit_cost (per ingredient.unit_of_measure) to a rate per recipe-line unit.
"""
from decimal import Decimal


def unit_cost_snapshot_for_recipe_line(ingredient, recipe_unit: str) -> Decimal:
    """
    Value stored on DishRecipe.unit_cost_snapshot for pricing.

    Same UOM as ingredient: returns unit_cost unchanged.
    Recipe line in g (ml) with ingredient in kg (litre): stores bulk rate (per kg / per litre);
    multiply cost by qty in g/ml uses ÷1000 at calculation time only.
    Other pairs: kg↔g and litre↔ml scaling as needed; count UOMs return unit_cost as-is.
    """
    if ingredient is None:
        return Decimal('0')

    base = ingredient.unit_cost
    ing_uom = (ingredient.unit_of_measure or '').strip().lower()
    rec_uom = (recipe_unit or '').strip().lower()
    if not rec_uom or ing_uom == rec_uom:
        return base

    # Snapshot stores the same basis as Ingredient.unit_cost for mass/volume base UOMs
    # (per kg / per litre); g/ml cost uses ÷1000 only at calculation time.
    if ing_uom == 'kg' and rec_uom == 'g':
        return base
    if ing_uom == 'g' and rec_uom == 'kg':
        return base * Decimal('1000')
    if ing_uom == 'litre' and rec_uom == 'ml':
        return base
    if ing_uom == 'ml' and rec_uom == 'litre':
        return base * Decimal('1000')

    return base


def _bulk_ingredient_uom_for_small_line(rec_u: str, ing_uom: str) -> bool:
    """True when snapshot/live rate is per kg or per litre but recipe qty is in g or ml."""
    iu = (ing_uom or '').strip().lower()
    if rec_u in ('g', 'gram'):
        return iu == 'kg'
    if rec_u in ('ml', 'millilitre', 'milliliter'):
        return iu in ('litre', 'liter', 'ltr')
    return False


def effective_rate_per_recipe_unit(line) -> Decimal:
    """
    DishRecipe: use stored snapshot when non-zero; else live converted rate.
    For g/ml lines with ingredient priced per kg/litre, snapshot is bulk rate; qty_per_unit is in g/ml → ÷1000.
    """
    from .models import Ingredient  # local import avoids cycles

    ing = getattr(line, 'ingredient', None)
    rec_u = str(getattr(line, 'unit', None) or '').strip().lower()
    snap = getattr(line, 'unit_cost_snapshot', None)
    if snap is not None and snap != 0:
        r = Decimal(str(snap))
        if isinstance(ing, Ingredient) and _bulk_ingredient_uom_for_small_line(rec_u, ing.unit_of_measure):
            # gram/ml unit cost conversion
            return r / Decimal('1000')
        return r
    if not isinstance(ing, Ingredient):
        return Decimal('0')
    unit = getattr(line, 'unit', None) or ing.unit_of_measure
    u = str(unit or '').strip().lower()
    live = unit_cost_snapshot_for_recipe_line(ing, str(unit or ''))
    if _bulk_ingredient_uom_for_small_line(u, ing.unit_of_measure):
        # gram/ml unit cost conversion
        return live / Decimal('1000')
    return live
