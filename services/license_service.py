import hashlib
from datetime import datetime
import urllib.request
import json
import os
import sys
import subprocess
from tkinter import messagebox
from config import CURRENT_VERSION, SECRET_SALT, UPDATE_INFO_URL

class LicenseService:
    @staticmethod
    def verify_license(hwid, license_key):
        """Xác thực bản quyền chuyên sâu, trả về: (is_valid, message, plan_type, limit)"""
        if not license_key: 
            return False, "Chưa có bản quyền.", "", 0
            
        try:
            parts = license_key.split("-")
            if len(parts) != 4: 
                return False, "Định dạng Key không hợp lệ!", "", 0
                
            plan_type, value, exp_date_str, sig = parts
            raw = f"{hwid.strip().upper()}-{plan_type}-{value}-{exp_date_str}-{SECRET_SALT}"
            expected_sig = hashlib.md5(raw.encode()).hexdigest().upper()[:12]
            
            if sig != expected_sig: 
                return False, "Key không hợp lệ cho máy tính này (Sai Mã Máy)!", "", 0
                
            exp_date = datetime.strptime(exp_date_str, "%Y%m%d")
            today = datetime.now()
            
            if today > exp_date: 
                return False, f"Bản quyền đã hết hạn vào ngày {exp_date.strftime('%d/%m/%Y')}!", "", 0
                
            days_left = (exp_date - today).days
            msg = f"Gói: {'Đếm Lượt' if plan_type == 'CRE' else 'Không Giới Hạn'}. Còn: {days_left} ngày."
            limit = 999999 if value == "UNLIMITED" else int(value)
            
            return True, msg, plan_type, limit
            
        except Exception:
            return False, "Lỗi phân tích License Key!", "", 0

    @staticmethod
    def generate_license_key(hwid: str, plan_type: str = "CRE", value: str = "30", days_valid: int = 365) -> str:
        """
        Tạo mã License Key bản quyền chuẩn theo đúng thuật toán mã hóa Desktop:
        hwid: Mã máy định danh (HWID 10 ký tự)
        plan_type: 'CRE' (đếm lượt) hoặc 'UNL' (không giới hạn)
        value: Số lượt ('30', '120') hoặc 'UNLIMITED'
        exp_date_str: YYYYMMDD (Hạn dùng)
        sig: MD5(hwid-plan_type-value-exp_date_str-SECRET_SALT)[:12]
        """
        from datetime import timedelta
        exp_date = (datetime.now() + timedelta(days=days_valid)).strftime("%Y%m%d")
        hwid_clean = hwid.strip().upper() if hwid and str(hwid).strip() else "STREAMLIT01"
        raw = f"{hwid_clean}-{plan_type}-{value}-{exp_date}-{SECRET_SALT}"
        sig = hashlib.md5(raw.encode()).hexdigest().upper()[:12]
        return f"{plan_type}-{value}-{exp_date}-{sig}"

# Alias cấp module phục vụ import linh hoạt
generate_license_key = LicenseService.generate_license_key
verify_license = LicenseService.verify_license
try:
    from config import get_hardware_id
except Exception:
    def get_hardware_id():
        return "STREAMLIT01"

class UpdaterService:
    @staticmethod
    def check_for_updates():
        """Kiểm tra bản cập nhật từ GitHub ngầm (Không làm treo UI)"""
        try:
            req = urllib.request.Request(UPDATE_INFO_URL, headers={'User-Agent': 'Mozilla/5.0'})
            response = urllib.request.urlopen(req, timeout=5)
            data = json.loads(response.read().decode('utf-8'))
            
            latest_version = data.get("version")
            download_url = data.get("download_url")
            notes = data.get("release_notes")
            
            latest_parts = [int(x) for x in latest_version.split('.')]
            current_parts = [int(x) for x in CURRENT_VERSION.split('.')]

            if latest_parts > current_parts:
                msg = f"Đã có phiên bản mới: {latest_version}!\n\nNội dung cập nhật:\n{notes}\n\nBạn có muốn cập nhật ngay không?"
                if messagebox.askyesno("Cập nhật phần mềm", msg):
                    UpdaterService._perform_update(download_url)
        except Exception as e:
            print(f"Lỗi check update: {e}") 
            # Im lặng bỏ qua nếu rớt mạng

    @staticmethod
    def _perform_update(download_url):
        """Tiến hành tải file và tạo script cập nhật"""
        import tkinter as tk
        try:
            update_win = tk.Toplevel()
            update_win.title("Đang cập nhật...")
            update_win.geometry("340x120")
            tk.Label(update_win, text="Đang tải bản cập nhật mới, vui lòng chờ...", pady=25, font=("Segoe UI", 10)).pack()
            update_win.update()
            
            # Đảm bảo lưu đúng vào thư mục của file exe đang chạy
            target_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.abspath(os.path.dirname(__file__))
            new_exe_name = "Mau_22_Pro_Update.exe"
            new_exe_path = os.path.join(target_dir, new_exe_name)
            current_exe_name = os.path.basename(sys.executable)
            
            # Nếu file Update cũ đang tồn tại hoặc bị kẹt, dọn dẹp trước
            if os.path.exists(new_exe_path):
                try:
                    subprocess.run(["taskkill", "/F", "/IM", new_exe_name], capture_output=True)
                    os.remove(new_exe_path)
                except Exception:
                    pass

            # Tải file trực tiếp kèm User-Agent tránh bị chặn
            req = urllib.request.Request(download_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=60) as resp, open(new_exe_path, 'wb') as out_file:
                while True:
                    chunk = resp.read(64 * 1024)
                    if not chunk: break
                    out_file.write(chunk)
            
            bat_path = os.path.join(target_dir, "update.bat")
            bat_script = f"""@echo off
cd /d "{target_dir}"
timeout /t 2 /nobreak > NUL
taskkill /F /IM "{current_exe_name}" > NUL 2>&1
del "{current_exe_name}"
ren "{new_exe_name}" "{current_exe_name}"
start "" "{current_exe_name}"
del "%~f0"
"""
            with open(bat_path, "w", encoding="utf-8") as f: 
                f.write(bat_script)
                
            subprocess.Popen(["cmd.exe", "/c", bat_path], cwd=target_dir)
            sys.exit()
        except Exception as e:
            messagebox.showerror("Lỗi cập nhật", f"Không thể tải bản cập nhật: {e}")