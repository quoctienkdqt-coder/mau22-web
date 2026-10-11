import os
import sys
import json
import base64
import uuid
import hashlib

# ==========================================
# 1. HẰNG SỐ & BẢN QUYỀN
# ==========================================
CURRENT_VERSION = "1.0.9" 
UPDATE_INFO_URL = "https://raw.githubusercontent.com/quoctienkdqt-coder/Mau22-Updates/refs/heads/main/version.json" 
SECRET_SALT = "MAU22_PRO_2026_BY_HAILONG" 

# ==========================================
# 2. XỬ LÝ ĐƯỜNG DẪN AN TOÀN CHO FILE .EXE
# ==========================================
# Đảm bảo file config luôn nằm cùng thư mục với file chạy (.py hoặc .exe)
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
DB_FILE = os.path.join(BASE_DIR, "dulieu_tau.db")

# ==========================================
# 3. BẢNG MÀU THƯƠNG HIỆU UI (MODERN DESIGN SYSTEM)
# ==========================================
COLOR_NAVY = "#0F172A"          # Slate 900 - Sang trọng, đẳng cấp
COLOR_NAVY_LIGHT = "#1E293B"    # Slate 800 - Dùng cho hover sidebar
COLOR_PRIMARY = "#2563EB"       # Royal Blue - Điểm nhấn chính hiện đại
COLOR_PRIMARY_HOVER = "#1D4ED8" # Hover cho nút primary
COLOR_PRIMARY_LIGHT = "#EFF6FF" # Nền pastel xanh cho badge / card
COLOR_SUCCESS = "#059669"       # Emerald Green - Trạng thái thành công
COLOR_SUCCESS_LIGHT = "#ECFDF5" # Nền pastel xanh lá
COLOR_WARNING = "#D97706"       # Warm Amber - Cảnh báo / đang xử lý
COLOR_WARNING_LIGHT = "#FFFBEB" # Nền pastel cam nhạt
COLOR_DANGER = "#DC2626"        # Rose Red - Thất bại / Xóa
COLOR_DANGER_LIGHT = "#FEF2F2"  # Nền pastel đỏ nhạt
COLOR_BG = "#F8FAFC"            # Slate 50 - Nền app dịu mắt, chống mỏi mắt
COLOR_CARD_BG = "#FFFFFF"       # Trắng tinh khiết cho Cards và Panels
COLOR_BORDER = "#E2E8F0"        # Slate 200 - Viền mảnh tinh tế chuẩn Apple/Stripe
COLOR_TEXT = "#0F172A"          # Slate 900 - Chữ chính tương phản cao
COLOR_TEXT_MUTED = "#64748B"    # Slate 500 - Chữ phụ trang nhã

# ==========================================
# 4. CÁC HÀM TIỆN ÍCH HỆ THỐNG
# ==========================================
def get_hidden_api_key():
    encoded_key = "QVEuQWI4Uk42SmJrZjhCQjd0ejN3V3Z0ZGpIZ1lac1pxSHQyOTBVV3VnN3NIUmZZbVRpdWc=" 
    return base64.b64decode(encoded_key).decode('utf-8')

def get_gemini_api_key():
    """
    Lấy Gemini API Key theo thứ tự ưu tiên đa tầng (Multi-tier Secrets):
    1. Streamlit Secrets (st.secrets["GEMINI_API_KEY"] hoặc st.secrets["gemini_api_key"])
    2. Biến môi trường hệ thống (os.environ["GEMINI_API_KEY"] hoặc GOOGLE_API_KEY)
    3. Tệp cấu hình cục bộ config.json ("api_key")
    4. Fallback key mặc định đã mã hóa (get_hidden_api_key())
    """
    # Tầng 1: Streamlit secrets (nếu chạy trên Streamlit Cloud hoặc local Streamlit)
    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            for k in ["GEMINI_API_KEY", "gemini_api_key", "GOOGLE_API_KEY", "google_api_key"]:
                if k in st.secrets and str(st.secrets[k]).strip():
                    return str(st.secrets[k]).strip()
    except Exception:
        pass

    # Tầng 2: Biến môi trường hệ thống
    for env_var in ["GEMINI_API_KEY", "gemini_api_key", "GOOGLE_API_KEY", "google_api_key"]:
        val = os.environ.get(env_var, "").strip()
        if val:
            return val

    # Tầng 3: Tệp config.json cục bộ
    try:
        cfg = load_config()
        cfg_key = str(cfg.get("api_key", "")).strip()
        if cfg_key:
            return cfg_key
    except Exception:
        pass

    # Tầng 4: Default fallback
    return get_hidden_api_key()

import platform
import subprocess
try:
    import winreg
except ImportError:
    winreg = None

