import unittest

from interpolation import bilinear_interpolate, calculate, linear_interpolate, normalize_state


class InterpolationTests(unittest.TestCase):
    def test_one_dimensional_interpolation_accepts_decimal_comma(self):
        response = calculate(
            {
                "mode": "1d",
                "values": {"x0": "0", "y0": "0", "x1": "10", "y1": "100", "x": "2,5"},
            }
        )
        self.assertTrue(response["ok"], response.get("error"))
        self.assertEqual(response["raw_value"], 25.0)
        self.assertEqual(linear_interpolate(10, 100, 0, 0, 2.5), 25.0)

    def test_two_dimensional_interpolation_is_bilinear(self):
        response = calculate(
            {
                "mode": "2d",
                "values": {
                    "x0": "0",
                    "x1": "10",
                    "y0": "0",
                    "y1": "10",
                    "z00": "0",
                    "z10": "10",
                    "z01": "20",
                    "z11": "30",
                    "x": "5",
                    "y": "5",
                },
            }
        )
        self.assertTrue(response["ok"], response.get("error"))
        self.assertEqual(response["raw_value"], 15.0)
        self.assertEqual(bilinear_interpolate(0, 10, 0, 10, 0, 10, 20, 30, 5, 5), 15.0)

    def test_zero_length_reference_axes_are_rejected(self):
        one_d = calculate(
            {"mode": "1d", "values": {"x0": "1", "y0": "0", "x1": "1", "y1": "2", "x": "1"}}
        )
        self.assertFalse(one_d["ok"])
        self.assertIn("x₀", one_d["error"])

        two_d = calculate(
            {
                "mode": "2d",
                "values": {
                    "x0": "0", "x1": "1", "y0": "2", "y1": "2",
                    "z00": "0", "z10": "1", "z01": "2", "z11": "3",
                    "x": "0.5", "y": "2",
                },
            }
        )
        self.assertFalse(two_d["ok"])
        self.assertIn("y₀", two_d["error"])

    def test_persisted_state_is_bounded_and_backward_compatible(self):
        state = normalize_state(
            {
                "mode": "2d",
                "one_d": {"x": "1" * 100},
                "two_d": {"z11": "3,5"},
            }
        )
        self.assertEqual(state["mode"], "2d")
        self.assertEqual(len(state["one_d"]["x"]), 80)
        self.assertEqual(state["two_d"]["z11"], "3,5")
        self.assertEqual(state["two_d"]["x"], "")


if __name__ == "__main__":
    unittest.main()
