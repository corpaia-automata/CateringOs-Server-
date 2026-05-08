"""HTML → PDF helpers for quotations (shared by API + admin actions)."""

import io
import re


def safe_quotation_pdf_filename(tenant_name: str, quote_number: str) -> str:
    base = re.sub(r'[^\w\-]+', '_', (tenant_name or 'Quotation').strip())[:80]
    safe_q = re.sub(r'[^\w\-]+', '_', quote_number or 'draft')
    return f'{base}-QTN-{safe_q}.pdf'


def _resolve_css_vars(html: str) -> str:
    """Inline CSS custom-property values so xhtml2pdf (no var() support) can render them."""
    root_block = re.search(r':root\s*\{([^}]+)\}', html)
    vars_map: dict[str, str] = {}
    if root_block:
        for m in re.finditer(r'--([\w-]+)\s*:\s*([^;]+);', root_block.group(1)):
            vars_map[f'--{m.group(1)}'] = m.group(2).strip()

    def _replace(m: re.Match) -> str:
        name = m.group(1).strip()
        fallback = (m.group(2) or '').strip()
        return vars_map.get(name, fallback or 'inherit')

    return re.sub(r'var\(\s*(--[\w-]+)\s*(?:,\s*([^)]+))?\s*\)', _replace, html)


def html_to_pdf_bytes(html_string: str, base_url: str | None = None) -> bytes:
    # 1. Playwright / Chromium — handles modern CSS, works on Windows without native libs
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page()
            page.set_content(html_string, wait_until='networkidle')
            pdf = page.pdf(format='A4', print_background=True)
            browser.close()
        return pdf
    except Exception:
        pass

    # 2. WeasyPrint — works on Linux/Mac with GTK installed
    try:
        from weasyprint import HTML

        kw = {'string': html_string}
        if base_url:
            kw['base_url'] = base_url
        return HTML(**kw).write_pdf()
    except Exception:
        pass

    # 3. xhtml2pdf last-resort fallback
    from xhtml2pdf import pisa

    buffer = io.BytesIO()
    result = pisa.CreatePDF(_resolve_css_vars(html_string), dest=buffer)
    if result.err:
        raise RuntimeError('PDF generation failed')
    return buffer.getvalue()
