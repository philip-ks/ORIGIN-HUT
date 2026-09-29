from __future__ import annotations

import sys
import unittest
from pathlib import Path

DATA_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = DATA_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from identity.organizations import normalize_domain


class OrganizationIdentityUnitTest(unittest.TestCase):

    def test_domain_normalization(self) -> None:
        self.assertEqual(
            normalize_domain(
                "https://www.Example.COM/path"
            ),
            "example.com",
        )
        self.assertEqual(
            normalize_domain("example.com"),
            "example.com",
        )
        self.assertIsNone(
            normalize_domain(None)
        )


if __name__ == "__main__":
    unittest.main()
