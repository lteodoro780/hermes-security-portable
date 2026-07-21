from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from hermes import hermes_paths  # noqa: E402


class PortablePathTests(unittest.TestCase):
    def test_source_mode_uses_project_root_for_data_and_assets(self) -> None:
        writable, bundled = hermes_paths.resolve_portable_roots(frozen=False)

        self.assertEqual(writable, PROJECT_ROOT)
        self.assertEqual(bundled, PROJECT_ROOT)

    def test_frozen_mode_writes_beside_executable_and_reads_bundle(self) -> None:
        writable, bundled = hermes_paths.resolve_portable_roots(
            frozen=True,
            executable="C:/HERMES/HERMES.exe",
            bundle_dir="C:/Temp/_MEI123",
        )

        self.assertEqual(writable.name, "HERMES")
        self.assertEqual(bundled.name, "_MEI123")


if __name__ == "__main__":
    unittest.main()
