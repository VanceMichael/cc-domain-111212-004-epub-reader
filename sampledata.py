import io
import zipfile

DATE = (2026, 1, 1, 0, 0, 0)
CONTAINER = ('<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
             '<rootfiles><rootfile full-path="{package}" '
             'media-type="application/oebps-package+xml"/></rootfiles></container>')


def epub(entries):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(zipfile.ZipInfo('mimetype', DATE), 'application/epub+zip')
        for name, content in entries:
            archive.writestr(zipfile.ZipInfo(name, DATE), content)
    return buffer.getvalue()


SAMPLE_OPF = ('<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
              'unique-identifier="book"><metadata '
              'xmlns:dc="http://purl.org/dc/elements/1.1/">'
              '<dc:identifier id="book">local:manual</dc:identifier>'
              '<dc:title>Manual</dc:title><dc:language>en</dc:language></metadata>'
              '<manifest><item id="chapter" href="chapter.xhtml" '
              'media-type="application/xhtml+xml"/><item id="notes" href="notes.xhtml" '
              'media-type="application/xhtml+xml"/></manifest>'
              '<spine><itemref idref="chapter"/><itemref idref="notes" linear="no"/></spine>'
              '</package>')
SAMPLE_CHAPTER = ('<html xmlns="http://www.w3.org/1999/xhtml" '
                  'xmlns:epub="http://www.idpf.org/2007/ops"><body>'
                  '<h1 id="start">Safety</h1>'
                  '<p>Use gloves<a epub:type="noteref" href="notes.xhtml#n1">1</a>.</p>'
                  '</body></html>')
SAMPLE_NOTES = ('<html xmlns="http://www.w3.org/1999/xhtml" '
                'xmlns:epub="http://www.idpf.org/2007/ops"><body>'
                '<aside epub:type="footnote" id="n1">Dry gloves</aside></body></html>')

MANUAL_OPF = ('<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
              'unique-identifier="pub-id"><metadata '
              'xmlns:dc="http://purl.org/dc/elements/1.1/">'
              '<dc:identifier id="pub-id">local:demo-manual</dc:identifier>'
              '<dc:title>虚构设备维护手册</dc:title>'
              '<dc:language>zh-CN</dc:language>'
              '<meta property="dcterms:modified">2026-01-01T00:00:00Z</meta></metadata>'
              '<manifest>'
              '<item id="nav" href="f-nav.xhtml" media-type="application/xhtml+xml" '
              'properties="nav"/>'
              '<item id="intro" href="c-intro.xhtml" media-type="application/xhtml+xml"/>'
              '<item id="intro-again" href="c-intro.xhtml" '
              'media-type="application/xhtml+xml"/>'
              '<item id="chap1" href="a-chap1.xhtml" media-type="application/xhtml+xml"/>'
              '<item id="chap2" href="b-chap2.xhtml" media-type="application/xhtml+xml"/>'
              '<item id="appendix" href="d-appendix.xhtml" '
              'media-type="application/xhtml+xml"/>'
              '<item id="notes" href="e-notes.xhtml" media-type="application/xhtml+xml"/>'
              '<item id="fancy" href="h-fancy.xhtml" media-type="application/xhtml+xml" '
              'fallback="plain"/>'
              '<item id="plain" href="g-plain.xhtml" media-type="application/xhtml+xml"/>'
              '<item id="ghost" href="i-ghost.xhtml" media-type="application/xhtml+xml"/>'
              '<item id="loop-a" href="j-loop-a.xhtml" media-type="application/xhtml+xml" '
              'fallback="loop-b"/>'
              '<item id="loop-b" href="j-loop-b.xhtml" media-type="application/xhtml+xml" '
              'fallback="loop-a"/>'
              '<item id="photo" href="k-photo.jpg" media-type="image/jpeg"/>'
              '</manifest><spine>'
              '<itemref idref="intro"/><itemref idref="chap1"/><itemref idref="chap2"/>'
              '<itemref idref="intro-again"/><itemref idref="fancy"/>'
              '<itemref idref="ghost"/><itemref idref="loop-a"/><itemref idref="photo"/>'
              '<itemref idref="nowhere"/>'
              '<itemref idref="appendix" linear="no"/><itemref idref="notes" linear="no"/>'
              '</spine></package>')
MANUAL_NAV = ('<html xmlns="http://www.w3.org/1999/xhtml" '
              'xmlns:epub="http://www.idpf.org/2007/ops"><body>'
              '<nav epub:type="toc"><h1>目录</h1><ol>'
              '<li><a href="c-intro.xhtml">引言</a></li>'
              '<li><a href="a-chap1.xhtml">安全须知</a><ol>'
              '<li><a href="a-chap1.xhtml#p3">术语注音示例</a></li></ol></li>'
              '<li><a href="b-chap2.xhtml#s2">例行保养</a></li>'
              '<li><a href="d-appendix.xhtml">附录</a></li>'
              '</ol></nav>'
              '<nav epub:type="landmarks"><ol>'
              '<li><a epub:type="bodymatter" href="c-intro.xhtml">正文开始</a></li>'
              '</ol></nav></body></html>')
MANUAL_INTRO = ('<html xmlns="http://www.w3.org/1999/xhtml"><body>'
                '<h1 id="top">虚构设备维护手册</h1>'
                '<p>本手册所有内容均为虚构，仅用于本地演示。</p></body></html>')
