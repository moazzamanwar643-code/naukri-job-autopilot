"""Offline smoke tests: never require API credentials or internet."""
import math
import time
import unittest

from crypto_scanner import scanner as s


class ScannerTest(unittest.TestCase):
    def test_flat_ema_and_rsi(self):
        prices = [10.0] * 150
        self.assertAlmostEqual(s.ema(prices, 25)[-1], 10.0)
        self.assertAlmostEqual(s.rsi(prices, 6)[-1], 50.0)

    def test_rising_rsi(self):
        prices = [10.0 + i * 0.1 for i in range(150)]
        self.assertAlmostEqual(s.rsi(prices, 6)[-1], 100.0)

    def test_stop_size_respects_allocation_and_risk(self):
        p = s.trade_plan(10.0, 9.5, True)
        self.assertIsNotNone(p)
        self.assertLessEqual(p["allocation"], s.ACCOUNT * 0.5 + 1e-8)
        self.assertLessEqual(p["maxloss"], s.ACCOUNT * 0.01 + 1e-8)
        self.assertAlmostEqual((p["tp1"] - 10.0) / (10.0 - p["stop"]), 1.5)

    def test_invalid_stop(self):
        self.assertIsNone(s.trade_plan(10.0, 10.1, True))
        self.assertIsNone(s.trade_plan(10.0, 0.5, True))

    def test_incomplete_candle_is_excluded(self):
        now = int(time.time() * 1000)
        rows = []
        for i in range(145):
            opening = now - (146 - i) * 60_000
            price = 10 + i * 0.002 + 0.05 * math.sin(i / 4)
            rows.append([opening, "10", str(price + 0.03), str(price - 0.03),
                         str(price), "1000", opening + 59_999])
        output = s.indicators(rows)
        self.assertEqual(len(output["c"]), 145)
        rows.append([now, "10", "9999", "0.01", "9999", "1000", now + 59_999])
        filtered = s.indicators(rows)
        self.assertEqual(len(filtered["c"]), 145)
        self.assertEqual(filtered["c"][-1], output["c"][-1])
        self.assertIsNotNone(filtered["k"][-1])


if __name__ == "__main__":
    unittest.main()
