"""Playwright-based PDF capture for public quotation pages."""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)


class PDFGenerationError(Exception):
    """Raised when Playwright PDF capture fails or prerequisites are missing."""


def _normalize_site_url(base: str) -> str:
    return (base or '').strip().rstrip('/')


def generate_pdf_for_quotation(quotation_id: str) -> bytes:
    """
    Render the public quote page in headless Chromium and return PDF bytes.

    Expects ``settings.SITE_URL`` (public app origin) and a reachable ``/q/<token>?print=true`` route.
    """
    from .models import Quotation

    try:
        quotation = Quotation.objects.select_related('tenant').get(pk=quotation_id, is_deleted=False)
    except Quotation.DoesNotExist as exc:
        msg = f'Quotation not found or inactive: {quotation_id}'
        logger.error(msg)
        raise PDFGenerationError(msg) from exc

    site = _normalize_site_url(getattr(settings, 'SITE_URL', '') or '')
    if not site:
        msg = 'SITE_URL is not configured'
        logger.error(msg)
        raise PDFGenerationError(msg)

    token_str = str(quotation.public_token)
    path = f'/q/{token_str}?print=true'
    url = f'{site}{path}'
    logger.info('Starting PDF capture for quotation_id=%s url=%s', quotation_id, url)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        msg = 'playwright is not installed (pip install playwright && playwright install chromium)'
        logger.error(msg)
        raise PDFGenerationError(msg) from exc

    try:
        with sync_playwright() as p:
            browser: Any = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(url, wait_until='networkidle')
                pdf_bytes: bytes = page.pdf(
                    format='A4',
                    print_background=True,
                    margin={
                        'top': '12mm',
                        'right': '12mm',
                        'bottom': '12mm',
                        'left': '12mm',
                    },
                )
            finally:
                browser.close()
    except Exception as exc:
        logger.exception('Playwright PDF capture failed for quotation_id=%s', quotation_id)
        raise PDFGenerationError(f'Playwright PDF capture failed: {exc}') from exc

    if not pdf_bytes:
        msg = 'Playwright returned empty PDF bytes'
        logger.error('%s quotation_id=%s', msg, quotation_id)
        raise PDFGenerationError(msg)

    logger.info('PDF capture succeeded quotation_id=%s bytes=%s', quotation_id, len(pdf_bytes))
    return pdf_bytes