MANUAL_CHAP1 = ('<html xmlns="http://www.w3.org/1999/xhtml" '
                'xmlns:epub="http://www.idpf.org/2007/ops">'
                '<head><title>安全须知</title></head><body><section id="s1">'
                '<h1>安全须知</h1>'
                '<p id="p1">操作前请佩戴防护手套'
                '<a epub:type="noteref" href="e-notes.xhtml#n1">[注1]</a>'
                '，并确认设备已断电。</p>'
                '<p id="p2">警告：虚构高温表面，请勿触摸。</p>'
                '<p id="p3" xml:lang="ja">部品の<ruby>交換<rt>こうかん</rt></ruby>'
                '手順を参照。</p>'
                '<p id="p4">详见<a href="b-chap2.xhtml#s2">例行保养</a>与'
                '<a href="#p1">本节开头</a>；工具 <span xml:lang="en">torque wrench</span>'
                ' 见附录。</p>'
                '<p id="p5">外部资料：<a href="https://example.invalid/manual">示例外链</a>'
                '，仅记录不访问。</p>'
                '<script>alert(1)</script>'
                '</section></body></html>')
MANUAL_CHAP2 = ('<html xmlns="http://www.w3.org/1999/xhtml" '
                'xmlns:epub="http://www.idpf.org/2007/ops"><body><section id="s2">'
                '<h1>例行保养</h1>'
                '<p id="p1">每季度检查密封件'
                '<a epub:type="noteref" href="e-notes.xhtml#n1">[注1]</a>'
                '，并记录状态。</p>'
                '<p id="p2">警告：虚构高温表面，请勿触摸。</p>'
                '<p id="p3">扭矩值参见<a href="i-ghost.xhtml">不存在的章节</a>与'
                '<a href="e-notes.xhtml#n99">缺失的锚点</a>。</p>'
                '<p id="p4">另见<a epub:type="noteref" href="e-notes.xhtml#n77">[注?]</a>'
                '这条未收录的注释。</p>'
                '</section></body></html>')
MANUAL_APPENDIX = ('<html xmlns="http://www.w3.org/1999/xhtml"><body>'
                   '<h1 id="apx">附录：扭矩对照</h1>'
                   '<p>虚构数值：M6 对应 9 N·m。</p></body></html>')
MANUAL_NOTES = ('<html xmlns="http://www.w3.org/1999/xhtml" '
                'xmlns:epub="http://www.idpf.org/2007/ops"><body>'
                '<section id="note-list"><h1>注释</h1>'
                '<aside epub:type="footnote" id="n1"><p>手套需保持干燥，虚构说明。'
                '<a href="a-chap1.xhtml#p1">返回正文</a></p></aside>'
                '<aside epub:type="footnote" id="n2"><p>虚构备件编号仅用于演示。</p></aside>'
                '</section></body></html>')
MANUAL_PLAIN = ('<html xmlns="http://www.w3.org/1999/xhtml"><body>'
                '<h1>增强说明（简版）</h1>'
                '<p>此替代内容由 manifest fallback 提供，数值为虚构。</p></body></html>')
MANUAL_PHOTO = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9'

FIXED_OPF = ('<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
             'unique-identifier="fid"><metadata '
             'xmlns:dc="http://purl.org/dc/elements/1.1/">'
             '<dc:identifier id="fid">local:fixed-demo</dc:identifier>'
             '<dc:title>虚构固定版式图册</dc:title><dc:language>zh-CN</dc:language>'
             '<meta property="rendition:layout">pre-paginated</meta></metadata>'
             '<manifest><item id="page1" href="page1.xhtml" '
             'media-type="application/xhtml+xml"/></manifest>'
             '<spine><itemref idref="page1"/></spine></package>')
FIXED_PAGE = ('<html xmlns="http://www.w3.org/1999/xhtml"><body>'
              '<h1>固定版式第一页</h1></body></html>')


def samples():
    sample = epub([
        ('META-INF/container.xml', CONTAINER.format(package='OPS/book.opf')),
        ('OPS/book.opf', SAMPLE_OPF),
        ('OPS/chapter.xhtml', SAMPLE_CHAPTER),
        ('OPS/notes.xhtml', SAMPLE_NOTES),
    ])
    # 条目顺序刻意打乱：ZIP 顺序与文件名排序都和 spine 阅读序不同。
    manual = epub([
        ('OPS/e-notes.xhtml', MANUAL_NOTES),
        ('OPS/k-photo.jpg', MANUAL_PHOTO),
        ('OPS/b-chap2.xhtml', MANUAL_CHAP2),
        ('META-INF/container.xml', CONTAINER.format(package='OPS/manual.opf')),
        ('OPS/g-plain.xhtml', MANUAL_PLAIN),
        ('OPS/manual.opf', MANUAL_OPF),
        ('OPS/f-nav.xhtml', MANUAL_NAV),
        ('OPS/d-appendix.xhtml', MANUAL_APPENDIX),
        ('OPS/a-chap1.xhtml', MANUAL_CHAP1),
        ('OPS/c-intro.xhtml', MANUAL_INTRO),
    ])
    fixed = epub([
        ('META-INF/container.xml', CONTAINER.format(package='OPS/fixed.opf')),
        ('OPS/fixed.opf', FIXED_OPF),
        ('OPS/page1.xhtml', FIXED_PAGE),
    ])
    return {'sample.epub': sample, 'invalid.epub': b'not a zip',
            'manual.epub': manual, 'fixed.epub': fixed}
