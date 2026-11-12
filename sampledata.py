import io
import zipfile

def samples():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(zipfile.ZipInfo('mimetype', (2026, 1, 1, 0, 0, 0)), 'application/epub+zip')
        archive.writestr(zipfile.ZipInfo('META-INF/container.xml', (2026, 1, 1, 0, 0, 0)), '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OPS/book.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        archive.writestr(zipfile.ZipInfo('OPS/book.opf', (2026, 1, 1, 0, 0, 0)), '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="book"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="book">local:manual</dc:identifier><dc:title>Manual</dc:title><dc:language>en</dc:language></metadata><manifest><item id="chapter" href="chapter.xhtml" media-type="application/xhtml+xml"/><item id="notes" href="notes.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="chapter"/><itemref idref="notes" linear="no"/></spine></package>')
        archive.writestr(zipfile.ZipInfo('OPS/chapter.xhtml', (2026, 1, 1, 0, 0, 0)), '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><body><h1 id="start">Safety</h1><p>Use gloves<a epub:type="noteref" href="notes.xhtml#n1">1</a>.</p></body></html>')
        archive.writestr(zipfile.ZipInfo('OPS/notes.xhtml', (2026, 1, 1, 0, 0, 0)), '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><body><aside epub:type="footnote" id="n1">Dry gloves</aside></body></html>')
    return {'sample.epub': buffer.getvalue(), 'invalid.epub': b'not a zip'}
