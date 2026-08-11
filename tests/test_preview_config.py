import unittest
from pathlib import Path


PREVIEW_CONFIG = (
    Path(__file__).resolve().parents[1] / "config" / "monitor-preview-path.yml"
)


class PreviewCommandTests(unittest.TestCase):
    def test_preview_ffmpeg_runs_with_nice_10_and_keeps_encoding_parameters(self):
        config = PREVIEW_CONFIG.read_text(encoding="utf-8")

        self.assertIn('"~^__preview__/(.+)$":', config)
        self.assertIn("nice -n 10 ffmpeg -nostdin -loglevel warning", config)
        for parameter in (
            "-vf scale=192:108,fps=10",
            "-b:v 80k",
            "-maxrate 100k",
            "-bufsize 100k",
        ):
            self.assertIn(parameter, config)


if __name__ == "__main__":
    unittest.main()
