import importlib
import unittest


class AppEntrypointTests(unittest.TestCase):
    def test_app_module_exposes_streamlit_entrypoints(self) -> None:
        app_module = importlib.import_module("app")
        self.assertTrue(hasattr(app_module, "main"))
        self.assertTrue(hasattr(app_module, "get_ohlcv"))
        self.assertTrue(hasattr(app_module, "get_exchange"))


if __name__ == "__main__":
    unittest.main()
