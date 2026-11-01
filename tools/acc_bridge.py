"""Read existing ACC Windows shared memory and drive Kan_sim over USB."""
import argparse
import ctypes as c
import math
import os
import time

from simulator import State

I, F, W = c.c_int32, c.c_float, c.c_uint16  # ACC UTF-16, independent of host wchar size


class Physics(c.LittleEndianStructure):
    _pack_ = 4
    _fields_ = [("packet", I), ("gas", F), ("brake", F), ("fuel", F),
                ("gear", I), ("rpm", I), ("steer", F), ("speed", F)]


class Graphics(c.LittleEndianStructure):
    _pack_ = 4
    _fields_ = (
        [("packet", I), ("status", I), ("session", I)]
        + [(n, W * 15) for n in ("currentTime", "lastTime", "bestTime", "split")]
        + [(n, I) for n in ("completedLaps", "position", "iCurrentTime", "iLastTime", "iBestTime")]
        + [("sessionTimeLeft", F), ("distance", F)]
        + [(n, I) for n in ("isInPit", "currentSector", "lastSectorTime", "numberOfLaps")]
        + [("tyreCompound", W * 33), ("replayMultiplier", F), ("normalizedPosition", F),
           ("activeCars", I), ("coordinates", F * 180), ("carIDs", I * 60),
           ("playerCarID", I), ("penaltyTime", F)]
        + [(n, I) for n in ("flag", "penalty", "idealLine", "isInPitLane")]
        + [("surfaceGrip", F), ("mandatoryPitDone", I), ("windSpeed", F), ("windDirection", F)]
        + [(n, I) for n in ("setupMenu", "mainDisplay", "secondaryDisplay", "tc", "tcut", "engineMap", "abs")]
        + [("fuelXLap", F)]
        + [(n, I) for n in ("rainLights", "flashingLights", "lightsStage")]
        + [("exhaustTemp", F)]
        + [(n, I) for n in ("wipers", "driverStintTotal", "driverStint", "rainTyres", "sessionIndex")]
        + [("usedFuel", F), ("deltaLapTime", W * 15), ("iDeltaLapTime", I),
           ("estimatedLapTime", W * 15), ("iEstimatedLapTime", I)]
        + [(n, I) for n in ("deltaPositive", "iSplit", "validLap")]
        + [("fuelEstimatedLaps", F), ("trackStatus", W * 33), ("missingPits", I),
           ("clock", F), ("left", I), ("right", I)]
    )


class ExistingMap:
    """OpenFileMapping, rather than mmap(tagname), never creates an empty fake ACC map."""
    def __init__(self, name, structure):
        self.structure = structure
        self.api = c.WinDLL("kernel32", use_last_error=True)
        self.api.OpenFileMappingW.argtypes = [c.c_uint32, c.c_int, c.c_wchar_p]
        self.api.OpenFileMappingW.restype = c.c_void_p
        self.api.MapViewOfFile.argtypes = [c.c_void_p, c.c_uint32, c.c_uint32, c.c_uint32, c.c_size_t]
        self.api.MapViewOfFile.restype = c.c_void_p
        self.api.UnmapViewOfFile.argtypes = [c.c_void_p]
        self.api.CloseHandle.argtypes = [c.c_void_p]
        self.handle = self.api.OpenFileMappingW(4, 0, "Local\\" + name)
        if not self.handle:
            raise OSError(c.get_last_error(), f"ACC map unavailable: {name}")
        self.address = self.api.MapViewOfFile(self.handle, 4, 0, 0, c.sizeof(structure))
        if not self.address:
            self.api.CloseHandle(self.handle)
            raise OSError(c.get_last_error(), f"Cannot map {name}")

    def read(self):
        for _ in range(5):
            before = c.string_at(self.address, c.sizeof(self.structure))
            after = c.string_at(self.address, c.sizeof(self.structure))
            if before == after:
                return self.structure.from_buffer_copy(before)
        raise ValueError("ACC snapshot changed during read")

    def close(self):
        self.api.UnmapViewOfFile(self.address)
        self.api.CloseHandle(self.handle)


