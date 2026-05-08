from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.events.models import Event, EventLog
from apps.events.services import EventExecutionService, recalculate_event
from apps.engine.models import EventIngredient
from apps.inquiries.models import Inquiry
from apps.master.models import Dish, DishRecipe, Ingredient
from apps.tenants.models import Tenant


class EventExecutionServiceTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(slug='event-execution', name='Event Execution')
        self.inquiry = Inquiry.objects.create(
            tenant=self.tenant,
            customer_name='Client One',
            source_channel='PHONE_CALL',
            event_type='Wedding',
            tentative_date=date.today(),
            guest_count=100,
            status='SUCCESS',
        )
        self.event = Event.objects.create(
            tenant=self.tenant,
            inquiry=self.inquiry,
            customer_name='Client One',
            event_type='Wedding',
            event_date=date.today(),
            guest_count=100,
            service_type=Event.ServiceType.BUFFET,
            status=Event.Status.CONFIRMED,
            total_amount=Decimal('0.00'),
            advance_amount=Decimal('0.00'),
            credited_amount=Decimal('0.00'),
        )
        self.rice = Ingredient.objects.create(
            tenant=self.tenant,
            name='Basmati Rice',
            category=Ingredient.Category.GROCERY,
            unit_of_measure=Ingredient.UOM.KG,
            unit_cost=Decimal('80.00'),
        )
        self.biryani = Dish.objects.create(
            tenant=self.tenant,
            name='Chicken Biryani',
            category_text='Main Course',
            serving_unit=Dish.ServingUnit.PLATE,
            base_price=Decimal('180.00'),
            selling_price=Decimal('180.00'),
            batch_size=Decimal('10.000'),
            batch_unit='PLATE',
        )
        DishRecipe.objects.create(
            tenant=self.tenant,
            dish=self.biryani,
            ingredient=self.rice,
            qty_per_unit=Decimal('2.0000'),
            unit=Ingredient.UOM.KG,
        )
        self.pulao = Dish.objects.create(
            tenant=self.tenant,
            name='Veg Pulao',
            category_text='Main Course',
            serving_unit=Dish.ServingUnit.PLATE,
            base_price=Decimal('120.00'),
            selling_price=Decimal('120.00'),
            batch_size=Decimal('5.000'),
            batch_unit='PLATE',
        )
        DishRecipe.objects.create(
            tenant=self.tenant,
            dish=self.pulao,
            ingredient=self.rice,
            qty_per_unit=Decimal('500.0000'),
            unit=Ingredient.UOM.G,
        )

    def test_add_new_dish_updates_total_and_persists(self):
        EventExecutionService.replace_menu(self.event, [
            {'name': 'Chicken Biryani', 'quantity': 100, 'unit': 'plate', 'price_per_unit': 180},
        ])

        self.event.refresh_from_db()
        self.assertEqual(self.event.total_amount, Decimal('18000.00'))
        self.assertEqual(self.event.pricing_snapshot['menu_total'], '18000.00')
        self.assertEqual(EventLog.objects.filter(event=self.event, action_type=EventLog.ActionType.ADD_DISH).count(), 1)

    def test_menu_update_derives_grocery_snapshot_from_menu(self):
        EventExecutionService.replace_menu(self.event, [
            {
                'id': str(self.biryani.id),
                'name': 'Chicken Biryani',
                'quantity': 100,
                'unit': 'plate',
                'price_per_unit': 180,
            },
        ])

        self.event.refresh_from_db()
        grocery_items = self.event.grocery_snapshot['items']
        self.assertEqual(len(grocery_items), 1)
        self.assertEqual(grocery_items[0]['ingredient_name'], 'Basmati Rice')
        self.assertEqual(grocery_items[0]['total_quantity'], '20.000')
        self.assertEqual(grocery_items[0]['unit'], 'kg')

    def test_menu_update_derives_costing_and_event_ingredients_from_menu(self):
        EventExecutionService.replace_menu(self.event, [
            {
                'id': str(self.biryani.id),
                'name': 'Chicken Biryani',
                'quantity': 100,
                'unit': 'plate',
                'price_per_unit': 180,
            },
        ])

        self.event.refresh_from_db()
        derived_items = self.event.costing_snapshot['derived_items']
        self.assertEqual(len(derived_items), 1)
        self.assertEqual(derived_items[0]['ingredient_name'], 'Basmati Rice')
        self.assertEqual(derived_items[0]['quantity'], '20.000')
        self.assertEqual(derived_items[0]['total'], '1600.00')
        self.assertEqual(self.event.total_cost, Decimal('1600.00'))
        self.assertEqual(self.event.pricing_snapshot['derived_cost'], '1600.00')
        self.assertEqual(self.event.pricing_snapshot['internal_cost'], '1600.00')
        ingredient = EventIngredient.objects.get(event=self.event, ingredient=self.rice)
        self.assertEqual(ingredient.tenant_id, self.tenant.id)
        self.assertEqual(ingredient.total_quantity, Decimal('20.000000'))
        self.assertEqual(ingredient.unit, 'kg')

    def test_menu_payload_with_explicit_dish_id_drives_grocery_and_costing(self):
        EventExecutionService.replace_menu(self.event, [
            {
                'id': 'client-row-1',
                'dish_id': str(self.biryani.id),
                'name': 'Chicken Biryani',
                'quantity': 25,
                'unit': 'plate',
                'price_per_unit': 180,
            },
        ])

        self.event.refresh_from_db()
        self.assertEqual(self.event.menu_snapshot['items'][0]['id'], 'client-row-1')
        self.assertEqual(self.event.menu_snapshot['items'][0]['dish_id'], str(self.biryani.id))
        self.assertEqual(self.event.grocery_snapshot['items'][0]['total_quantity'], '5.000')
        self.assertEqual(self.event.costing_snapshot['derived_items'][0]['total'], '400.00')
        self.assertEqual(self.event.total_cost, Decimal('400.00'))

    def test_same_ingredient_across_dishes_is_deduplicated_and_unit_normalized(self):
        EventExecutionService.replace_menu(self.event, [
            {
                'id': str(self.biryani.id),
                'dish_id': str(self.biryani.id),
                'name': 'Chicken Biryani',
                'quantity': 10,
                'unit': 'plate',
                'price_per_unit': 180,
            },
            {
                'id': str(self.pulao.id),
                'dish_id': str(self.pulao.id),
                'name': 'Veg Pulao',
                'quantity': 10,
                'unit': 'plate',
                'price_per_unit': 120,
            },
        ])

        self.event.refresh_from_db()
        derived_items = self.event.costing_snapshot['derived_items']
        grocery_items = self.event.grocery_snapshot['items']
        self.assertEqual(len(derived_items), 1)
        self.assertEqual(len(grocery_items), 1)
        self.assertEqual(derived_items[0]['ingredient_id'], str(self.rice.id))
        self.assertEqual(derived_items[0]['quantity'], '3.000')
        self.assertEqual(derived_items[0]['unit'], 'kg')
        self.assertEqual(derived_items[0]['rate'], '80.00')
        self.assertEqual(derived_items[0]['total_cost'], '240.00')
        self.assertEqual(grocery_items[0]['total_quantity'], '3.000')
        self.assertEqual(grocery_items[0]['unit'], 'kg')
        self.assertEqual(self.event.total_cost, Decimal('240.00'))

    def test_legacy_non_uuid_menu_ids_do_not_break_grocery_derivation(self):
        EventExecutionService.replace_menu(self.event, [
            {'id': 'dish-1', 'name': 'Legacy Dish', 'quantity': 10, 'unit': 'plate', 'price_per_unit': 100},
            {
                'id': str(self.biryani.id),
                'name': 'Chicken Biryani',
                'quantity': 10,
                'unit': 'plate',
                'price_per_unit': 180,
            },
        ])

        self.event.refresh_from_db()
        self.assertEqual(self.event.total_amount, Decimal('2800.00'))
        self.assertEqual(len(self.event.menu_snapshot['items']), 2)
        self.assertNotIn('dish_id', self.event.menu_snapshot['items'][0])
        self.assertEqual(self.event.grocery_snapshot['items'][0]['ingredient_name'], 'Basmati Rice')

    def test_modify_quantity_recalculates_total(self):
        EventExecutionService.replace_menu(self.event, [
            {'name': 'Chicken Biryani', 'quantity': 100, 'unit': 'plate', 'price_per_unit': 180},
        ])
        EventExecutionService.replace_menu(self.event, [
            {'name': 'Chicken Biryani', 'quantity': 120, 'unit': 'plate', 'price_per_unit': 180},
        ])

        self.event.refresh_from_db()
        self.assertEqual(self.event.total_amount, Decimal('21600.00'))
        self.assertTrue(EventLog.objects.filter(event=self.event, action_type=EventLog.ActionType.UPDATE_QTY).exists())

    def test_add_service_updates_total(self):
        EventExecutionService.replace_services(self.event, [
            {'name': 'Service Staff', 'quantity': 5, 'unit': 'person', 'price_per_unit': 1000},
        ])

        self.event.refresh_from_db()
        self.assertEqual(self.event.total_amount, Decimal('5000.00'))
        self.assertEqual(self.event.pricing_snapshot['service_total'], '5000.00')

    def test_add_extra_charge_reflects_in_final_price(self):
        EventExecutionService.replace_menu(self.event, [
            {'name': 'Chicken Biryani', 'quantity': 100, 'unit': 'plate', 'price_per_unit': 180},
        ])
        EventExecutionService.add_extra_charge(self.event, {'amount': 2500, 'description': 'Last-minute dish addition'})

        self.event.refresh_from_db()
        self.assertEqual(self.event.extra_charges, Decimal('2500.00'))
        self.assertEqual(self.event.total_amount, Decimal('20500.00'))
        self.assertEqual(self.event.pricing_snapshot['final_total'], '20500.00')

    def test_costing_update_recalculates_internal_cost_and_margin(self):
        EventExecutionService.replace_menu(self.event, [
            {'id': str(self.biryani.id), 'name': 'Chicken Biryani', 'quantity': 100, 'unit': 'plate', 'price_per_unit': 180},
        ])
        EventExecutionService.replace_costing(self.event, [
            {'name': 'Rice', 'quantity': 20, 'unit': 'kg', 'rate': 60},
            {'name': 'Chicken', 'quantity': 30, 'unit': 'kg', 'rate': 200},
        ])

        self.event.refresh_from_db()
        self.assertEqual(self.event.total_cost, Decimal('8800.00'))
        self.assertEqual(self.event.pricing_snapshot['derived_cost'], '1600.00')
        self.assertEqual(self.event.pricing_snapshot['manual_cost'], '7200.00')
        self.assertEqual(self.event.pricing_snapshot['total_cost'], '8800.00')
        self.assertEqual(len(self.event.costing_snapshot['derived_items']), 1)
        self.assertEqual(len(self.event.costing_snapshot['manual_items']), 2)

    def test_recalculate_event_rebuilds_all_snapshots_from_event_id(self):
        self.event.menu_snapshot = {
            'items': [{
                'id': str(self.biryani.id),
                'dish_id': str(self.biryani.id),
                'name': 'Chicken Biryani',
                'quantity': '50.00',
                'qty': '50.00',
                'unit': 'plate',
                'price_per_unit': '200.00',
                'price': '200.00',
                'total': '10000.00',
            }]
        }
        self.event.services_snapshot = {
            'items': [{
                'id': 'service-1',
                'name': 'Service Staff',
                'quantity': '2.00',
                'price_per_unit': '1000.00',
                'price': '1000.00',
                'total': '2000.00',
            }]
        }
        self.event.costing_snapshot = {
            'manual_items': [{
                'id': 'manual-1',
                'name': 'Fuel',
                'ingredient_name': 'Fuel',
                'quantity': '1.00',
                'rate': '500.00',
                'total': '500.00',
            }]
        }
        self.event.save(update_fields=['menu_snapshot', 'services_snapshot', 'costing_snapshot'])

        recalculate_event(self.event.id)

        self.event.refresh_from_db()
        self.assertEqual(self.event.pricing_snapshot['menu_total'], '10000.00')
        self.assertEqual(self.event.pricing_snapshot['service_total'], '2000.00')
        self.assertEqual(self.event.pricing_snapshot['derived_cost'], '800.00')
        self.assertEqual(self.event.pricing_snapshot['manual_cost'], '500.00')
        self.assertEqual(self.event.total_cost, Decimal('1300.00'))
        self.assertEqual(self.event.total_amount, Decimal('12000.00'))
        self.assertEqual(self.event.grocery_snapshot['items'][0]['ingredient_name'], 'Basmati Rice')

    def test_completed_event_is_locked(self):
        self.event.status = Event.Status.COMPLETED
        self.event.save(update_fields=['status'])

        with self.assertRaises(ValidationError):
            EventExecutionService.replace_menu(self.event, [
                {'name': 'Chicken Biryani', 'quantity': 100, 'unit': 'plate', 'price_per_unit': 180},
            ])

    def test_menu_locked_event_is_locked(self):
        self.event.menu_locked = True
        self.event.save(update_fields=['menu_locked'])

        with self.assertRaises(ValidationError):
            EventExecutionService.replace_menu(self.event, [
                {'name': 'Chicken Biryani', 'quantity': 100, 'unit': 'plate', 'price_per_unit': 180},
            ])

    def test_duplicate_dish_names_are_rejected(self):
        with self.assertRaises(ValidationError):
            EventExecutionService.replace_menu(self.event, [
                {'name': 'Chicken Biryani', 'quantity': 100, 'unit': 'plate', 'price_per_unit': 180},
                {'name': 'chicken biryani', 'quantity': 50, 'unit': 'plate', 'price_per_unit': 180},
            ])

    def test_negative_and_zero_dish_values_are_rejected(self):
        invalid_payloads = [
            [{'name': 'Chicken Biryani', 'quantity': -1, 'unit': 'plate', 'price_per_unit': 180}],
            [{'name': 'Chicken Biryani', 'quantity': 0, 'unit': 'plate', 'price_per_unit': 180}],
            [{'name': 'Chicken Biryani', 'quantity': 1, 'unit': 'plate', 'price_per_unit': -1}],
            [{'name': 'Chicken Biryani', 'quantity': 'abc', 'unit': 'plate', 'price_per_unit': 180}],
        ]

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ValidationError):
                    EventExecutionService.replace_menu(self.event, payload)