def get_hardware_id():
    """Lấy mã máy duy nhất (HWID) - Đa nền tảng an toàn cho cả Windows và Linux"""
    hwid_string = ""
    
    try:
        # Kiểm tra winreg cả ở module level lẫn sys.modules (hỗ trợ kiểm thử giả lập Linux)
        active_winreg = sys.modules.get("winreg") if "winreg" in sys.modules else winreg
        if platform.system() == "Windows" and active_winreg is not None:
            # CÁCH 1 (Ưu tiên Windows): Đọc MachineGuid từ Registry.
            try:
                key = active_winreg.OpenKey(
                    active_winreg.HKEY_LOCAL_MACHINE, 
                    r"SOFTWARE\Microsoft\Cryptography", 
                    0, 
                    active_winreg.KEY_READ | active_winreg.KEY_WOW64_64KEY
                )
                value, _ = active_winreg.QueryValueEx(key, "MachineGuid")
                active_winreg.CloseKey(key)
                if value:
                    hwid_string = str(value).strip()
            except Exception:
                pass
                
            # CÁCH 2 (Dự phòng Windows): Serial Number ổ C
            if not hwid_string:
                try:
                    output = subprocess.check_output("vol c:", shell=True, stderr=subprocess.DEVNULL).decode()
                    hwid_string = output.strip().split()[-1]
                except Exception:
                    pass
        elif platform.system() == "Linux":
            # Trên Linux / Streamlit Cloud: Đọc /etc/machine-id hoặc /var/lib/dbus/machine-id
            for mid_path in ["/etc/machine-id", "/var/lib/dbus/machine-id"]:
                if os.path.exists(mid_path):
                    try:
                        with open(mid_path, "r") as f:
                            hwid_string = f.read().strip()
                        if hwid_string:
                            break
                    except Exception:
                        pass
    except Exception:
        pass

    # CHỐT CHẶN CUỐI CÙNG: Hostname hoặc fallback định danh
    if not hwid_string:
        hwid_string = platform.node() or "STREAMLIT_HOST_2026"

    # Băm MD5 và cắt đúng 10 ký tự 
    return hashlib.md5(hwid_string.encode('utf-8')).hexdigest().upper()[:10]

def load_config():
    """Đọc config an toàn, chống lỗi khi file bị hỏng"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f: 
                return json.load(f)
        except json.JSONDecodeError:
            # File tồn tại nhưng bị lỗi định dạng JSON
            return {}
        except Exception: 
            return {}
    return {}

def save_config(api_key="", license_key="", profile_data=None):
    """Ghi config một cách an toàn"""
    cfg = load_config()
    if api_key: cfg["api_key"] = api_key
    if license_key: cfg["license_key"] = license_key
    if profile_data is not None: cfg["profile"] = profile_data
    
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f: 
            json.dump(cfg, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Lỗi khi lưu config: {e}")

import re
import unicodedata

def normalize_text_key(s):
    """Chuẩn hóa chuỗi tiếng Việt để so khớp cột header Excel"""
    if not s: return ""
    s = str(s).replace('đ', 'd').replace('Đ', 'D')
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return s.lower().strip()

def load_company_list(custom_path=None):
    """
    Tải danh sách các doanh nghiệp từ file Excel Danh_sach_cong_ty.xlsx.
    Trả về tuple: (dict_danh_sach_cong_ty, duong_dan_file_thuc_te)
    """
    candidates = []
    if custom_path and str(custom_path).strip():
        candidates.append(str(custom_path).strip())
    candidates.append(os.path.join(BASE_DIR, "Danh_sach_cong_ty.xlsx"))
    candidates.append(r"C:\Users\Admin\Desktop\Cấu trúc phần mềm\Danh_sach_cong_ty.xlsx")
    if getattr(sys, 'frozen', False):
        candidates.append(os.path.join(os.path.dirname(sys.executable), "Danh_sach_cong_ty.xlsx"))

    excel_path = None
    for p in candidates:
        if os.path.exists(p):
            excel_path = os.path.abspath(p)
            break

    if not excel_path:
        return {}, ""

    try:
        import openpyxl
        wb = openpyxl.load_workbook(excel_path, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows or len(rows) < 2:
            return {}, excel_path

        header = [normalize_text_key(c) for c in rows[0]]
        col_map = {}
        for i, h in enumerate(header):
            if 'ten' in h:
                col_map['ten_co_so'] = i
            elif 'dia chi' in h:
                col_map['dia_chi'] = i
            elif 'dai dien' in h or 'nguoi' in h:
                col_map['nguoi_dai_dien'] = i
            elif 'dien thoai' in h or 'sdt' in h or 'phone' in h:
                col_map['sdt'] = i

        companies = {}
        for r in rows[1:]:
            if not any(r): continue
            ten = str(r[col_map.get('ten_co_so', 0)] or '').strip()
            if not ten: continue
            dc = str(r[col_map.get('dia_chi', 1)] or '').strip()
            ndd = str(r[col_map.get('nguoi_dai_dien', 2)] or '').strip()
            sdt_raw = str(r[col_map.get('sdt', 3)] or '').strip()
            sdt = re.sub(r'[ \t]{2,}', ' - ', sdt_raw)

            companies[ten] = {
                "ten_co_so": ten,
                "dia_chi": dc,
                "nguoi_dai_dien": ndd,
                "sdt": sdt
            }
        return companies, excel_path
    except Exception as e:
        print(f"Lỗi khi đọc file Danh_sach_cong_ty.xlsx: {e}")
        return {}, excel_path