import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import app
from collect import collect_publication
from sampledata import samples

class CollectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = samples()
        cls.manual = cls.fixtures['manual.epub']
        cls.report = collect_publication(cls.manual)

    def test_reading_order_follows_spine_not_zip_or_name_order(self):
        hrefs = [entry['href'] for entry in self.report['reading_order']]
        self.assertEqual(hrefs, ['OPS/c-intro.xhtml', 'OPS/a-chap1.xhtml',
                                 'OPS/b-chap2.xhtml', 'OPS/c-intro.xhtml',
                                 'OPS/g-plain.xhtml'])
        with zipfile.ZipFile(io.BytesIO(self.manual)) as archive:
            names = archive.namelist()
        self.assertLess(names.index('OPS/a-chap1.xhtml'), names.index('OPS/c-intro.xhtml'))
        self.assertNotEqual(hrefs, sorted(hrefs))

    def test_status_partial_and_missing_report(self):
        self.assertEqual(self.report['status'], 'partial')
        kinds = [entry['kind'] for entry in self.report['missing']]
        for kind in ('missing-resource', 'fallback-cycle', 'unsupported-media',
                     'spine-missing', 'broken-link', 'broken-anchor', 'missing-note'):
            self.assertIn(kind, kinds)
        cycle = next(entry for entry in self.report['missing']
                     if entry['kind'] == 'fallback-cycle')
        self.assertEqual(cycle['chain'], ['loop-a', 'loop-b'])
        ghost = next(entry for entry in self.report['missing']
                     if entry['kind'] == 'missing-resource')
        self.assertEqual(ghost['href'], 'OPS/i-ghost.xhtml')

    def test_nav_and_notes_stay_out_of_reading_order(self):
        linear = [entry['href'] for entry in self.report['reading_order']]
        nonlinear = [entry['href'] for entry in self.report['nonlinear']]
        self.assertEqual(nonlinear, ['OPS/d-appendix.xhtml', 'OPS/e-notes.xhtml'])
        self.assertNotIn('OPS/f-nav.xhtml', linear + nonlinear)
        chapters = [para['chapter'] for para in self.report['paragraphs']]
        self.assertNotIn('OPS/e-notes.xhtml', chapters)
        self.assertNotIn('OPS/f-nav.xhtml', chapters)
        toc = self.report['navigation']['toc']
        self.assertIn('安全须知', [entry['text'] for entry in toc])
        nested = next(entry for entry in toc if entry['text'] == '术语注音示例')
        self.assertEqual(nested['depth'], 2)
        self.assertEqual(nested['target'], 'OPS/a-chap1.xhtml')
        self.assertEqual(nested['fragment'], 'p3')

    def test_shared_footnote_collected_once_with_backlink(self):
        notes = {note['key']: note for note in self.report['notes']}
        self.assertEqual(sorted(notes), ['OPS/e-notes.xhtml#n1', 'OPS/e-notes.xhtml#n2'])
        note = notes['OPS/e-notes.xhtml#n1']
        self.assertEqual([ref['chapter'] for ref in note['referenced_by']],
                         ['OPS/a-chap1.xhtml', 'OPS/b-chap2.xhtml'])
        backlink = note['backlinks'][0]
        self.assertEqual(backlink['target'], 'OPS/a-chap1.xhtml')
        self.assertEqual(backlink['fragment'], 'p1')
        self.assertFalse(any('手套需保持干燥' in para['text']
                             for para in self.report['paragraphs']))

    def test_fallback_resolution_and_same_resource_dedup(self):
        entries = {entry['id']: entry for entry in self.report['reading_order']}
        self.assertEqual(entries['fancy']['href'], 'OPS/g-plain.xhtml')
        self.assertEqual(entries['fancy']['via_fallback'], ['fancy', 'plain'])
        self.assertTrue(entries['intro-again']['reused'])
        self.assertEqual(self.report['deduplicated'],
                         [{'href': 'OPS/c-intro.xhtml', 'references': 2}])
        intro = [para for para in self.report['paragraphs']
                 if para['chapter'] == 'OPS/c-intro.xhtml']
        self.assertEqual(len(intro), 2)

    def test_identical_text_in_distinct_resources_not_merged(self):
        warnings = [para for para in self.report['paragraphs']
                    if para['text'] == '警告：虚构高温表面，请勿触摸。']
        self.assertEqual(len(warnings), 2)
        self.assertEqual({para['chapter'] for para in warnings},
                         {'OPS/a-chap1.xhtml', 'OPS/b-chap2.xhtml'})

    def test_ruby_language_links_and_anchors(self):
        ja = next(para for para in self.report['paragraphs'] if para['language'] == 'ja')
        self.assertEqual(ja['text'], '部品の交換手順を参照。')
        ruby = next(span for span in ja['spans'] if span['kind'] == 'ruby')
        self.assertEqual(ruby['base'], '交換')
        self.assertEqual(ruby['annotation'], 'こうかん')
        p4 = next(para for para in self.report['paragraphs']
                  if para['chapter'] == 'OPS/a-chap1.xhtml'
                  and para['node'].endswith('/p[4]'))
        lang = next(span for span in p4['spans'] if span['kind'] == 'lang')
        self.assertEqual((lang['language'], lang['text']), ('en', 'torque wrench'))
        links = {link['href']: link for link in p4['links']}
        self.assertEqual(links['b-chap2.xhtml#s2']['target'], 'OPS/b-chap2.xhtml')
        self.assertEqual(links['b-chap2.xhtml#s2']['fragment'], 's2')
        self.assertFalse(links['b-chap2.xhtml#s2']['external'])
        self.assertEqual(links['#p1']['target'], 'OPS/a-chap1.xhtml')
        p5 = next(para for para in self.report['paragraphs']
                  if para['chapter'] == 'OPS/a-chap1.xhtml'
                  and para['node'].endswith('/p[5]'))
        self.assertTrue(p5['links'][0]['external'])
        self.assertNotIn('target', p5['links'][0])
        p1 = next(para for para in self.report['paragraphs']
                  if para['chapter'] == 'OPS/a-chap1.xhtml'
                  and para['node'].endswith('/p[1]'))
        self.assertIn('p1', p1['anchors'])
        noteref = p1['links'][0]
        self.assertEqual(noteref.get('note'), 'OPS/e-notes.xhtml#n1')

    def test_provenance_triple_and_node_uniqueness(self):
        digest = hashlib.sha256(self.manual).hexdigest()
        seen = set()
        for para in self.report['paragraphs']:
            self.assertEqual(para['book'], digest)
            self.assertEqual(self.report['publication']['digest'], digest)
            self.assertTrue(para['chapter'].startswith('OPS/'))
            self.assertTrue(para['node'].startswith('html[1]/body[1]/'))
            key = (para['chapter'], para['node'])
            self.assertNotIn(key, seen)
            seen.add(key)

    def test_scripts_not_executed_nor_extracted(self):
        self.assertFalse(any('alert' in para['text'] for para in self.report['paragraphs']))
        chap1 = next(entry for entry in self.report['reading_order']
                     if entry['href'] == 'OPS/a-chap1.xhtml')
        self.assertEqual(chap1['scripts_skipped'], 1)

    def test_fixed_layout_declined_not_scrambled(self):
        report = collect_publication(self.fixtures['fixed.epub'])
        self.assertEqual(report['status'], 'declined')
        self.assertIn('固定版式', report['reason'])
        self.assertEqual([item['href'] for item in report['declared_order']],
                         ['OPS/page1.xhtml'])
        self.assertNotIn('paragraphs', report)

    def test_invalid_input_rejected(self):
        with self.assertRaises(ValueError):
            collect_publication(self.fixtures['invalid.epub'])

    def test_determinism(self):
        self.assertEqual(collect_publication(self.manual), self.report)

    def test_cli_collect_and_collect_demo(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'manual.epub'
            path.write_bytes(self.manual)
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(app.main(['collect', str(path)]), 0)
            report = json.loads(output.getvalue())
            self.assertEqual(report['status'], 'partial')
            self.assertEqual(len(report['reading_order']), 5)
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(app.main(['collect-demo']), 0)
            demo = json.loads(output.getvalue())
            self.assertEqual(demo['requests'], 1)
            self.assertEqual(demo['report']['status'], 'partial')
            self.assertTrue(demo['report']['missing'])
            self.assertTrue(demo['report']['notes'])

if __name__ == '__main__':
    unittest.main()
