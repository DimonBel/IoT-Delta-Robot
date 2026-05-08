import re
import time
import serial

POST_COMMAND_SLEEP_SECONDS = 0.4


class CommandFailed(RuntimeError):
    pass


class RobotController:
    def __init__(self, port: str = "COM6", baudrate: int = 115200, timeout: float = 10.0):
        self._ser = serial.Serial(port=port, baudrate=baudrate, timeout=timeout)
        self._acceleration: float | None = None
        self._speed: float | None = None
        print("Robot controller initialised.")

    def close(self) -> None:
        if self._ser.is_open:
            self._ser.close()

    def __enter__(self) -> "RobotController":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _read_response(self) -> str:
        return self._ser.readline().decode("utf-8", errors="replace").strip()

    def _send_command(self, command: str, success_predicate=None) -> str:
        if not command.endswith("\n"):
            command += "\n"
        print(f"Sending: {command.rstrip()}")
        self._ser.write(command.encode("utf-8"))
        self._ser.flush()

        response = self._read_response()
        if not response:
            raise CommandFailed("No Response")
        if success_predicate is not None and not success_predicate(response):
            raise CommandFailed(f"Unexpected Response: {response}")
        time.sleep(POST_COMMAND_SLEEP_SECONDS)
        return response

    def send_ok_command(self, command: str) -> None:
        self._send_command(command, success_predicate=lambda r: r == "Ok")

    def send_axes_home(self, X: bool = False, Y: bool = False, Z: bool = False,
                       U: bool = False, V: bool = False, W: bool = False) -> None:
        if not any([X, Y, Z, U, V, W]):
            raise CommandFailed("Error: no axes specified to home")

        axes = []
        if X:
            axes.append("X0")
        if Y:
            axes.append("Y0")
        if Z:
            axes.append("Z0")
        if U:
            axes.append("U0")
        if V:
            axes.append("V0")
        if W:
            axes.append("W0")

        self.send_ok_command(f"G28 {' '.join(axes)}")

    def set_motion(self, speed: float | None = None, acceleration: float | None = None) -> None:
        if speed is not None:
            self._speed = speed
        if acceleration is not None:
            self._acceleration = acceleration

    def move_to(self, X: float | None = None, Y: float | None = None, Z: float | None = None,
                W: float | None = None, U: float | None = None, V: float | None = None) -> None:
        if not any(value is not None for value in [X, Y, Z, W, U, V]):
            raise CommandFailed("Error: no axes specified to move")
        parts = ["G01"]
        if self._acceleration is not None:
            parts.append(f"A{self._acceleration}")
        if self._speed is not None:
            parts.append(f"F{self._speed}")
        if X is not None:
            parts.append(f"X{X}")
        if Y is not None:
            parts.append(f"Y{Y}")
        if Z is not None:
            parts.append(f"Z{Z}")
        if W is not None:
            parts.append(f"W{W}")
        if U is not None:
            parts.append(f"U{U}")
        if V is not None:
            parts.append(f"V{V}")
        self.send_ok_command(" ".join(parts))

    def get_position(self) -> list[float]:
        response = self._send_command("Position", success_predicate=self._is_position_response)
        return [float(value) for value in response.split(",")]

    def is_delta(self) -> bool:
        self._send_command("IsDelta", success_predicate=lambda r: r == "YesDelta")
        return True

    @staticmethod
    def _is_position_response(response: str) -> bool:
        pattern = r"^-?\d+(?:\.\d+)?(?:,-?\d+(?:\.\d+)?){5}$"
        return re.match(pattern, response) is not None