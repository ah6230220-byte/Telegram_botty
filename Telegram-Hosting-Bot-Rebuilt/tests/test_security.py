import tempfile, unittest, zipfile
from pathlib import Path
from utils.security import inspect_python, extract_zip

class SecurityTests(unittest.TestCase):
    def test_detects_dynamic_execution(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "main.py").write_text("eval('1 + 1')\n", encoding="utf-8")
            self.assertTrue(any("dynamic code execution" in x for x in inspect_python(d)))

    def test_detects_syntax_error(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "main.py").write_text("def broken(:\n pass", encoding="utf-8")
            self.assertTrue(any("syntax error" in x for x in inspect_python(d)))

    def test_extracts_safe_zip(self):
        with tempfile.TemporaryDirectory() as d:
            archive, output = Path(d, "ok.zip"), Path(d, "out")
            output.mkdir()
            with zipfile.ZipFile(archive, "w") as z: z.writestr("main.py", "print('ok')")
            extract_zip(archive, output)
            self.assertEqual((output / "main.py").read_text(), "print('ok')")

    def test_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as d:
            archive, output = Path(d, "bad.zip"), Path(d, "out")
            output.mkdir()
            with zipfile.ZipFile(archive, "w") as z: z.writestr("../evil.py", "print('bad')")
            with self.assertRaises(ValueError): extract_zip(archive, output)

if __name__ == "__main__": unittest.main()
