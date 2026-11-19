import hashlib
import serial
import database

from datetime import datetime, timedelta

from PyQt6.QtCore import QThread, pyqtSignal
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives import serialization


class Monitor(QThread):

    # Signals for UI updates
    connection_status = pyqtSignal(str)
    key_exchange_complete = pyqtSignal(bool)

    def __init__(self, connection_port: str, rmv_after_hrs: int = 48):
        super().__init__()

        self.port = connection_port
        self.hrs = rmv_after_hrs
        self.time_format = "%Y-%m-%d %H:%M:%S"

        # Temporary cryptographic keys
        self.private_key = None
        self.public_key = None
        self.mcu_public_key = None
        self.shared_secret = None

    # STEP 1: Generate temporary X25519 keys

    def generate_temp_keys(self):

        self.private_key = x25519.X25519PrivateKey.generate()

        self.public_key = self.private_key.public_key()

        public_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )

        return public_bytes

    # STEP 2: Send application's public key

    def send_public_key(self, ser, public_bytes):

        message = f"APP_PUBLIC_KEY:{public_bytes.hex()}\n"

        ser.write(message.encode("ascii"))
        ser.flush()

        print("[SafeTrack] Application public key sent.")

    # STEP 3: Receive MCU public key

    def receive_public_key(self, ser):

        while not self.isInterruptionRequested():

            raw = ser.readline()

            if not raw:
                raise TimeoutError("MCU public key response timed out.")

            message = raw.decode("ascii", errors="replace").strip()

            if message.startswith("MCU_PUBLIC_KEY:"):

                hex_key = message.split(":", 1)[1]

                try:
                    public_bytes = bytes.fromhex(hex_key)
                except ValueError as exc:
                    raise ValueError("MCU sent invalid hexadecimal key.") from exc

                if len(public_bytes) != 32:
                    raise ValueError(
                        f"Invalid MCU public key length: {len(public_bytes)}"
                    )

                self.mcu_public_key = (
                    x25519.X25519PublicKey.from_public_bytes(public_bytes)
                )

                print("[SafeTrack] MCU public key received.")

                return

            # Ignore existing plaintext GPS messages during handshake
            print(f"[SafeTrack] Ignoring during handshake: {message}")

        raise InterruptedError("Key exchange interrupted.")

    # STEP 4: Generate shared secret

    def generate_shared_secret(self):

        if self.private_key is None or self.mcu_public_key is None:
            raise RuntimeError("Key exchange is incomplete.")

        self.shared_secret = self.private_key.exchange(
            self.mcu_public_key
        )

        # Development-only fingerprint
        fingerprint = hashlib.sha256(
            self.shared_secret
        ).hexdigest()[:16]

        print("[SafeTrack] Shared secret generated.")
        print(f"[SafeTrack] Secret fingerprint: {fingerprint}")

    # STEP 5: Perform complete key exchange

    def perform_key_exchange(self, ser):

        self.connection_status.emit("Generating temporary keys...")

        public_bytes = self.generate_temp_keys()

        self.connection_status.emit("Sending application public key...")

        self.send_public_key(ser, public_bytes)

        self.connection_status.emit("Waiting for MCU public key...")

        self.receive_public_key(ser)

        self.connection_status.emit("Generating shared secret...")

        self.generate_shared_secret()

        self.connection_status.emit("X25519 key exchange complete.")

        self.key_exchange_complete.emit(True)

    # STEP 6: Existing GPS monitoring

    def monitor_gps(self, ser):

        while not self.isInterruptionRequested():

            try:
                raw = ser.readline()

                if not raw:
                    continue

                message = raw.decode("utf-8").strip()

                packets = message.split()

                if len(packets) != 3:
                    continue

                packet = [
                    int(packets[0]),
                    float(packets[2]),
                    float(packets[1])
                ]

                database.add_to_db((
                    datetime.now().strftime(self.time_format),
                    packet[0],
                    packet[1],
                    packet[2],
                    "SOS"
                ))

                cutoff = (
                    datetime.now() - timedelta(hours=self.hrs)
                ).strftime(self.time_format)

                database.delete_before_time(cutoff)

                database.delete_before_time(
                    cutoff,
                    "notifications"
                )

                database.print_db()

            except (ValueError, UnicodeDecodeError):
                continue

    # MAIN THREAD

    def run(self):

        try:
            self.connection_status.emit("Connecting to MCU...")

            with serial.Serial(
                self.port,
                baudrate=9600,
                timeout=1,
                write_timeout=2
            ) as ser:

                # Some boards reset when serial port opens.
                # Firmware should be ready to receive APP_PUBLIC_KEY.

                self.perform_key_exchange(ser)

                # Existing plaintext GPS monitoring
                # This is temporary until AES-GCM is implemented.
                self.monitor_gps(ser)

        except (
            serial.SerialException,
            TimeoutError,
            ValueError,
            RuntimeError,
            InterruptedError,
            OSError
        ) as exc:

            print(f"[SafeTrack] Connection error: {exc}")

            self.connection_status.emit(
                f"Connection error: {exc}"
            )

            self.key_exchange_complete.emit(False)

        finally:
            self.shared_secret = None
            self.private_key = None
            self.public_key = None
            self.mcu_public_key = None

            self.connection_status.emit("Disconnected.")