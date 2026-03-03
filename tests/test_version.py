import unittest

import version


class TestVersion(unittest.TestCase):
    def test_get_version_matches_constant(self):
        self.assertEqual(version.get_version(), version.__version__)
