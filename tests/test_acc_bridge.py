import ctypes
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from acc_bridge import Physics, Graphics, Mapper, Freshness, serial_frame


def snapshot(speed=25.5, brake=0.0, gear=2, status=2, left=0, right=0):
    # Binary fixtures use documented offsets, independently of ctypes declarations.
    physics = bytearray(32)
    struct.pack_into("f", physics, 8, brake)
    struct.pack_into("i", physics, 16, gear)
    struct.pack_into("f", physics, 28, speed)
    graphics = bytearray(1500)
    struct.pack_into("i", graphics, 4, status)
    # Clock is before the indicators; a nonzero time catches the old missing-field bug.
    struct.pack_into("fii", graphics, 1488, 32400.0, left, right)
    return Physics.from_buffer_copy(physics), Graphics.from_buffer_copy(graphics)


class AccTests(unittest.TestCase):
    def test_layout(self):
        self.assertEqual(ctypes.sizeof(Physics), 32)
        self.assertEqual(Graphics.clock.offset, 1488)
        self.assertEqual(Graphics.left.offset, 1492)
        self.assertEqual(Graphics.right.offset, 1496)
        self.assertEqual(ctypes.sizeof(Graphics), 1500)

    def test_reverse_hazard_and_atomic_command(self):
        state = Mapper().convert(*snapshot(speed=5.5, brake=0.5, gear=0, left=1, right=1))
        self.assertEqual(serial_frame(state), b"FRAME 55 7\n")
        self.assertEqual(state.frame(0), bytes.fromhex("01 07 37 00 00 00 00 00"))

    def test_brake_is_not_forwarded(self):
        mapper = Mapper()
        for brake, expected in [(0.01, False), (0.1, True), (0.03, True), (0.01, False)]:
            self.assertFalse(mapper.convert(*snapshot(brake=brake)).brake)

    def test_speed_threshold_cap_and_neutral(self):
        state = Mapper().convert(*snapshot(speed=0.4, gear=1, brake=0))
        self.assertEqual(state.speed, 0)
        self.assertFalse(state.reverse)
        self.assertFalse(state.brake)
        self.assertEqual(Mapper().convert(*snapshot(speed=280)).speed, 2000)

    def test_invalid_and_non_live_rejected(self):
        for values in [dict(status=0), dict(status=1), dict(status=3), dict(speed=float("nan")),
                       dict(left=99), dict(gear=-1)]:
            with self.assertRaises(ValueError):
                Mapper().convert(*snapshot(**values))

    def test_frozen_packets_do_not_become_live(self):
        p, g = snapshot()
        fresh = Freshness()
        self.assertFalse(fresh.check(p, g, 10))
        self.assertFalse(fresh.check(p, g, 10.1))
        p.packet = g.packet = 1
        self.assertTrue(fresh.check(p, g, 10.2))
        self.assertTrue(fresh.check(p, g, 10.3))
        p.packet = 2  # Physics alone cannot keep a frozen graphics map alive.
        self.assertFalse(fresh.check(p, g, 11))


if __name__ == "__main__":
    unittest.main()
