from pathlib import Path

# ================= CONFIG ==================
PORT = "/dev/ttyUSB0"
BAUD = 9600
ID_TEMP_HUM = 1
ID_WIND_SPD = 3
ID_WIND_DIR = 4
READ_INTERVAL_MS = 1000
CSV_AUTO_DIR = Path.cwd()
MAX_SAMPLES = 200
TABLE_HEADERS = ["Time", "Temperature (°C)", "Humidity (%)", "Wind Direction (°)", "Wind Speed (m/s)"]

# ================= ADXL CONFIG (từ adxl.py) ==================
MUX_ADDR = 0x70
ADXL_ADDR = 0x53

CH_ADXL1 = 1
CH_ADXL2 = 2
CH_ADXL3 = 4

INTERVAL_US = 2000  # ~500 Hz

ADXL_HEADERS = ["Z1", "Z2", "Z3"]

# ================= REALTIME SERVER CONFIG (ADD) ==================
SERVER_URL = "http://100.109.17.117:8080"  # <-- IP Windows chạy server
API_KEY = "iotserver"
DEVICE_ID = "raspi-01"

# ADXL gửi batch để vẫn đủ 500Hz dữ liệu nhưng giảm số request
ADXL_BATCH_SIZE = 50          # 50 mẫu/batch -> ~10 request/s
ADXL_FLUSH_INTERVAL_S = 0.15  # flush nếu batch chưa đầy nhưng quá lâu
