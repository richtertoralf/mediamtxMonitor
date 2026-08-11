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
            "-vf fps=10,scale=384:216",
            "-b:v 200k",
            "-maxrate 250k",
            "-bufsize 250k",
        ):
            self.assertIn(parameter, config)


if __name__ == "__main__":
    unittest.main()
