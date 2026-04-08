from django.core.exceptions import ValidationError
from django.db import transaction

from apps.events.models import Event

from .models import Inquiry


class InquiryService:

    @staticmethod
    @transaction.atomic
    def convert_to_event(inquiry: Inquiry) -> Event:
        """
        Creates an Event from inquiry data, marks the inquiry as CONVERTED,
        and links the two via converted_event.
        Raises ValidationError if already converted.
        """
        # Re-fetch with row lock inside the atomic block to prevent races.
        inquiry = Inquiry.objects.select_for_update().get(pk=inquiry.pk)

        if inquiry.converted_event_id is not None:
            raise ValidationError('This inquiry has already been converted to an event.')

        event = Event.objects.create(
            tenant_id      = inquiry.tenant_id,
            customer_name  = inquiry.customer_name,
            contact_number = inquiry.contact_number,
            event_type     = inquiry.event_type,
            event_date     = inquiry.tentative_date,
            guest_count    = inquiry.guest_count,
            service_type   = Event.ServiceType.BUFFET,  # default, staff can update
            notes          = inquiry.notes,
        )

        inquiry.status          = Inquiry.Status.CONVERTED
        inquiry.converted_event = event
        inquiry.save(update_fields=['status', 'converted_event', 'updated_at'])

        return event
