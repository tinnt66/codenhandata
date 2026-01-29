import sys
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent
if str(_BASE_DIR) not in sys.path:
    sys.path.insert(0, str(_BASE_DIR))

from app.config import (  # noqa: E402
    ADXL_ADDR,
    ADXL_BATCH_SIZE,
    ADXL_FLUSH_INTERVAL_S,
    ADXL_HEADERS,
    API_KEY,
    BAUD,
    CH_ADXL1,
    CH_ADXL2,
    CH_ADXL3,
    CSV_AUTO_DIR,
    DEVICE_ID,
    ID_TEMP_HUM,
    ID_WIND_DIR,
    ID_WIND_SPD,
    INTERVAL_US,
    MAX_SAMPLES,
    MUX_ADDR,
    PORT,
    READ_INTERVAL_MS,
    SERVER_URL,
    TABLE_HEADERS,
)
from app.main import main as _main  # noqa: E402
from app.realtime_sender import RealtimeSender  # noqa: E402
from app.sensors.adxl import (  # noqa: E402
    ADXLLogger,
    adxl_init_on_current_channel,
    adxl_read_multi,
    adxl_read_z,
    adxl_write_reg,
    tca9548a_select,
)
from app.sensors.rs485 import deg_to_cardinal, make_instrument  # noqa: E402
from app.ui.dashboard import Dashboard  # noqa: E402
from app.ui.plots import SimplePlot  # noqa: E402


def main():
    return _main()


__all__ = [
    "ADXL_ADDR",
    "ADXL_BATCH_SIZE",
    "ADXL_FLUSH_INTERVAL_S",
    "ADXL_HEADERS",
    "API_KEY",
    "BAUD",
    "CH_ADXL1",
    "CH_ADXL2",
    "CH_ADXL3",
    "CSV_AUTO_DIR",
    "DEVICE_ID",
    "ID_TEMP_HUM",
    "ID_WIND_DIR",
    "ID_WIND_SPD",
    "INTERVAL_US",
    "MAX_SAMPLES",
    "MUX_ADDR",
    "PORT",
    "READ_INTERVAL_MS",
    "SERVER_URL",
    "TABLE_HEADERS",
    "RealtimeSender",
    "ADXLLogger",
    "adxl_init_on_current_channel",
    "adxl_read_multi",
    "adxl_read_z",
    "adxl_write_reg",
    "tca9548a_select",
    "deg_to_cardinal",
    "make_instrument",
    "SimplePlot",
    "Dashboard",
    "main",
]


if __name__ == "__main__":
    main()
