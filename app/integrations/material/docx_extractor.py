from io import BytesIO
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree

MAX_DOCUMENT_XML_BYTES = 25 * 1024 * 1024


def extract_docx(data: bytes) -> str:
    try:
        with ZipFile(BytesIO(data)) as archive:
            document = archive.getinfo("word/document.xml")
            if document.file_size > MAX_DOCUMENT_XML_BYTES:
                raise ValueError("Konten DOCX terlalu besar untuk diproses.")
            xml = archive.read(document)
        declaration = xml.upper()
        if b"<!DOCTYPE" in declaration or b"<!ENTITY" in declaration:
            raise ValueError("Deklarasi XML eksternal tidak diizinkan.")
        parser = ElementTree.XMLParser()  # noqa: S314 - DTD/entity declarations are rejected above.
        parser.feed(xml)
        root = parser.close()
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        paragraphs = []
        for paragraph in root.findall(".//w:p", ns):
            text = "".join(node.text or "" for node in paragraph.findall(".//w:t", ns))
            if text.strip():
                paragraphs.append(text)
        return "\n".join(paragraphs)
    except (BadZipFile, KeyError, ElementTree.ParseError) as exc:
        raise ValueError("File DOCX tidak dapat dibaca.") from exc
