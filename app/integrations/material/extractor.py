from dataclasses import dataclass
from pathlib import PurePath

from app.integrations.material.docx_extractor import extract_docx
from app.integrations.material.pdf_extractor import extract_pdf


@dataclass(frozen=True)
class ExtractedMaterial:
    filename: str
    mime_type: str
    text: str


class MaterialExtractor:
    MIME_TYPES = {".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".pdf": "application/pdf"}

    def extract(self, filename: str, mime_type: str, data: bytes, max_size: int) -> ExtractedMaterial:
        extension = PurePath(filename).suffix.lower()
        expected_mime = self.MIME_TYPES.get(extension)
        if not expected_mime or mime_type not in (expected_mime, "application/octet-stream"):
            raise ValueError("File harus berupa DOCX atau PDF yang valid.")
        if not data or len(data) > max_size:
            raise ValueError("File kosong atau melebihi batas ukuran.")
        if extension == ".pdf":
            if not data.startswith(b"%PDF-"):
                raise ValueError("File PDF tidak valid.")
            text = extract_pdf(data)
        else:
            text = extract_docx(data)
        text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        if not text:
            raise ValueError("Teks tidak dapat diekstrak dari file.")
        return ExtractedMaterial(filename, expected_mime, text)
