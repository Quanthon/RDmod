import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from convert_webp_to_png import convert, prompt_convert


class ConversionTests(unittest.TestCase):
    def test_prompt_accepts_quoted_path_with_spaces(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "中文 卡图.webp"
            Image.new("RGB", (12, 9), "red").save(source, "WEBP")
            with patch("builtins.input", return_value=f'"{source}"'), patch("builtins.print"):
                self.assertEqual(prompt_convert(), 0)
            with Image.open(source.with_suffix(".png")) as image:
                self.assertEqual(image.format, "PNG")
                self.assertEqual(image.size, (12, 9))

    def test_preserves_pixels_alpha_and_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            source.mkdir()
            output = Path(directory) / "output"
            original = source / "卡图.WEBP"
            Image.new("RGBA", (17, 13), (31, 63, 95, 127)).save(
                original, format="WEBP", lossless=True)
            before = original.read_bytes()
            self.assertEqual(convert(source, output)["converted"], 1)
            with Image.open(original) as expected, Image.open(output / "卡图.png") as actual:
                self.assertEqual(actual.size, expected.size)
                self.assertEqual(actual.convert("RGBA").tobytes(),
                                 expected.convert("RGBA").tobytes())
            saved = (output / "卡图.png").read_bytes()
            self.assertEqual(convert(source, output)["skipped"], 1)
            self.assertEqual((output / "卡图.png").read_bytes(), saved)
            self.assertEqual(original.read_bytes(), before)

    def test_invalid_file_is_reported_without_partial_png(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            (source / "bad.webp").write_bytes(b"invalid")
            output = source / "output"
            result = convert(source, output)
            self.assertEqual(len(result["errors"]), 1)
            self.assertFalse((output / "bad.png").exists())


if __name__ == "__main__":
    unittest.main()
