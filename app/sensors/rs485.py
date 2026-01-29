import minimalmodbus

from ..config import BAUD, PORT


# ================= HELPER ==================
def make_instrument(addr: int):
    inst = minimalmodbus.Instrument(PORT, addr)
    inst.serial.baudrate = BAUD
    inst.serial.bytesize = 8
    inst.serial.parity = minimalmodbus.serial.PARITY_NONE
    inst.serial.stopbits = 1
    inst.serial.timeout = 1.0
    inst.mode = minimalmodbus.MODE_RTU
    inst.clear_buffers_before_each_transaction = True
    inst.close_port_after_each_call = True
    return inst


def deg_to_cardinal(deg: float) -> str:
    try:
        d = float(deg) % 360.0
    except Exception:
        return "-"
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    idx = int((d + 22.5) // 45) % 8
    return dirs[idx]
