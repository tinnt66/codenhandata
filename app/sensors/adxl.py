import csv
import threading
import time
from pathlib import Path

from smbus2 import SMBus  # <-- thêm để dùng ADXL I2C

from ..config import (
    ADXL_ADDR,
    ADXL_HEADERS,
    CH_ADXL1,
    CH_ADXL2,
    CH_ADXL3,
    INTERVAL_US,
    MUX_ADDR,
)


# ================= ADXL HELPERS (copy tối giản từ adxl.py) ==================
def tca9548a_select(bus: SMBus, channel: int):
    if not (0 <= channel <= 7):
        raise ValueError("Channel must be 0..7")
    bus.write_byte(MUX_ADDR, 1 << channel)
    time.sleep(0.0005)


def adxl_write_reg(bus: SMBus, reg: int, val: int) -> int:
    try:
        bus.write_byte_data(ADXL_ADDR, reg, val)
        return 0
    except OSError:
        return 1


def adxl_read_multi(bus: SMBus, reg: int, length: int):
    try:
        data = bus.read_i2c_block_data(ADXL_ADDR, reg, length)
        if len(data) != length:
            return 5, []
        return 0, data
    except OSError:
        return 1, []


def adxl_read_z(bus: SMBus):
    err, buf = adxl_read_multi(bus, 0x36, 2)
    if err != 0:
        return err, 0
    z = (buf[1] << 8) | buf[0]
    if z & 0x8000:
        z -= 0x10000
    return 0, z


def adxl_init_on_current_channel(bus: SMBus):
    # BW_RATE ~ 400 Hz
    adxl_write_reg(bus, 0x2C, 0x0C)
    # ±8g, full-res
    adxl_write_reg(bus, 0x31, 0x0A)
    # Measure=1
    adxl_write_reg(bus, 0x2D, 0x08)


# ================= ADXL LOGGER THREAD ==================
class ADXLLogger(threading.Thread):
    """
    Đọc 3 ADXL345 qua TCA9548A và ghi CSV riêng.
    Không liên quan UI.
    """
    def __init__(self, csv_path: Path, realtime_sender=None):
        super().__init__(daemon=True)
        self.csv_path = csv_path
        self._running = True

        self.offsetZ1 = 0
        self.offsetZ2 = 0
        self.offsetZ3 = 0

        self._lock = threading.Lock()
        self._latest = None  # (z1, z2, z3)

        # ===== ADD: realtime sender =====
        self.realtime_sender = realtime_sender

    def stop(self):
        self._running = False

    def get_latest(self):
        with self._lock:
            return self._latest

    def run(self):
        try:
            with SMBus(1) as bus:
                time.sleep(0.2)

                # init 3 sensors
                tca9548a_select(bus, CH_ADXL1)
                adxl_init_on_current_channel(bus)

                tca9548a_select(bus, CH_ADXL2)
                adxl_init_on_current_channel(bus)

                tca9548a_select(bus, CH_ADXL3)
                adxl_init_on_current_channel(bus)

                # read offsets (improve stability: discard warm-up + average many samples)
                def _calc_offset(channel: int, discard: int = 20, samples: int = 200, dt: float = 0.001):
                    """Return (err, offset) for Z-axis on a given mux channel."""
                    try:
                        tca9548a_select(bus, channel)
                        # discard a few samples after switching mux / enabling measure
                        for _ in range(discard):
                            adxl_read_z(bus)
                            time.sleep(dt)
                        vals = []
                        for _ in range(samples):
                            err, z = adxl_read_z(bus)
                            if err == 0:
                                vals.append(z)
                            time.sleep(dt)
                        if not vals:
                            return 1, 0
                        vals.sort()
                        # use median to suppress spikes
                        offset = vals[len(vals)//2]
                        return 0, int(offset)
                    except Exception:
                        return 1, 0

                e1, z1_off = _calc_offset(CH_ADXL1)
                e2, z2_off = _calc_offset(CH_ADXL2)
                e3, z3_off = _calc_offset(CH_ADXL3)

                # nếu lỗi offset thì vẫn set 0 để chạy tiếp
                self.offsetZ1 = z1_off if e1 == 0 else 0
                self.offsetZ2 = z2_off if e2 == 0 else 0
                self.offsetZ3 = z3_off if e3 == 0 else 0

                # open csv
                self.csv_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.csv_path, "w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(ADXL_HEADERS)

                    previous_us = time.time_ns() // 1000
                    total_us = 0

                    # sampling loop
                    while self._running:
                        current_us = time.time_ns() // 1000
                        if current_us - previous_us >= INTERVAL_US:
                            previous_us += INTERVAL_US

                            # Z1
                            tca9548a_select(bus, CH_ADXL1)
                            err1, z1_raw = adxl_read_z(bus)
                            z1 = z1_raw - self.offsetZ1

                            # Z2
                            tca9548a_select(bus, CH_ADXL2)
                            err2, z2_raw = adxl_read_z(bus)
                            z2 = z2_raw - self.offsetZ2

                            # Z3
                            tca9548a_select(bus, CH_ADXL3)
                            err3, z3_raw = adxl_read_z(bus)
                            z3 = z3_raw - self.offsetZ3

                            with self._lock:
                                self._latest = (z1, z2, z3)

                            writer.writerow([z1, z2, z3])

                            # ===== ADD: realtime push per sample (500Hz) =====
                            if self.realtime_sender is not None:
                                try:
                                    self.realtime_sender.push_adxl_sample(z1, z2, z3)
                                except Exception:
                                    pass

                        else:
                            # nhường CPU chút
                            time.sleep(0.0002)

        except Exception:
            # im lặng để không phá UI
            return
