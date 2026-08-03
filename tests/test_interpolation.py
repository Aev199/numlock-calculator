import unittest

from interpolation import calculate, linear_interpolate, normalize_state


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

    def test_two_dimensional_interpolation_is_not_available(self):
        response = calculate(
            {
                "mode": "2d",
                "values": {"x0": "0", "y0": "0", "x1": "10", "y1": "100", "x": "5"},
            }
        )
        self.assertFalse(response["ok"])
        self.assertIn("только", response["error"])

    def test_zero_length_reference_axes_are_rejected(self):
        one_d = calculate(
            {"mode": "1d", "values": {"x0": "1", "y0": "0", "x1": "1", "y1": "2", "x": "1"}}
        )
        self.assertFalse(one_d["ok"])
        self.assertIn("x₀", one_d["error"])

    def test_persisted_state_is_bounded_and_backward_compatible(self):
        state = normalize_state(
            {
                "mode": "2d",
                "one_d": {"x": "1" * 100},
                "two_d": {"z11": "3,5"},
            }
        )
        self.assertEqual(len(state["one_d"]["x"]), 80)
        self.assertNotIn("mode", state)
        self.assertNotIn("two_d", state)


if __name__ == "__main__":
    unittest.main()
