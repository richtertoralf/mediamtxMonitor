import subprocess
import sys
import textwrap
import unittest


class ProductModuleImportTests(unittest.TestCase):
    def test_imports_do_not_start_runtime_services(self):
        script = textwrap.dedent(
            """
            import builtins
            import sys
            import types
            from pathlib import Path
            from unittest import mock

            real_open = builtins.open
            real_path_open = Path.open

            def guarded_open(path, *args, **kwargs):
                if str(path).startswith("/opt/mediamtx-monitoring-backend"):
                    raise AssertionError(f"production path read during import: {path}")
                return real_open(path, *args, **kwargs)

            def guarded_path_open(path, *args, **kwargs):
                if str(path).startswith("/opt/mediamtx-monitoring-backend"):
                    raise AssertionError(f"production path read during import: {path}")
                return real_path_open(path, *args, **kwargs)

            redis_module = types.ModuleType("redis")
            redis_module.Redis = mock.Mock(
                side_effect=AssertionError("Redis used during import")
            )

            class FakeFastAPI:
                def __init__(self, *args, **kwargs):
                    pass

                def mount(self, *args, **kwargs):
                    pass

                def get(self, *args, **kwargs):
                    return lambda function: function

            fastapi_module = types.ModuleType("fastapi")
            fastapi_module.FastAPI = FakeFastAPI
            responses_module = types.ModuleType("fastapi.responses")
            responses_module.JSONResponse = lambda *args, **kwargs: None
            responses_module.FileResponse = lambda *args, **kwargs: None
            staticfiles_module = types.ModuleType("fastapi.staticfiles")
            staticfiles_module.StaticFiles = lambda *args, **kwargs: object()

            with (
                mock.patch("builtins.open", side_effect=guarded_open),
                mock.patch("pathlib.Path.open", side_effect=guarded_path_open),
                mock.patch("requests.get", side_effect=AssertionError("HTTP used during import")),
                mock.patch.dict(
                    sys.modules,
                    {
                        "redis": redis_module,
                        "fastapi": fastapi_module,
                        "fastapi.responses": responses_module,
                        "fastapi.staticfiles": staticfiles_module,
                    },
                ),
            ):
                import bin.mediamtx_collector as collector
                import bin.mediamtx_api as api
                import bin.mediamtx_systeminfo as systeminfo
                import bin.monitoring_config
                import bin.redis_keys
                import bin.redis_store

            assert collector.r is None
            assert api.r is None
            assert systeminfo.r is None
            assert collector.snapshot_store is None
            assert api.snapshot_store is None
            assert systeminfo.snapshot_store is None
            """
        )

        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=".",
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
