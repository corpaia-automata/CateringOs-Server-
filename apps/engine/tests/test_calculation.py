import datetime
from decimal import Decimal

from django.test import TestCase

from apps.engine.calculation import CalculationEngine, normalise
from apps.engine.models import EventIngredient
from apps.events.models import Event
from apps.master.models import Dish, DishRecipe, Ingredient
from apps.menu.models import EventMenuItem


class NormalisationTest(TestCase):
    """Pure unit tests for the normalise() function — no DB required."""

    def test_grams_to_kg(self):
        qty, unit = normalise(Decimal('500'), 'g')
        self.assertEqual(qty, Decimal('0.5'))
        self.assertEqual(unit, 'kg')

    def test_ml_to_litre(self):
        qty, unit = normalise(Decimal('750'), 'ml')
        self.assertEqual(qty, Decimal('0.75'))
        self.assertEqual(unit, 'litre')

    def test_kg_unchanged(self):
        qty, unit = normalise(Decimal('2'), 'kg')
        self.assertEqual(qty, Decimal('2'))
        self.assertEqual(unit, 'kg')


class AggregationTest(TestCase):
    """
    Integration test: full pipeline from EventMenuItem → CalculationEngine → EventIngredient.

    Scenario:
        Salt in Biryani: 50 g/plate × 200 plates = 10,000 g → 10 kg
        Salt in Curry:   30 g/plate × 200 plates =  6,000 g →  6 kg
        Expected total:                                         16 kg
    """

    def setUp(self):
        self.salt = Ingredient.objects.create(
            name='Salt',
            category='GROCERY',
            unit_of_measure='g',
        )
        self.biryani = Dish.objects.create(
            name='Chicken Biryani',
            category='Mains',
            unit_type='PLATE',
        )
        self.curry = Dish.objects.create(
            name='Chicken Sukka',
            category='Mains',
            unit_type='PLATE',
        )
        DishRecipe.objects.create(
            dish=self.biryani,
            ingredient=self.salt,
            qty_per_unit=Decimal('50'),
            unit='g',
        )
        DishRecipe.objects.create(
            dish=self.curry,
            ingredient=self.salt,
            qty_per_unit=Decimal('30'),
            unit='g',
        )
        self.event = Event.objects.create(
            customer_name='Test Client',
            event_type='Wedding',
            event_date=datetime.date.today(),
            guest_count=300,
            service_type='BUFFET',
        )

    def test_salt_aggregates_across_dishes(self):
        # Creating menu items freezes snapshots in EventMenuItem.save().
        # The engine can still rebuild EventIngredient rows from those snapshots.
        EventMenuItem.objects.create(
            event=self.event,
            dish=self.biryani,
            quantity=Decimal('200'),
        )
        EventMenuItem.objects.create(
            event=self.event,
            dish=self.curry,
            quantity=Decimal('200'),
        )

        # After both items exist, the engine has run with the full menu.
        ei = EventIngredient.objects.get(event=self.event, ingredient=self.salt)

        self.assertEqual(ei.total_quantity, Decimal('16'))
        self.assertEqual(ei.unit, 'kg')
        self.assertEqual(ei.ingredient_name, 'Salt')
        self.assertEqual(ei.category, 'GROCERY')
