"""按出版物语义采集 EPUB 正文。

阅读序由 container 指向的 package、manifest 与 spine 决定，不按 ZIP 文件名排序。
非线性资源、导航文档与可复用注释分别归位；脚注被多章引用时只采集一次并保留回跳。
manifest fallback 链限制深度并检测循环，缺资源或循环记入缺失报告，不假装提取完整。
固定版式出版物无法可靠生成阅读序时明确报告 declined，不重排文本。
每个段落携带出版物摘要、资源路径、节点路径三元组；去重只针对同一资源的重复引用。
全程只读取包内字节，不执行书内脚本，不访问外站。
"""
import hashlib
import io
import posixpath
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET
import zipfile

CONTAINER_NS = '{urn:oasis:names:tc:opendocument:xmlns:container}'
OPF_NS = '{http://www.idpf.org/2007/opf}'
EPUB_TYPE = '{http://www.idpf.org/2007/ops}type'
XML_LANG = '{http://www.w3.org/XML/1998/namespace}lang'
XHTML_MEDIA = 'application/xhtml+xml'
MAX_FALLBACK_DEPTH = 8
MAX_RESOURCE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
BLOCK_TAGS = frozenset(
    'address article aside blockquote caption dd details div dl dt figcaption figure'
    ' footer h1 h2 h3 h4 h5 h6 header hr li main nav ol p pre section summary table'
    ' td th tr ul'.split())
SKIP_TAGS = frozenset(('script', 'style'))
RUBY_HIDDEN = frozenset(('rt', 'rp', 'rtc'))
NOTE_TYPES = frozenset(('footnote', 'rearnote'))


class ResourceTooLarge(Exception):
    """单个资源超过解压限制。"""


def local(tag):
    return tag.rsplit('}', 1)[-1] if tag.startswith('{') else tag


def normalize(text):
    return ' '.join(text.split())


def lang_of(element, inherited):
    return element.get(XML_LANG) or element.get('lang') or inherited


def epub_types(element):
    return frozenset((element.get(EPUB_TYPE) or '').split())


def text_content(element):
    parts = []
    if element.text:
        parts.append(element.text)
    for child in element:
        name = local(child.tag)
        if name not in SKIP_TAGS and name not in RUBY_HIDDEN:
            parts.append(text_content(child))
        if child.tail:
            parts.append(child.tail)
    return ''.join(parts)


def ruby_parts(ruby):
    bases = []
    annotations = []
    if ruby.text:
        bases.append(ruby.text)
    for child in ruby:
        name = local(child.tag)
        if name == 'rt':
            annotations.append(text_content(child))
        elif name not in ('rp', 'rtc'):
            bases.append(text_content(child))
        if child.tail:
            bases.append(child.tail)
    return ''.join(bases), ''.join(annotations)


def parse_xml(raw, what):
    if b'<!ENTITY' in raw:
        raise ValueError(what + ' 含有实体定义，已拒绝')
    doctype = raw.find(b'<!DOCTYPE')
    if doctype != -1:
        subset = raw.find(b'[', doctype)
        close = raw.find(b'>', doctype)
        if subset != -1 and (close == -1 or subset < close):
            raise ValueError(what + ' 含有 DTD 内部子集，已拒绝')
    return ET.fromstring(raw)


