from unittest import TestCase
from numbas_lti.diff import make_diff, apply_diff

class DiffTest(TestCase):

    def generic_test_diff_restores(self, a, b):
        diff = make_diff(a, b)
        c = apply_diff(diff, a)
        self.assertEqual(b, c)

    def test_delete(self):
        self.generic_test_diff_restores(
            'hi there',
            'hi'
        )

    def test_replace(self):
        self.generic_test_diff_restores(
            'hi there!',
            'hi bob!'
        )

    def test_insert(self):
        self.generic_test_diff_restores(
            'what for',
            'what for?'
        )

    def test_from_blank(self):
        self.generic_test_diff_restores(
            '',
            'something'
        )

    def test_to_blank(self):
        self.generic_test_diff_restores(
            'something',
            ''
        )

    def test_newline(self):
        self.generic_test_diff_restores(
            'one line\ntwo lines\n',
            '\none line two lines'
        )

    def test_backslash(self):
        self.generic_test_diff_restores(
            'a\\b\\c',
            '\\a\\B\\c\\d'
        )
