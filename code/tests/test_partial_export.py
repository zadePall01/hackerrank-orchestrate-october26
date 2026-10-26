"""Explicit partial export does not claim a complete challenge submission."""
from pathlib import Path
import contextlib
import io
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main as cli


class PartialExportTests(unittest.TestCase):
    def check_export(self, allow_partial: bool) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root/'output.csv'
            diagnostics = dict(requests=2, resolved=1, errors=[dict(case_id='missing', error='No subject link')],
                               warnings=[], coverage=[], dataset_sha256='fixture', elapsed_seconds=0,
                               observations=0)
            rows = [dict(case_id='known', deletion_status='NOT_APPLICABLE', steps_json='[]')]
            argv = ['main.py', '--requests', 'fixture.csv', '--output', str(output),
                    '--diagnostics', str(root/'diagnostics')]
            if allow_partial:
                argv.append('--allow-partial')
            with patch.object(sys, 'argv', argv), patch.object(cli, 'run', return_value=(rows, diagnostics, {})), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(cli.main(), 2)
            self.assertEqual(output.exists(), allow_partial)
            self.assertEqual(output.with_suffix('.csv.partial.md').exists(), allow_partial)
            self.assertIn('missing', (root/'diagnostics/diagnostics.md').read_text())
            if allow_partial:
                self.assertEqual(output.read_text(), 'case_id,deletion_status,steps_json\nknown,NOT_APPLICABLE,[]\n')
                self.assertIn('NOT SUBMISSION-READY', output.with_suffix('.csv.partial.md').read_text())

    def test_default_does_not_export_incomplete_run(self):
        self.check_export(False)

    def test_opt_in_exports_candidates_without_fabricating_missing_rows(self):
        self.check_export(True)
