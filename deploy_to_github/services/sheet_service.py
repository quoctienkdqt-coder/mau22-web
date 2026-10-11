import requests
import threading
import os

class SheetService:
    WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbxpWqRVr3h2TlLkAtPlb1N8SbPyOYOSeq5XjCc1mIPhP9FPLkTxzxMRMblVsFW5t4p7/exec"

    @staticmethod
    def log_api_call(hwid, ma_ho_so, nghiep_vu, in_tokens, out_tokens, duration, so_trang):
        """Bắn log thống kê AI lên Google Sheets"""
        try: user_name = os.getlogin()
        except: user_name = "Unknown User"
        
        payload = {
            "machine_id": hwid,
            "user_name": user_name,
            "ma_ho_so": ma_ho_so,
            "nghiep_vu": nghiep_vu,
            "input_tokens": in_tokens,
            "output_tokens": out_tokens,
            "duration": duration,       
            "so_trang": so_trang
        }
        threading.Thread(target=lambda: requests.post(SheetService.WEBHOOK_URL, json=payload, timeout=10), daemon=True).start()
        
    @staticmethod
    def update_accuracy(ma_ho_so, accuracy):
        """Bắn chỉ số độ chính xác % lên Google Sheets"""
        payload = {"action": "update_accuracy", "ma_ho_so": ma_ho_so, "accuracy": accuracy}
        threading.Thread(target=lambda: requests.post(SheetService.WEBHOOK_URL, json=payload, timeout=10), daemon=True).start()