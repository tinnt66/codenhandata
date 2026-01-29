import threading
import time
from datetime import datetime

import requests


# ================= REALTIME SENDER (ADD) ==================
class RealtimeSender(threading.Thread):
    """
    - RS485: gửi mỗi 1s (mỗi lần read_all gọi push_rs485)
    - ADXL: nhận từng mẫu 500Hz (push_adxl_sample) rồi gửi theo batch (ADXL_BATCH_SIZE)
    Endpoint: POST {SERVER_URL}/ingest
    Header: X-API-Key: API_KEY
    """
    def __init__(self, server_url: str, api_key: str, device_id: str,
                 timeout: float = 2.0,
                 adxl_batch_size: int = 50,
                 adxl_flush_interval_s: float = 0.15):
        super().__init__(daemon=True)
        self.server_url = server_url.rstrip("/")
        self.api_key = api_key
        self.device_id = device_id
        self.timeout = timeout

        self.adxl_batch_size = int(adxl_batch_size)
        self.adxl_flush_interval_s = float(adxl_flush_interval_s)

        self._running = True
        self._lock = threading.Lock()

        self._rs485_buf = []   # list[dict]
        self._adxl_buf = []    # list[[z1, z2, z3]]
        self._adxl_last_flush = time.time()

        self._sess = requests.Session()
        self._headers = {"X-API-Key": self.api_key}

    def stop(self):
        self._running = False

    def push_rs485(self, sample: dict):
        # ít dữ liệu -> buffer list là đủ
        with self._lock:
            self._rs485_buf.append(sample)

    def push_adxl_sample(self, z1: int, z2: int, z3: int):
        # 500Hz -> chỉ append, không network tại thread đọc sensor
        with self._lock:
            self._adxl_buf.append([int(z1), int(z2), int(z3)])

    def _post(self, body: dict):
        self._sess.post(
            f"{self.server_url}/ingest",
            json=body,
            headers=self._headers,
            timeout=self.timeout
        )

    def run(self):
        while self._running:
            # ---- 1) gửi RS485 nếu có ----
            rs_item = None
            with self._lock:
                if self._rs485_buf:
                    rs_item = self._rs485_buf.pop(0)

            if rs_item is not None:
                body = {
                    "device_id": self.device_id,
                    "ts": datetime.utcnow().isoformat() + "Z",
                    "type": "rs485",
                    "sample": rs_item
                }
                try:
                    self._post(body)
                except Exception:
                    pass

            # ---- 2) flush ADXL batch ----
            now = time.time()
            chunk = None
            with self._lock:
                need_flush = (len(self._adxl_buf) >= self.adxl_batch_size) or \
                             ((now - self._adxl_last_flush) >= self.adxl_flush_interval_s and len(self._adxl_buf) > 0)
                if need_flush:
                    take = min(self.adxl_batch_size, len(self._adxl_buf))
                    chunk = self._adxl_buf[:take]
                    del self._adxl_buf[:take]
                    self._adxl_last_flush = now

            if chunk is not None:
                body = {
                    "device_id": self.device_id,
                    "ts": datetime.utcnow().isoformat() + "Z",
                    "type": "adxl_batch",
                    "fs_hz": 500,
                    "chunk_start_us": int(chunk[0][0]),
                    "samples": chunk
                }
                try:
                    self._post(body)
                except Exception:
                    pass

            time.sleep(0.001)
