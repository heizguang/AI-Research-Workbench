"""source_to_md — Document to Markdown conversion package.

Supported formats:
    - PDF (via PyMuPDF)
    - DOCX (via mammoth)
    - HTML (via beautifulsoup4 + markdownify)
    - XLSX (via openpyxl)
    - PPTX (via python-pptx)
"""

from .pdf_to_md import pdf_to_markdown
from .doc_to_md import docx_to_markdown
from .web_to_md import web_to_markdown

__all__ = [
    'pdf_to_markdown',
    'docx_to_markdown',
    'web_to_markdown',
]