class DocumentParser:
    """解析单个 XHTML 内容文档为段落、锚点、注释与脚本计数。"""

    def __init__(self, path, digest, language):
        self.path = path
        self.digest = digest
        self.language = language
        self.paragraphs = []
        self.anchors = set()
        self.notes = []
        self.scripts = 0

    def parse(self, root):
        self.walk(root, [local(root.tag) + '[1]'], self.language)
        return self

    def walk(self, element, path, lang):
        tag = local(element.tag)
        if tag in SKIP_TAGS:
            self.scripts += 1
            return
        lang = lang_of(element, lang)
        anchor = element.get('id')
        if anchor:
            self.anchors.add(anchor)
        if epub_types(element) & NOTE_TYPES:
            self.collect_note(element, path, lang)
            return
        if tag in BLOCK_TAGS and not any(
                local(item.tag) in BLOCK_TAGS for item in element.iter() if item is not element):
            self.collect_paragraph(element, tag, path, lang)
            return
        counters = {}
        for child in element:
            name = local(child.tag)
            counters[name] = counters.get(name, 0) + 1
            self.walk(child, path + [name + '[' + str(counters[name]) + ']'], lang)

    def collect_note(self, element, path, lang):
        identifier = element.get('id')
        node = '/'.join(path)
        key = self.path + '#' + identifier if identifier else self.path + '@' + node
        note = {'key': key, 'id': identifier, 'chapter': self.path, 'node': node,
                'language': lang, 'text': normalize(text_content(element)),
                'backlinks': [], 'referenced_by': []}
        for item in element.iter():
            if item.get('id'):
                self.anchors.add(item.get('id'))
            if local(item.tag) == 'a' and item.get('href'):
                link = {'text': normalize(text_content(item)), 'href': item.get('href')}
                types = epub_types(item)
                if types:
                    link['epub_type'] = sorted(types)
                note['backlinks'].append(link)
        self.notes.append(note)

    def collect_paragraph(self, element, tag, path, lang):
        para = {'book': self.digest, 'chapter': self.path, 'node': '/'.join(path),
                'tag': tag, 'language': lang, 'spans': [], 'anchors': [], 'links': []}
        if element.get('id'):
            para['anchors'].append(element.get('id'))
        texts = []
        self.inline(element, lang, para['node'], texts, para)
        para['text'] = normalize(''.join(texts))
        if para['text'] or para['links'] or para['spans']:
            self.paragraphs.append(para)

    def inline(self, element, lang, path, texts, para):
        lang = lang_of(element, lang)
        if element.text:
            texts.append(element.text)
        counters = {}
        for child in element:
            name = local(child.tag)
            counters[name] = counters.get(name, 0) + 1
            cpath = path + '/' + name + '[' + str(counters[name]) + ']'
            self.inline_child(child, lang, cpath, texts, para)
            if child.tail:
                texts.append(child.tail)

    def inline_child(self, child, lang, cpath, texts, para):
        tag = local(child.tag)
        if tag in SKIP_TAGS:
            self.scripts += 1
            return
        anchor = child.get('id')
        if anchor:
            self.anchors.add(anchor)
            if anchor not in para['anchors']:
                para['anchors'].append(anchor)
        clang = lang_of(child, lang)
        if tag == 'ruby':
            base, annotation = ruby_parts(child)
            texts.append(base)
            para['spans'].append({'kind': 'ruby', 'base': normalize(base),
                                  'annotation': normalize(annotation)})
            return
        if tag == 'a' and child.get('href'):
            text = text_content(child)
            texts.append(text)
            link = {'text': normalize(text), 'href': child.get('href'), 'node': cpath}
            types = epub_types(child)
            if types:
                link['epub_type'] = sorted(types)
            para['links'].append(link)
            self.scan_anchors(child, para)
            if clang != lang:
                para['spans'].append({'kind': 'lang', 'language': clang,
                                      'text': normalize(text)})
            return
        if clang != lang:
            text = text_content(child)
            texts.append(text)
            para['spans'].append({'kind': 'lang', 'language': clang, 'text': normalize(text)})
            self.scan_anchors(child, para)
            self.scan_links(child, cpath, para)
            return
        self.inline(child, clang, cpath, texts, para)

    def scan_anchors(self, element, para):
        for item in element.iter():
            anchor = item.get('id')
            if anchor:
                self.anchors.add(anchor)
                if anchor not in para['anchors']:
                    para['anchors'].append(anchor)

    def scan_links(self, element, path, para):
        counters = {}
        for child in element:
            name = local(child.tag)
            counters[name] = counters.get(name, 0) + 1
            cpath = path + '/' + name + '[' + str(counters[name]) + ']'
            if name == 'a' and child.get('href'):
                link = {'text': normalize(text_content(child)),
                        'href': child.get('href'), 'node': cpath}
                types = epub_types(child)
                if types:
                    link['epub_type'] = sorted(types)
                para['links'].append(link)
            self.scan_links(child, cpath, para)


