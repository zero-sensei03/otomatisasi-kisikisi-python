from __future__ import annotations

from io import BytesIO
from zipfile import ZipFile

import pytest

from app.integrations.material.extractor import MaterialExtractor


def docx_payload(text: str) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>",
        )
    return output.getvalue()


def test_docx_extraction_normalizes_whitespace_and_returns_detected_mime():
    extracted = MaterialExtractor().extract(
        "materi.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        docx_payload(" Materi penting "),
        10_000,
    )
    assert extracted.filename == "materi.docx"
    assert extracted.text == "Materi penting"
    assert extracted.mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@pytest.mark.parametrize(
    ("filename", "mime", "content", "limit", "message"),
    [
        ("materi.txt", "text/plain", b"Isi", 100, "DOCX atau PDF"),
        ("materi.pdf", "application/pdf", b"", 100, "kosong"),
        ("materi.pdf", "application/pdf", b"%PDF-data", 4, "ukuran"),
        ("materi.pdf", "application/pdf", b"bukan-pdf", 100, "PDF tidak valid"),
    ],
)
def test_material_extractor_rejects_invalid_file(filename, mime, content, limit, message):
    with pytest.raises(ValueError, match=message):
        MaterialExtractor().extract(filename, mime, content, limit)


def test_material_extractor_rejects_docx_that_contains_no_extractable_text():
    with pytest.raises(ValueError, match="Teks tidak dapat diekstrak"):
        MaterialExtractor().extract(
            "materi.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            docx_payload("   "),
            10_000,
        )


def test_pdf_extraction_reads_text_operator_and_ignores_invalid_compressed_stream():
    from app.integrations.material.pdf_extractor import extract_pdf

    data = b"%PDF-1.7\nstream\n(Contoh PDF) Tj\nendstream\nstream\nnot-zlib\nendstream"
    assert "Contoh PDF" in extract_pdf(data)
