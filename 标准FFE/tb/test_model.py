"""验证 Python 定点运算及其与 RTL 默认配置的一致性。"""

import re
import unittest
from pathlib import Path

from ffe import FFE, arithmetic_shift, demo_samples, saturate


class FFEModelTest(unittest.TestCase):
    # 同时核对参数/系数，避免软件与硬件各自改变默认值。
    def test_rtl_default_parameters_match_reference(self) -> None:
        rtl_path = Path(__file__).resolve().parents[1] / "rtl" / "ffe.sv"
        rtl = rtl_path.read_text(encoding="utf-8")
        model = FFE()
        parameters = (("DATA_W", model.data_width),
                      ("COEFF_W", model.coeff_width),
                      ("FRAC", model.frac_bits))
        for name, expected in parameters:
            match = re.search(rf"parameter int {name} = (\d+)", rtl)
            self.assertIsNotNone(match, f"missing RTL parameter {name}")
            self.assertEqual(int(match.group(1)), expected, name)
        for index, expected in enumerate(model.coeffs):
            pattern = rf"parameter signed \[COEFF_W-1:0\] C{index} = (-?\d+)"
            match = re.search(pattern, rtl)
            self.assertIsNotNone(match, f"missing RTL coefficient C{index}")
            self.assertEqual(int(match.group(1)), expected, f"C{index}")
        self.assertIn("localparam int ACC_W = PROD_W + $clog2(TAPS);", rtl)

    def test_impulse_response(self) -> None:
        model = FFE()
        impulse_and_zeros = [64, 0, 0, 0, 0, 0]
        output = model.process(impulse_and_zeros)
        self.assertEqual(output, [-4, -12, 64, -16, 4, 0])

    # 用独立卷积公式交叉检查状态模型，避免只做自我对照。
    def test_against_independent_convolution(self) -> None:
        coeffs = (-4, -12, 64, -16, 4)
        data = demo_samples()
        actual = FFE().process(data)
        expected = []
        for n in range(len(data)):
            acc = sum(coeffs[k] * data[n-k] for k in range(5) if n >= k)
            scaled = acc // 64
            expected.append(max(-128, min(127, scaled)))
        self.assertEqual(actual, expected)
        self.assertIn(-128, actual)
        self.assertIn(127, actual)

    def test_invalid_cycle_matches_rtl_hold_behavior(self) -> None:
        model = FFE()
        accepted = model.step(64)
        held_history = model.history.copy()
        bubble = model.step(127, valid=False)
        self.assertFalse(bubble["valid"])
        self.assertEqual(bubble["y"], accepted["y"])
        self.assertEqual(model.history, held_history)
        self.assertEqual(bubble["acc"], 127 * -4 + 64 * -12)
        next_sample = model.step(0)
        self.assertEqual(next_sample["taps"], [0, 64, 0, 0, 0])

    def test_reset_and_bounds(self) -> None:
        model = FFE()
        model.step(127)
        model.reset()
        self.assertEqual(model.step(0)["y"], 0)
        with self.assertRaises(ValueError):
            model.step(128)
        with self.assertRaises(ValueError):
            FFE(coeffs=(128, 0, 0, 0, 0))
        self.assertEqual(arithmetic_shift(-65, 6), -2)
        self.assertEqual(saturate(200, 8), 127)
        self.assertEqual(saturate(-200, 8), -128)


if __name__ == "__main__":
    unittest.main()
