import io

from django.template.loader import render_to_string


def generate_pdf(template_name: str, context: dict) -> bytes:
    """Render an HTML template to PDF bytes using xhtml2pdf."""
    from xhtml2pdf import pisa  # lazy import

    html_string = render_to_string(template_name, context)
    buffer = io.BytesIO()
    result = pisa.CreatePDF(html_string, dest=buffer)
    if result.err:
        raise RuntimeError(f'PDF generation failed: {result.err}')
    return buffer.getvalue()
