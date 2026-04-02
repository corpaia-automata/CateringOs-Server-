from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404

from apps.events.models import Event

from .models import EventMenuItem


class MenuService:

    @staticmethod
    def add_dish(event_id, validated_data: dict) -> EventMenuItem:
        """
        Creates an EventMenuItem for the given event.
        Raises ValidationError if the event menu is locked.
        Snapshot fields are frozen automatically inside EventMenuItem.save().
        """
        event = get_object_or_404(Event, pk=event_id)

        if event.menu_locked:
            raise ValidationError(
                f'Menu is locked for event {event.event_code}. '
                'Unlock the event before adding dishes.'
            )

        dish = validated_data.get('dish')
        if dish and EventMenuItem.objects.filter(
            event=event, dish=dish, is_deleted=False
        ).exists():
            raise ValidationError(
                f'"{dish.name}" is already in the menu for this event. '
                'Edit its quantity instead of adding it again.'
            )

        return EventMenuItem.objects.create(event=event, **validated_data)

    @staticmethod
    def remove_dish(instance: EventMenuItem) -> None:
        """
        Soft-deletes a menu item.
        post_save signal fires after soft_delete → CalculationEngine recalculates.
        """
        instance.soft_delete()
