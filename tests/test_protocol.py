import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from simulator import State


class ProtocolTests(unittest.TestCase):
    def test_combined_reverse_hazard_brake(self):
        s = State()
        for command in ["HAZARD", "REVERSE ON", "BRAKE ON", "SPEED 5.5"]:
            s.apply(command)
        self.assertEqual(s.frame(256), bytes.fromhex("01 0F 37 00 00 00 00 00"))

    def test_stop_is_independent_of_brake_and_turn(self):
        s = State()
        for command in ["LEFT", "SPEED 25.5", "STOP"]:
            s.apply(command)
        self.assertEqual(s.frame(1), bytes.fromhex("01 01 00 00 01 00 00 00"))
        self.assertFalse(s.brake)

    def test_invalid_commands_preserve_state(self):
        s = State(speed=123)
        for command in ["SPEED -1", "SPEED 201", "SPEED nan", "SPEED inf", "SPEED 2x", "BOGUS"]:
            with self.assertRaises(ValueError):
                s.apply(command)
            self.assertEqual(s.speed, 123)

    def test_endianness_and_reset(self):
        s = State()
        s.apply("SPEED 200")
        self.assertEqual(s.frame(255)[2:5], bytes.fromhex("D0 07 FF"))
        s.apply("RESET")
        self.assertEqual(s, State())


if __name__ == "__main__":
    unittest.main()
