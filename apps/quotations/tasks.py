"""Celery tasks for quotation workflows."""

import logging

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from celery import shared_task
from django.conf import settings

from .models import Quotation
from .pdf_service import PDFGenerationError, generate_pdf_for_quotation

logger = logging.getLogger(__name__)


def _s3_object_https_url(bucket: str, region: str, key: str) -> str:
    """Virtual-hosted-style object URL (suitable for saving on ``Quotation.pdf_url``)."""
    from urllib.parse import quote

    safe_key = quote(key, safe='/')
    if not region or region == 'us-east-1':
        return f'https://{bucket}.s3.amazonaws.com/{safe_key}'
    return f'https://{bucket}.s3.{region}.amazonaws.com/{safe_key}'


def _upload_pdf_to_s3(*, bucket: str, key: str, body: bytes, region: str) -> str:
    session_kwargs = {'region_name': region}
    if getattr(settings, 'AWS_ACCESS_KEY_ID', None):
        session_kwargs['aws_access_key_id'] = settings.AWS_ACCESS_KEY_ID
    if getattr(settings, 'AWS_SECRET_ACCESS_KEY', None):
        session_kwargs['aws_secret_access_key'] = settings.AWS_SECRET_ACCESS_KEY
    client = boto3.client('s3', **session_kwargs)
    try:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType='application/pdf',
        )
    except (ClientError, BotoCoreError) as exc:
        logger.exception('S3 upload failed bucket=%s key=%s', bucket, key)
        raise PDFGenerationError(f'S3 upload failed: {exc}') from exc
    return _s3_object_https_url(bucket, region, key)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    name='quotations.generate_quotation_pdf',
)
def generate_quotation_pdf(self, quotation_id: str) -> str:
    """
    Capture the public quotation page as PDF (Playwright) and store it on S3.

    Updates ``Quotation.pdf_url`` on success.
    """
    logger.info('generate_quotation_pdf started quotation_id=%s task_id=%s', quotation_id, self.request.id)

    try:
        pdf_bytes = generate_pdf_for_quotation(quotation_id)
    except PDFGenerationError as exc:
        logger.warning(
            'PDF generation failed (will retry if allowed) quotation_id=%s error=%s',
            quotation_id,
            exc,
        )
        raise self.retry(exc=exc)

    bucket = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', '') or ''
    region = getattr(settings, 'AWS_S3_REGION_NAME', '') or 'us-east-1'
    if not bucket:
        exc = PDFGenerationError('AWS_STORAGE_BUCKET_NAME is not configured')
        logger.error(str(exc))
        raise self.retry(exc=exc)

    try:
        quotation = Quotation.objects.select_related('tenant').get(pk=quotation_id, is_deleted=False)
    except Quotation.DoesNotExist as exc:
        msg = f'Quotation not found for S3 upload: {quotation_id}'
        logger.error(msg)
        raise PDFGenerationError(msg) from exc
    key = f'quotations/{quotation.tenant.slug}/{quotation.public_token}.pdf'

    try:
        pdf_url = _upload_pdf_to_s3(bucket=bucket, key=key, body=pdf_bytes, region=region)
    except PDFGenerationError as exc:
        logger.warning(
            'S3 upload failed (will retry if allowed) quotation_id=%s error=%s',
            quotation_id,
            exc,
        )
        raise self.retry(exc=exc)

    quotation.pdf_url = pdf_url
    quotation.save(update_fields=['pdf_url', 'updated_at'])
    logger.info(
        'generate_quotation_pdf succeeded quotation_id=%s pdf_url=%s bytes=%s',
        quotation_id,
        pdf_url,
        len(pdf_bytes),
    )
    return pdf_url
