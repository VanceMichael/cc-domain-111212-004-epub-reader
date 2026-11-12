import io
import zipfile
import xml.etree.ElementTree as ET

def inspect_bytes(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if archive.read('mimetype') != b'application/epub+zip':
            raise ValueError('不是 EPUB 出版物')
        container = ET.fromstring(archive.read('META-INF/container.xml'))
        namespace = '{urn:oasis:names:tc:opendocument:xmlns:container}'
        roots = container.findall(namespace + 'rootfiles/' + namespace + 'rootfile')
        if not roots:
            raise ValueError('缺少 package 入口')
        root_path = roots[0].attrib['full-path']
        return [{'path': item.filename, 'size': item.file_size, 'package': root_path}
                for item in archive.infolist() if not item.is_dir()]
