"""Interactive USB controller or hardware-free CAN frame preview."""
import argparse
from dataclasses import dataclass
import math
import time


@dataclass
class State:
    turn: int = 0
    reverse: bool = False
    brake: bool = False
    speed: int = 0

    def apply(self, command):
        cmd = " ".join(command.upper().split())
        if cmd == "RESET":
            self.turn, self.reverse, self.brake, self.speed = 0, False, False, 0
        elif cmd in ("LEFT", "RIGHT", "HAZARD", "OFF"):
            self.turn = {"OFF": 0, "LEFT": 1, "RIGHT": 2, "HAZARD": 3}[cmd]
        elif cmd == "STOP":
            self.speed = 0
        elif cmd in ("REVERSE ON", "REVERSE OFF", "BRAKE ON", "BRAKE OFF"):
            setattr(self, cmd.split()[0].lower(), cmd.endswith(" ON"))
        elif cmd.startswith("SPEED "):
            value = float(cmd[6:])
            if not math.isfinite(value) or not 0 <= value <= 200:
                raise ValueError("speed must be 0..200 km/h")
            self.speed = math.floor(value * 10 + 0.5)
        elif cmd != "STATUS":
            raise ValueError("unknown command; type HELP")
        return cmd

    def frame(self, counter):
        flags = self.turn | (int(self.reverse) << 2) | (int(self.brake) << 3)
        return bytes([1, flags, self.speed & 255, self.speed >> 8, counter & 255, 0, 0, 0])


HELP = "LEFT | RIGHT | HAZARD | OFF | STOP | SPEED 25.5 | REVERSE ON/OFF | BRAKE ON/OFF | RESET | STATUS | DEMO | QUIT"
DEMO = ["RESET", "SPEED 25", "LEFT", "RIGHT", "HAZARD", "BRAKE ON", "STOP",
        "OFF", "BRAKE OFF", "REVERSE ON", "SPEED 5", "STOP", "RESET"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="USB serial port, e.g. COM5")
    parser.add_argument("--dry-run", action="store_true", help="preview only; no physical CAN output")
    parser.add_argument("--demo", action="store_true", help="run scenario then exit")
    args = parser.parse_args()
    if bool(args.port) == args.dry_run:
        parser.error("choose exactly one of --port COMx or --dry-run")
    connection = None
    if args.port:
        import serial
        connection = serial.Serial(args.port, 115200, timeout=0.05, write_timeout=1)
        time.sleep(2)  # ESP32 may reset when USB serial opens.
    state, counter = State(), 0

    def send(command):
        nonlocal counter
        normalized = state.apply(command)
        if connection:
            connection.write((normalized + "\n").encode("ascii"))
        else:
            print(f"PREVIEW 321# {state.frame(counter).hex(' ').upper()} stopped={state.speed == 0}")
            counter = (counter + 1) & 255

    def drain():
        if connection:
            for _ in range(100):
                if not connection.in_waiting:
                    break
                print(connection.readline().decode(errors="replace").rstrip())

    try:
        print(HELP)
        if args.dry_run:
            print("Preview emits one frame per command; ESP32 firmware emits every 100 ms.")
        if args.demo:
            for command in DEMO:
                print(">", command)
                send(command)
                if connection:
                    until = time.monotonic() + 1
                    while time.monotonic() < until:
                        drain()
                        time.sleep(0.02)
        else:
            while True:
                drain()
                command = input("kan> ").strip()
                if command.upper() in ("QUIT", "EXIT"):
                    break
                if command.upper() == "HELP":
                    print(HELP)
                    continue
                try:
                    for item in DEMO if command.upper() == "DEMO" else [command]:
                        send(item)
                        if connection:
                            time.sleep(0.15)
                            drain()
                except ValueError as exc:
                    print("ERR", exc)
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        if connection:
            # Stop stale simulated motion when controller exits normally.
            connection.write(b"RESET\n")
            connection.close()


if __name__ == "__main__":
    main()