class Mapper:
    def __init__(self, stop_speed=0.5):
        self.stop_speed = stop_speed

    def convert(self, p, g):
        if g.status != 2:
            raise ValueError("ACC not LIVE (menu, pause or replay)")
        if not math.isfinite(p.speed):
            raise ValueError("invalid ACC telemetry")
        if not 0 <= p.gear <= 20 or g.left not in (0, 1) or g.right not in (0, 1):
            raise ValueError(f"unsupported ACC shared memory values/layout: brake={p.brake!r} "
                             f"gear={p.gear} left={g.left} right={g.right}")
        speed = abs(p.speed)
        speed = 0 if speed < self.stop_speed else min(speed, 200)
        turn = 3 if g.left and g.right else (1 if g.left else 2 if g.right else 0)
        return State(turn, p.gear == 0, False, math.floor(speed * 10 + 0.5))


class Freshness:
    def __init__(self):
        self.previous = None
        self.updated = 0
        self.seen_update = False

    def check(self, p, g, now):
        packets = (p.packet, g.packet)
        if self.previous is None:
            self.previous = packets
            self.updated = now
            return False  # Observe a real update before accepting shared memory.
        if p.packet != self.previous[0] and g.packet != self.previous[1]:
            self.previous = packets
            self.updated = now
            self.seen_update = True
            return True
        return self.seen_update and now - self.updated < 0.75


def serial_frame(state):
    flags = state.frame(0)[1]
    return f"FRAME {state.speed} {flags}\n".encode("ascii")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--port", help="ESP32 sender USB COM port")
    group.add_argument("--dry-run", action="store_true", help="read ACC and print only")
    parser.add_argument("--stop-speed", type=float, default=0.5)
    parser.add_argument("--duration", type=float, default=0, help="seconds; 0 runs until Ctrl+C")
    args = parser.parse_args()
    if not (0 <= args.stop_speed <= 5 and
            math.isfinite(args.duration) and args.duration >= 0):
        parser.error("require stop-speed 0..5, duration >= 0")
    if os.name != "nt":
        parser.error("ACC shared memory requires Windows")
    mapper = Mapper(args.stop_speed)
    connection, maps = None, []
    freshness = Freshness()
    started = time.monotonic()
    previous_message = None
    last_log = 0
    try:
        if args.port:
            import serial
            connection = serial.Serial(args.port, 115200, timeout=0, write_timeout=1)
            time.sleep(2)
            connection.write(b"PAUSE\n")
        print("ACC bridge: 10 Hz; Ctrl+C exits. CAN protocol is private bench data, not Hyundai.")
        while not args.duration or time.monotonic() - started < args.duration:
            now = time.monotonic()
            try:
                if not maps:
                    maps.append(ExistingMap("acpmf_physics", Physics))
                    maps.append(ExistingMap("acpmf_graphics", Graphics))
                    freshness = Freshness()
                p, g = [m.read() for m in maps]
                if not freshness.check(p, g, now):
                    raise ValueError("waiting for fresh ACC packets")
                state = mapper.convert(p, g)
                message = f"LIVE speed={state.speed / 10:.1f} gas={p.gas:.2f} reverse={int(state.reverse)} turn={state.turn}"
                if abs(p.speed) > 200:
                    message += " [speed capped at protocol limit 200 km/h]"
                if connection:
                    connection.write(serial_frame(state))
            except (OSError, ValueError) as exc:
                if isinstance(exc, OSError) or now - freshness.updated >= 0.75:
                    for mapping in maps:
                        mapping.close()
                    maps = []
                message = f"UNKNOWN / CAN paused: {exc}"
                if connection:
                    connection.write(b"PAUSE\n")
            if message != previous_message and now - last_log >= 0.5:
                print(message)
                previous_message, last_log = message, now
            if connection and connection.in_waiting:
                # Drain diagnostics continuously so USB output cannot stall the firmware.
                output = connection.read(connection.in_waiting).decode(errors="replace")
                for line in output.splitlines():
                    if line.startswith(("ERR", "BUS", "STREAM")):
                        print("ESP32:", line)
            time.sleep(max(0, 0.1 - (time.monotonic() - now)))
    except KeyboardInterrupt:
        pass
    finally:
        for mapping in maps:
            mapping.close()
        if connection:
            try:
                connection.write(b"PAUSE\n")
                connection.flush()
            finally:
                connection.close()


if __name__ == "__main__":
    main()
