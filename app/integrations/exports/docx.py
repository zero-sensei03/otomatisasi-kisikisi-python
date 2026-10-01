from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import xml.etree.ElementTree as ET


TEMPLATE_DIR = Path("app/templates/docx_templates")
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
ET.register_namespace("w", W)
ET.register_namespace("r", R)

TEMPLATES = {
    "materi": "Template Materi.docx",
    "soal_1": "Template Soal 1.docx",
    "soal_2": "Template Soal 2.docx",
    "pembahasan": "Template Pembahasan.docx",
    "kisi_kisi": "Template Kisi Kisi.docx",
}


def _tag(name: str) -> str:
    return f"{{{W}}}{name}"


def ensure_templates() -> None:
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>'''
    rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'''
    document_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>'''
    styles = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles xmlns:w="{W}"><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:rPr><w:sz w:val="22"/><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/></w:rPr><w:pPr><w:spacing w:after="120"/></w:pPr></w:style><w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:rPr><w:b/><w:sz w:val="32"/><w:color w:val="8A6426"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:rPr><w:b/><w:sz w:val="26"/></w:rPr></w:style></w:styles>'''
    empty_document = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="{W}"><w:body><w:p/><w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/></w:sectPr></w:body></w:document>'''
    for filename in TEMPLATES.values():
        path = TEMPLATE_DIR / filename
        if path.exists():
            continue
        with ZipFile(path, "w", ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", content_types)
            archive.writestr("_rels/.rels", rels)
            archive.writestr("word/document.xml", empty_document)
            archive.writestr("word/_rels/document.xml.rels", document_rels)
            archive.writestr("word/styles.xml", styles)


def _paragraph(text: str, style: str | None = None):
    p = ET.Element(_tag("p"))
    if style:
        ppr = ET.SubElement(p, _tag("pPr"))
        ET.SubElement(ppr, _tag("pStyle"), {_tag("val"): style})
    r = ET.SubElement(p, _tag("r"))
    t = ET.SubElement(r, _tag("t"), {"{http://www.w3.org/XML/1998/namespace}space": "preserve"})
    t.text = text
    return p


def _cell(text: str | list[str], *, header: bool = False, width: int | None = None):
    cell = ET.Element(_tag("tc"))
    props = ET.SubElement(cell, _tag("tcPr"))
    if width is not None:
        ET.SubElement(props, _tag("tcW"), {_tag("w"): str(width), _tag("type"): "dxa"})
    if header:
        ET.SubElement(props, _tag("shd"), {_tag("fill"): "F6EDDC", _tag("val"): "clear"})
    for paragraph in text if isinstance(text, list) else [text]:
        cell.append(_paragraph(paragraph))
    return cell


def _table(rows: list[list[str | list[str]]], widths: list[int] | None = None):
    table = ET.Element(_tag("tbl"))
    props = ET.SubElement(table, _tag("tblPr"))
    ET.SubElement(props, _tag("tblBorders"))
    if widths:
        ET.SubElement(props, _tag("tblW"), {_tag("w"): str(sum(widths)), _tag("type"): "dxa"})
        ET.SubElement(props, _tag("tblLayout"), {_tag("type"): "fixed"})
        grid = ET.SubElement(table, _tag("tblGrid"))
        for width in widths:
            ET.SubElement(grid, _tag("gridCol"), {_tag("w"): str(width)})
    for row_number, values in enumerate(rows):
        row = ET.SubElement(table, _tag("tr"))
        for index, value in enumerate(values):
            width = widths[index] if widths else None
            row.append(_cell(value if isinstance(value, list) else str(value), header=row_number == 0, width=width))
    return table


def build_generation_docx(template_key: str, generation, *, selected: list[int] | None = None) -> BytesIO:
    ensure_templates()
    if template_key not in TEMPLATES:
        raise ValueError("Template export tidak tersedia.")
    with ZipFile(TEMPLATE_DIR / TEMPLATES[template_key]) as source:
        files = {name: source.read(name) for name in source.namelist()}

    root = ET.Element(_tag("document"))
    body = ET.SubElement(root, _tag("body"))
    body.append(_paragraph(generation.title, "Title"))
    body.append(_paragraph(f"{generation.subject} · Kelas {generation.class_name}"))
    if generation.description:
        body.append(_paragraph(generation.description))

    if template_key == "materi":
        body.append(_paragraph("Rangkuman Materi", "Heading1"))
        for paragraph in (generation.summary or "").splitlines():
            if paragraph.strip():
                body.append(_paragraph(paragraph.strip()))
    elif template_key in {"soal_1", "soal_2"}:
        questions = [q for q in generation.questions if selected is None or q.number in selected]
        if template_key == "soal_2":
            table_rows = [["No.", "Soal", "Pilihan"]]
            for q in questions:
                options = [f"{o.label}. {o.text}" for o in q.options] or ["—"]
                table_rows.append([str(q.number), q.question, options])
            body.append(_table(table_rows, widths=[720, 5000, 3880]))
        else:
            for q in questions:
                body.append(_paragraph(f"{q.number}. {q.question}", "Heading1"))
                for option in q.options:
                    body.append(_paragraph(f"{option.label}. {option.text}"))
    elif template_key == "pembahasan":
        for q in generation.questions:
            body.append(_paragraph(f"{q.number}. {q.question}", "Heading1"))
            body.append(_paragraph(f"Jawaban: {q.answer}"))
            body.append(_paragraph(f"Pembahasan: {q.explanation}"))
    else:
        for bp in sorted(generation.blueprints, key=lambda item: item.number):
            body.append(_paragraph(f"Kisi-kisi {bp.number} · Soal {bp.question_number}", "Heading1"))
            body.append(_paragraph(f"Topik materi: {bp.material_topic}"))
            body.append(_paragraph(f"Tujuan pembelajaran: {bp.learning_objective}"))
            body.append(_paragraph(f"Indikator: {bp.indicator}"))
            body.append(_paragraph(f"Level kognitif: {bp.cognitive_level} · Kesulitan: {bp.difficulty}"))

    sect = ET.SubElement(body, _tag("sectPr"))
    ET.SubElement(sect, _tag("pgSz"), {_tag("w"): "11906", _tag("h"): "16838"})
    ET.SubElement(sect, _tag("pgMar"), {_tag("top"): "1134", _tag("right"): "1134", _tag("bottom"): "1134", _tag("left"): "1134"})
    files["word/document.xml"] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    output.seek(0)
    return output
