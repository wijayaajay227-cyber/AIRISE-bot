import unittest

from real import _compute_margin_usdt


class WalletHelperTests(unittest.TestCase):
    def test_compute_margin_usdt_uses_available_balance(self) -> None:
        self.assertEqual(_compute_margin_usdt(1000.0, 200.0, 10.0), 80.0)

    def test_compute_margin_usdt_never_goes_negative(self) -> None:
        self.assertEqual(_compute_margin_usdt(100.0, 200.0, 25.0), 0.0)


if __name__ == "__main__":
    unittest.main()