class Collector:
    def __init__(self, archive, digest):
        self.archive = archive
        self.digest = digest
        self.names = set(archive.namelist())
        self.budget = 0
        self.manifest = {}
        self.package_dir = ''
        self.docs = {}
        self.notes = {}
        self.note_order = []
        self.nav_links = []
        self.missing = []

    def read(self, name):
        info = self.archive.getinfo(name)
        if info.file_size > MAX_RESOURCE_BYTES:
            raise ResourceTooLarge(name)
        self.budget += info.file_size
        if self.budget > MAX_TOTAL_BYTES:
            raise ValueError('出版物解压总量超过限制')
        return self.archive.read(name)

    def container_package(self):
        try:
            raw = self.read('META-INF/container.xml')
        except KeyError:
            raise ValueError('缺少 container 入口') from None
        root = parse_xml(raw, 'container 文档')
        roots = root.findall(CONTAINER_NS + 'rootfiles/' + CONTAINER_NS + 'rootfile')
        if not roots or not roots[0].get('full-path'):
            raise ValueError('缺少 package 入口')
        return roots[0].get('full-path')

    def parse_package(self, path):
        try:
            raw = self.read(path)
        except KeyError:
            raise ValueError('缺少 package 文件：' + path) from None
        root = parse_xml(raw, 'package 文档')
        if local(root.tag) != 'package':
            raise ValueError('package 文档无效')
        self.package_dir = posixpath.dirname(path)
        uid = root.get('unique-identifier')
        identifier = title = language = None
        layout = 'reflowable'
        metadata = root.find(OPF_NS + 'metadata')
        if metadata is not None:
            for element in metadata:
                name = local(element.tag)
                text = (element.text or '').strip()
                if not text:
                    continue
                if name == 'identifier' and (identifier is None or (uid and element.get('id') == uid)):
                    identifier = text
                elif name == 'title' and title is None:
                    title = text
                elif name == 'language' and language is None:
                    language = text
                elif name == 'meta' and element.get('property') == 'rendition:layout':
                    layout = text
        manifest = root.find(OPF_NS + 'manifest')
        if manifest is None:
            raise ValueError('package 缺少 manifest')
        for item in manifest:
            if local(item.tag) != 'item' or not item.get('id') or not item.get('href'):
                continue
            self.manifest[item.get('id')] = {
                'id': item.get('id'), 'href': item.get('href'),
                'media_type': item.get('media-type', ''),
                'properties': frozenset((item.get('properties') or '').split()),
                'fallback': item.get('fallback'),
                'path': posixpath.normpath(
                    posixpath.join(self.package_dir, unquote(item.get('href'))))}
        spine_element = root.find(OPF_NS + 'spine')
        spine = []
        if spine_element is not None:
            for ref in spine_element:
                if local(ref.tag) == 'itemref' and ref.get('idref'):
                    spine.append({'idref': ref.get('idref'),
                                  'linear': ref.get('linear', 'yes') != 'no'})
        if not spine:
            raise ValueError('package 缺少 spine')
        return {'spine': spine, 'layout': layout, 'identifier': identifier,
                'title': title, 'language': language}

    def resolve(self, item):
        chain = []
        seen = set()
        current = item
        while True:
            if current['id'] in seen:
                return None, chain, 'fallback-cycle'
            seen.add(current['id'])
            chain.append(current['id'])
            if len(chain) > MAX_FALLBACK_DEPTH:
                return None, chain, 'fallback-depth'
            if current['media_type'] == XHTML_MEDIA and current['path'] in self.names:
                return current['path'], chain, None
            fallback = current.get('fallback')
            if not fallback:
                if current['path'] not in self.names:
                    return None, chain, 'missing-resource'
                return None, chain, 'unsupported-media'
            current = self.manifest.get(fallback)
            if current is None:
                return None, chain, 'fallback-missing'

    def extract_document(self, path, language):
        if path in self.docs:
            return self.docs[path]
        try:
            root = parse_xml(self.read(path), path)
        except ResourceTooLarge:
            self.missing.append({'kind': 'resource-too-large', 'href': path})
            self.docs[path] = None
            return None
        except (ET.ParseError, ValueError) as error:
            self.missing.append({'kind': 'invalid-document', 'href': path,
                                 'reason': str(error)})
            self.docs[path] = None
            return None
        parser = DocumentParser(path, self.digest, language).parse(root)
        self.docs[path] = parser
        for note in parser.notes:
            if note['key'] not in self.notes:
                self.notes[note['key']] = note
                self.note_order.append(note['key'])
        return parser

    def parse_nav(self, item):
        path = item['path']
        if path not in self.names:
            self.missing.append({'kind': 'missing-resource', 'item': item['id'], 'href': path})
            return None
        try:
            root = parse_xml(self.read(path), path)
        except (ResourceTooLarge, ET.ParseError, ValueError) as error:
            self.missing.append({'kind': 'invalid-document', 'href': path, 'reason': str(error)})
            return None
        nav = {'href': path, 'toc': [], 'landmarks': []}
        for element in root.iter():
            if local(element.tag) != 'nav':
                continue
            types = epub_types(element)
            target = 'toc' if 'toc' in types else 'landmarks' if 'landmarks' in types else None
            if target is None:
                continue
            for child in element:
                if local(child.tag) in ('ol', 'ul'):
                    self.nav_list(child, path, nav[target], 1)
        return nav

    def nav_list(self, listing, path, out, depth):
        for item in listing:
            if local(item.tag) != 'li':
                continue
            entry = {'text': '', 'depth': depth}
            for child in item:
                name = local(child.tag)
                if name == 'a' and child.get('href') and 'href' not in entry:
                    entry['text'] = normalize(text_content(child))
                    entry['href'] = child.get('href')
                elif name == 'span' and 'href' not in entry and not entry['text']:
                    entry['text'] = normalize(text_content(child))
            if 'href' in entry:
                self.nav_links.append((entry, path))
            out.append(entry)
            for child in item:
                if local(child.tag) in ('ol', 'ul'):
                    self.nav_list(child, path, out, depth + 1)

    def resolve_link(self, link, chapter, node):
        href = link.get('href') or ''
        parts = urlsplit(href)
        if parts.scheme or parts.netloc:
            link['external'] = True
            return
        link['external'] = False
        if parts.path:
            target = posixpath.normpath(
                posixpath.join(posixpath.dirname(chapter), unquote(parts.path)))
        else:
            target = chapter
        link['target'] = target
        if parts.fragment:
            link['fragment'] = parts.fragment
        if target not in self.names:
            self.missing.append({'kind': 'broken-link', 'chapter': chapter,
                                 'node': node, 'href': href})
            return
        if not parts.fragment:
            return
        if 'noteref' in link.get('epub_type', ()):
            key = target + '#' + parts.fragment
            note = self.notes.get(key)
            if note is None:
                self.missing.append({'kind': 'missing-note', 'chapter': chapter,
                                     'node': node, 'href': href})
            else:
                link['note'] = key
                note['referenced_by'].append({'chapter': chapter, 'node': node})
            return
        doc = self.docs.get(target)
        if doc is not None and parts.fragment not in doc.anchors:
            self.missing.append({'kind': 'broken-anchor', 'chapter': chapter,
                                 'node': node, 'href': href})

    def resolve_links(self):
        for doc in self.docs.values():
            if doc is None:
                continue
            for para in doc.paragraphs:
                for link in para['links']:
                    self.resolve_link(link, para['chapter'], para['node'])
        for note in self.notes.values():
            for link in note['backlinks']:
                self.resolve_link(link, note['chapter'], note['node'])
        for link, path in self.nav_links:
            self.resolve_link(link, path, 'nav')

    def run(self):
        try:
            mimetype = self.archive.read('mimetype')
        except KeyError:
            raise ValueError('不是 EPUB 出版物') from None
        if mimetype != b'application/epub+zip':
            raise ValueError('不是 EPUB 出版物')
        package_path = self.container_package()
        package = self.parse_package(package_path)
        publication = {'identifier': package['identifier'], 'title': package['title'],
                       'language': package['language'], 'digest': self.digest,
                       'package': package_path, 'layout': package['layout']}
        if package['layout'] == 'pre-paginated':
            declared = []
            for ref in package['spine']:
                item = self.manifest.get(ref['idref'])
                if item is None:
                    self.missing.append({'kind': 'spine-missing', 'idref': ref['idref']})
                    continue
                declared.append({'id': item['id'], 'href': item['path'], 'linear': ref['linear']})
                if item['path'] not in self.names:
                    self.missing.append({'kind': 'missing-resource',
                                         'item': item['id'], 'href': item['path']})
            return {'status': 'declined',
                    'reason': '固定版式出版物无法可靠生成阅读序，未重排文本',
                    'publication': publication, 'declared_order': declared,
                    'missing': self.missing}
        navigation = None
        for item in self.manifest.values():
            if 'nav' in item['properties']:
                navigation = self.parse_nav(item)
                break
        reading_order = []
        nonlinear = []
        paragraphs = []
        references = {}
        for ref in package['spine']:
            item = self.manifest.get(ref['idref'])
            if item is None:
                self.missing.append({'kind': 'spine-missing', 'idref': ref['idref']})
                continue
            path, chain, error = self.resolve(item)
            if error is not None:
                entry = {'kind': error, 'item': item['id'], 'href': item['path']}
                if len(chain) > 1:
                    entry['chain'] = chain
                self.missing.append(entry)
                continue
            doc = self.extract_document(path, package['language'])
            if doc is None:
                continue
            first = path not in references
            references[path] = references.get(path, 0) + 1
            if ref['linear']:
                entry = {'index': len(reading_order), 'id': item['id'], 'href': path}
                if len(chain) > 1:
                    entry['via_fallback'] = chain
                if first:
                    entry['paragraphs'] = len(doc.paragraphs)
                    if doc.scripts:
                        entry['scripts_skipped'] = doc.scripts
                    paragraphs.extend(doc.paragraphs)
                else:
                    entry['reused'] = True
                    entry['paragraphs'] = 0
                reading_order.append(entry)
            else:
                entry = {'id': item['id'], 'href': path,
                         'paragraphs': list(doc.paragraphs) if first else []}
                if len(chain) > 1:
                    entry['via_fallback'] = chain
                if not first:
                    entry['reused'] = True
                elif doc.scripts:
                    entry['scripts_skipped'] = doc.scripts
                nonlinear.append(entry)
        for item in self.manifest.values():
            if item['media_type'] == XHTML_MEDIA and item['path'] in self.names:
                self.extract_document(item['path'], package['language'])
        self.resolve_links()
        return {'status': 'partial' if self.missing else 'ok',
                'publication': publication,
                'reading_order': reading_order,
                'nonlinear': nonlinear,
                'navigation': navigation,
                'paragraphs': paragraphs,
                'notes': [self.notes[key] for key in self.note_order],
                'deduplicated': [{'href': path, 'references': count}
                                 for path, count in references.items() if count > 1],
                'missing': self.missing}


def collect_publication(data):
    digest = hashlib.sha256(data).hexdigest()
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise ValueError('不是 EPUB 出版物') from None
    with archive:
        return Collector(archive, digest).run()
