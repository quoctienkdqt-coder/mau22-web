import pandas as pd
import numpy as np
import os
import re
import sys
import threading
from vessel_utils import clean_vessel_name, clean_imo_number, check_gear_match, normalize_country_flag

class RFMOCheckerOffline:
    _instance = None
    _lock = threading.Lock()
    _cache = {}

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(RFMOCheckerOffline, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, *args, base_dir=None, reload_cache=False, **kwargs):
        # 1. Linh hoạt trích xuất đường dẫn cơ sở từ keyword argument hoặc positional argument
        target_dir = base_dir or kwargs.get('data_dir')
        if not target_dir and args:
            if isinstance(args[0], str):
                target_dir = args[0]
            elif isinstance(args[0], bool) and 'reload_cache' not in kwargs:
                reload_cache = args[0]

        if 'reload_cache' in kwargs:
            reload_cache = bool(kwargs['reload_cache'])

        # 2. Xử lý trường hợp Singleton đã khởi tạo: cập nhật data_dir nếu được truyền rõ ràng
        if getattr(self, '_initialized', False) and not reload_cache:
            if target_dir:
                new_data_dir = os.path.abspath(target_dir) + os.sep
                if getattr(self, 'data_dir', None) != new_data_dir:
                    self.data_dir = new_data_dir
            return

        with self._lock:
            if getattr(self, '_initialized', False) and not reload_cache:
                if target_dir:
                    new_data_dir = os.path.abspath(target_dir) + os.sep
                    if getattr(self, 'data_dir', None) != new_data_dir:
                        self.data_dir = new_data_dir
                return

            # 3. Tự động nhận diện thư mục chứa file CSDL (Ưu tiên: target_dir -> frozen -> __file__)
            if target_dir:
                base_path = os.path.abspath(target_dir)
            elif getattr(sys, 'frozen', False):
                base_path = os.path.dirname(sys.executable)
            else:
                base_path = os.path.abspath(os.path.dirname(__file__))
                
            self.data_dir = base_path + os.sep
            
            # Khởi tạo các biến nội bộ (Lazy Loading - nạp theo nhu cầu hoặc nạp nền)
            self._db_iccat = None
            self._db_wcpfc = None
            self._db_iattc = None
            self._db_iotc = None
            self._db_iuu = None
            self._online_engine = None
            
            self._initialized = True

    @property
    def online_engine(self):
        """Khởi tạo trễ (Lazy init) công cụ tra cứu trực tuyến 4 tổ chức RFMO."""
        if self._online_engine is None:
            try:
                from rfmo_online_engine import RFMOOnlineEngine
                self._online_engine = RFMOOnlineEngine(timeout=12)
            except Exception as e:
                print(f"[RFMO] Không thể nạp RFMOOnlineEngine: {e}")
                self._online_engine = None
        return self._online_engine

    @property
    def db_iccat(self):
        if self._db_iccat is None:
            self._db_iccat = self._get_cached_db("iccat_vessels.csv")
        return self._db_iccat

    @property
    def db_wcpfc(self):
        if self._db_wcpfc is None:
            self._db_wcpfc = self._get_cached_db("wcpfc_vessels.csv")
        return self._db_wcpfc

    @property
    def db_iattc(self):
        if self._db_iattc is None:
            self._db_iattc = self._get_cached_db("iattc_vessels.xlsx")
        return self._db_iattc

    @property
    def db_iotc(self):
        if self._db_iotc is None:
            self._db_iotc = self._get_cached_db("iotc_vessels.xlsx")
        return self._db_iotc

    @property
    def db_iuu(self):
        if self._db_iuu is None:
            self._db_iuu = self._get_cached_db("IUUList.xls")
        return self._db_iuu

    def _get_cached_db(self, filename, reload_cache=False):
        with self._lock:
            if not reload_cache and filename in self._cache:
                return self._cache[filename]
        print(f"Đang nạp file {filename} vào bộ đệm RFMO...")
        df = self._load_db(filename)
        with self._lock:
            self._cache[filename] = df
            if filename == "iccat_vessels.csv": self._db_iccat = df
            elif filename == "wcpfc_vessels.csv": self._db_wcpfc = df
            elif filename == "iattc_vessels.xlsx": self._db_iattc = df
            elif filename == "iotc_vessels.xlsx": self._db_iotc = df
            elif filename == "IUUList.xls": self._db_iuu = df
        return df

    @classmethod
    def preload_async(cls, progress_callback=None, completion_callback=None):
        """
        Nạp ngầm CSDL từng file trong background thread, giữa mỗi file có micro-sleep
        để nhả GIL và CPU cho Tkinter GUI mượt mà 100%, không bị đơ giật.
        """
        import time
        def _worker():
            checker = cls()
            targets = [
                ("iccat_vessels.csv", "ICCAT"),
                ("wcpfc_vessels.csv", "WCPFC"),
                ("IUUList.xls", "IUU Global"),
                ("iattc_vessels.xlsx", "IATTC"),
                ("iotc_vessels.xlsx", "IOTC")
            ]
            total = len(targets)
            for idx, (filename, label) in enumerate(targets, 1):
                try:
                    time.sleep(0.08) # Nhường GIL cho Tkinter vẽ mượt
                    checker._get_cached_db(filename)
                    if progress_callback:
                        progress_callback(idx, total, label)
                except Exception as e:
                    print(f"Lỗi preload {filename}: {e}")
            if completion_callback:
                completion_callback()

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        return t

    @classmethod
    def reload_all(cls):
        """Buộc nạp lại toàn bộ CSDL tàu từ đĩa (ví dụ sau khi tải cập nhật mới)"""
        with cls._lock:
            cls._cache.clear()
            if cls._instance:
                cls._instance._db_iccat = None
                cls._instance._db_wcpfc = None
                cls._instance._db_iattc = None
                cls._instance._db_iotc = None
                cls._instance._db_iuu = None
                cls._instance._initialized = False
                cls._instance.__init__(reload_cache=True)

    def _load_db(self, filename):
        filepath = os.path.join(self.data_dir, filename)
        
        if not os.path.exists(filepath):
            print(f"Cảnh báo: Không tìm thấy file {filepath}")
            return pd.DataFrame()
            
        try:
            # Tự động nhận diện định dạng file (CSV, Excel) và Sheet
            if filename.lower().endswith('.xlsx') or filename.lower().endswith('.xls'):
                with pd.ExcelFile(filepath) as xls:
                    sheet_to_load = 0
                    if 'RegionalVesselRegister' in xls.sheet_names:
                        sheet_to_load = 'RegionalVesselRegister'
                    elif 'Results' in xls.sheet_names:
                        sheet_to_load = 'Results'
                    elif 'IUUList' in xls.sheet_names:
                        sheet_to_load = 'IUUList'
                    df = pd.read_excel(xls, sheet_name=sheet_to_load, dtype=str)
            else:
                df = pd.read_csv(filepath, dtype=str)
                
            # Xử lý đặc thù cho WCPFC: Ngư cụ ưu tiên 'Type of fishing method or methods', nếu trống lấy 'Type of vessel'
            if filename.lower().startswith("wcpfc"):
                m_col = None
                v_col = None
                for col in df.columns:
                    cu = str(col).upper().strip()
                    if cu == 'TYPE OF FISHING METHOD OR METHODS': m_col = col
                    elif cu == 'TYPE OF VESSEL': v_col = col
                if m_col and v_col:
                    m_series = df[m_col].fillna('').astype(str).str.strip()
                    v_series = df[v_col].fillna('').astype(str).str.strip()
                    df['Gear'] = m_series.where(m_series != '', v_series)

            # Bộ lọc chuẩn hóa cột thông minh
            col_mapping = {}
            is_wcpfc = filename.lower().startswith("wcpfc")
            for col in df.columns:
                col_upper = str(col).upper().strip()
                
                if col_upper in ['VESSELNAME', 'NAME OF FISHING VESSEL', 'NAME', 'VESSEL']:
                    col_mapping[col] = 'Name'
                elif col_upper in ['INTREGNO', 'IMO OR LR NUMBER', 'IMO', 'IMO NUMBER']:
                    col_mapping[col] = 'IMO'
                elif col_upper in ['FLAGVESCODE', 'FLAG OF FISHING VESSEL', 'FLAG', 'FLAG STATE']:
                    col_mapping[col] = 'Flag'
                elif col_upper in ['IRCS', 'INTERNATIONAL RADIO CALL SIGN', 'CALL SIGN']:
                    col_mapping[col] = 'IRCS'
                # Đã thêm các từ khóa Ngư cụ chuẩn cho mọi tổ chức và IUU (trừ WCPFC vì đã xử lý riêng ở trên)
                elif not is_wcpfc and col_upper in ['ISSCFGCODE', 'TYPE OF FISHING METHOD OR METHODS', 'GEAR', 'GEARS', 'GEARTYPE']:
                    col_mapping[col] = 'Gear'
            
            df = df.rename(columns=col_mapping)
            # Nếu có cột trùng tên do rename, giữ lại cột đầu tiên
            df = df.loc[:, ~df.columns.duplicated()]
            df = df.replace({np.nan: "N/A", "None": "N/A", "": "N/A", "nan": "N/A"})
            
            # Làm sạch dữ liệu IMO và Name
            if 'IMO' in df.columns:
                df['IMO'] = df['IMO'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.upper()
                df['IMO'] = df['IMO'].replace(['NAN', 'NONE', 'N/A', ''], '')
            else:
                df['IMO'] = ""
                
            if 'Name' in df.columns:
                df['Name'] = df['Name'].astype(str).str.strip().str.upper()
            else:
                df['Name'] = ""
            
            # Chốt chặn an toàn chống lỗi KeyError
            for req_col in ['Name', 'IMO', 'Flag', 'IRCS', 'Gear', 'CurrentlyListed']:
                if req_col not in df.columns:
                    df[req_col] = "N/A"
                    
            return df
            
        except Exception as e:
            print(f"Lỗi khi nạp file {filename}: {e}")
            return pd.DataFrame()

    def _search_offline(self, db_name, df, imo, ten_tau):
        default_urls = {
            "ICCAT": "https://www.iccat.int/en/VesselsRecord.asp",
            "WCPFC": "https://vessels.wcpfc.int/",
            "IOTC": "https://rav.iotc.org/",
            "IATTC": "https://www.iattc.org/VesselRegister/VesselList.aspx"
        }
        def_url = default_urls.get(db_name, "https://www.iuu-vessels.org/")

        if df.empty:
            return {
                "status": "error", "message": f"Chưa có dữ liệu offline cho {db_name}.",
                "goc_co": "", "goc_ircs": "", "goc_gear": "", "goc_status": "", "goc_auth": "",
                "source": "offline", "url": def_url
            }

        ten_tau_clean = str(ten_tau).strip().upper() if ten_tau else ""
        imo_clean = str(imo).strip().upper() if imo else ""
        if imo_clean in ["N/A", "NAN", "NONE"]: imo_clean = ""

        if not ten_tau_clean and not imo_clean:
            return {
                "status": "error", "message": f"Thiếu thông tin nhận diện tàu (Tên/IMO) cho {db_name}.",
                "goc_co": "", "goc_ircs": "", "goc_gear": "", "goc_status": "", "goc_auth": "",
                "source": "offline", "url": def_url
            }

        if imo_clean:
            ket_qua = df[df['IMO'] == imo_clean]
        else:
            ket_qua = df[df['Name'].str.upper().str.contains(ten_tau_clean, regex=False, na=False)]

        if not ket_qua.empty:
            tau = ket_qua.iloc[0]
            web_ten = tau.get('Name', 'N/A')
            web_imo = tau.get('IMO', 'N/A')
            web_co = tau.get('Flag', 'N/A')
            web_ircs = tau.get('IRCS', 'N/A')
            web_gear = tau.get('Gear', 'N/A')

            bao_cao = []
            if imo and web_imo != "" and imo != web_imo:
                bao_cao.append(f"Sai IMO ({imo} != {web_imo})")

            thong_tin = f"[Tên: {web_ten} | IMO: {web_imo} | Cờ: {web_co} | Hô hiệu: {web_ircs} | Ngư cụ: {web_gear}]"
            
            if not bao_cao:
                return {
                    "status": "success", 
                    "message": f"Hợp lệ. {db_name} {thong_tin}",
                    "goc_co": web_co, "goc_ircs": web_ircs, "goc_gear": web_gear,
                    "goc_status": "Ủy quyền (CSDL)", "goc_auth": "Còn hiệu lực",
                    "source": "offline", "url": def_url
                }
            else:
                return {
                    "status": "error", 
                    "message": f"Rủi ro: {', '.join(bao_cao)}. Dữ liệu: {thong_tin}",
                    "goc_co": web_co, "goc_ircs": web_ircs, "goc_gear": web_gear,
                    "goc_status": "Cảnh báo", "goc_auth": "",
                    "source": "offline", "url": def_url
                }
        else:
            return {
                "status": "error", "message": f"Không tìm thấy tàu trên cơ sở dữ liệu {db_name}.",
                "goc_co": "", "goc_ircs": "", "goc_gear": "", "goc_status": "", "goc_auth": "",
                "source": "offline", "url": def_url
            }

    def _format_online_result(self, db_name, online_item, imo, ten_tau):
        """Chuẩn hóa và đối chiếu chéo thông tin kết quả trả về từ tra cứu trực tuyến."""
        web_ten = online_item.get("vessel_name", "N/A")
        web_imo = online_item.get("imo", "N/A")
        web_co = online_item.get("flag", "N/A")
        web_ircs = online_item.get("ircs", "N/A")
        web_gear = online_item.get("gear_type", "N/A")
        web_status = online_item.get("status", "N/A")
        web_auth = online_item.get("auth_period", "N/A")
        web_url = online_item.get("url", "")

        bao_cao = []
        imo_c1 = clean_imo_number(imo)
        imo_c2 = clean_imo_number(web_imo)
        if imo_c1 and imo_c2 and imo_c1 != imo_c2:
            bao_cao.append(f"Sai IMO ({imo_c1} != {imo_c2})")

        is_not_active = any(k in web_status.lower() for k in ["không hoạt động", "inactive", "delisted", "hết hạn", "chưa ủy quyền"])
        if is_not_active:
            bao_cao.append(f"Trạng thái: {web_status}")

        thong_tin = f"[Tên: {web_ten} | IMO: {web_imo} | Cờ: {web_co} | Hô hiệu: {web_ircs} | Ngư cụ: {web_gear} | Trạng thái: {web_status}] (Nguồn: Tra cứu trực tuyến {db_name})"

        if is_not_active:
            return {
                "status": "warning",
                "message": f"🚨 Rủi ro: Giấy phép {db_name} {web_status}. {thong_tin}",
                "goc_co": web_co, "goc_ircs": web_ircs, "goc_gear": web_gear,
                "goc_status": web_status, "goc_auth": web_auth,
                "source": "online", "url": web_url
            }
        elif bao_cao:
            return {
                "status": "error",
                "message": f"Rủi ro: {', '.join(bao_cao)}. {thong_tin}",
                "goc_co": web_co, "goc_ircs": web_ircs, "goc_gear": web_gear,
                "goc_status": web_status, "goc_auth": web_auth,
                "source": "online", "url": web_url
            }
        else:
            return {
                "status": "success",
                "message": f"Hợp lệ (Trực tuyến). {db_name} {thong_tin}",
                "goc_co": web_co, "goc_ircs": web_ircs, "goc_gear": web_gear,
                "goc_status": web_status, "goc_auth": web_auth,
                "source": "online", "url": web_url
            }

    MODE_ONLINE_ONLY = True  # Chế độ tra cứu 100% TRỰC TUYẾN trên website của các tổ chức RFMO

    def _search_online(self, db_name, imo, ten_tau):
        """Thực hiện tra cứu trực tiếp thời gian thực trên cổng thông tin RFMO."""
        default_urls = {
            "ICCAT": "https://www.iccat.int/en/VesselsRecord.asp",
            "WCPFC": "https://vessels.wcpfc.int/",
            "IOTC": "https://rav.iotc.org/",
            "IATTC": "https://www.iattc.org/VesselRegister/VesselList.aspx"
        }
        def_url = default_urls.get(db_name, "https://www.iuu-vessels.org/")

        if not self.online_engine:
            return {
                "status": "error", "message": f"Không thể kết nối bộ máy tra cứu trực tuyến {db_name}.",
                "goc_co": "", "goc_ircs": "", "goc_gear": "", "goc_status": "", "goc_auth": "",
                "source": "online", "url": def_url
            }

        imo_clean = clean_imo_number(imo)
        ten_clean = clean_vessel_name(ten_tau)

        if not imo_clean and not ten_clean:
            return {
                "status": "error", "message": f"Thiếu thông tin nhận diện tàu (Tên/IMO) cho {db_name}.",
                "goc_co": "", "goc_ircs": "", "goc_gear": "", "goc_status": "", "goc_auth": "",
                "source": "online", "url": def_url
            }

        search_funcs = {
            "ICCAT": self.online_engine.search_iccat,
            "WCPFC": self.online_engine.search_wcpfc,
            "IOTC": self.online_engine.search_iotc,
            "IATTC": self.online_engine.search_iattc,
        }
        func = search_funcs.get(db_name)
        if not func:
            return {
                "status": "error", "message": f"Không tìm thấy phương thức tra cứu cho {db_name}.",
                "goc_co": "", "goc_ircs": "", "goc_gear": "", "goc_status": "", "goc_auth": "",
                "source": "online", "url": def_url
            }

        online_list = []
        # 1. Ưu tiên tìm trực tuyến theo IMO trước nếu có
        if imo_clean:
            try:
                online_list = func(imo_clean)
            except Exception as e:
                print(f"[{db_name} Online IMO Error]: {e}")

        # 2. Nếu tìm theo IMO không ra nhưng có Tên tàu -> tìm trực tuyến tiếp theo Tên tàu
        if not online_list and ten_clean:
            try:
                online_list = func(ten_clean)
            except Exception as e:
                print(f"[{db_name} Online Name Error]: {e}")

        if online_list:
            return self._format_online_result(db_name, online_list[0], imo, ten_tau)
        else:
            return {
                "status": "error", "message": f"Không tìm thấy tàu trên cổng thông tin trực tuyến {db_name}.",
                "goc_co": "", "goc_ircs": "", "goc_gear": "", "goc_status": "", "goc_auth": "",
                "source": "online", "url": def_url
            }

    def check_iccat(self, imo, ten_tau, rfmo_number="", online_fallback=True):
        if self.MODE_ONLINE_ONLY:
            return self._search_online("ICCAT", imo, ten_tau)
        res = self._search_offline("ICCAT", self.db_iccat, imo, ten_tau)
        if res["status"] == "success" or "Rủi ro:" in res.get("message", ""):
            return res
        return self._search_online("ICCAT", imo, ten_tau)

    def check_wcpfc(self, imo, ten_tau, online_fallback=True):
        if self.MODE_ONLINE_ONLY:
            return self._search_online("WCPFC", imo, ten_tau)
        res = self._search_offline("WCPFC", self.db_wcpfc, imo, ten_tau)
        if res["status"] == "success" or "Rủi ro:" in res.get("message", ""):
            return res
        return self._search_online("WCPFC", imo, ten_tau)

    def check_iattc(self, imo, ten_tau, online_fallback=True):
        if self.MODE_ONLINE_ONLY:
            return self._search_online("IATTC", imo, ten_tau)
        res = self._search_offline("IATTC", self.db_iattc, imo, ten_tau)
        if res["status"] == "success" or "Rủi ro:" in res.get("message", ""):
            return res
        return self._search_online("IATTC", imo, ten_tau)

    def check_iotc(self, imo, ten_tau, online_fallback=True):
        if self.MODE_ONLINE_ONLY:
            return self._search_online("IOTC", imo, ten_tau)
        res = self._search_offline("IOTC", self.db_iotc, imo, ten_tau)
        if res["status"] == "success" or "Rủi ro:" in res.get("message", ""):
            return res
        return self._search_online("IOTC", imo, ten_tau)

    def check_all_rfmo_live(self, imo, ten_tau):
        """Tra cứu song song trên cả 4 tổ chức trực tuyến và trả về kết quả nhanh nhất."""
        if not self.online_engine:
            return {}
        q = str(imo).strip() if (imo and str(imo).strip() not in ["N/A", "NAN", ""]) else str(ten_tau).strip()
        if not q:
            return {}
        return self.online_engine.search_all_concurrent(q)

    def check_iuu_global(self, imo, ten_tau, online_fallback=True):
        """
        Tra cứu danh sách đen IUU toàn cầu:
        1. Ưu tiên tra cứu TRỰC TUYẾN LIVE trên https://www.iuu-vessels.org/Home/Search.
        2. Tự động dự phòng tra cứu Offline qua IUUList.xls nếu mất kết nối mạng.
        """
        ten_tau_clean = clean_vessel_name(ten_tau) if ten_tau else ""
        imo_clean = clean_imo_number(imo) if imo else ""

        # 1. LIVE ONLINE SEARCH (ƯU TIÊN HÀNG ĐẦU)
        if self.online_engine and (self.MODE_ONLINE_ONLY or online_fallback):
            online_items = []
            if imo_clean:
                try:
                    online_items = self.online_engine.search_iuu_global(imo_clean)
                except Exception as e:
                    print(f"[IUU Online IMO Error]: {e}")
            if not online_items and ten_tau_clean:
                try:
                    online_items = self.online_engine.search_iuu_global(ten_tau_clean)
                except Exception as e:
                    print(f"[IUU Online Name Error]: {e}")

            if online_items:
                match = online_items[0]
                status = match.get("status", "Currently Listed")
                w_name = match.get("vessel_name", ten_tau)
                w_imo = match.get("imo", imo)
                w_flag = match.get("flag", "N/A")
                w_url = match.get("url", "https://www.iuu-vessels.org/Home/Search")
                thong_tin = f"[Tên: {w_name} | IMO: {w_imo} | Cờ: {w_flag}]"

                if "Currently" in status:
                    return {
                        "status": "warning",
                        "message": f"🚨 RỦI RO NGHIÊM TRỌNG: Tàu nằm trong DANH SÁCH ĐEN IUU TOÀN CẦU (Đang bị liệt kê trên https://www.iuu-vessels.org/). {thong_tin}",
                        "source": "online",
                        "url": w_url
                    }
                else:
                    return {
                        "status": "info",
                        "message": f"Tàu từng bị cảnh báo IUU nhưng hiện tại đã được gỡ ({status} trên https://www.iuu-vessels.org/). {thong_tin}",
                        "source": "online",
                        "url": w_url
                    }
            elif self.MODE_ONLINE_ONLY:
                return {
                    "status": "success",
                    "message": "Hợp lệ. Không tìm thấy tàu trong danh sách đen IUU toàn cầu (https://www.iuu-vessels.org/).",
                    "source": "online",
                    "url": "https://www.iuu-vessels.org/Home/Search"
                }

        # 2. DỰ PHÒNG OFFLINE (NẾU MẤT KẾT NỐI MẠNG)
        df = self.db_iuu
        if df.empty:
            return {"status": "success", "message": "Hợp lệ. Không tìm thấy tàu trong danh sách đen IUU toàn cầu (Kiểm tra online hoàn tất)."}

        ten_tau_upper = str(ten_tau_clean).strip().upper()
        imo_upper = str(imo_clean).strip().upper()

        match = None
        if imo_upper:
            ket_qua = df[df['IMO'] == imo_upper]
            if not ket_qua.empty: match = ket_qua.iloc[0]

        if match is None and ten_tau_upper:
            ket_qua = df[df['Name'].str.upper().str.contains(ten_tau_upper, regex=False, na=False)]
            if not ket_qua.empty: match = ket_qua.iloc[0]

        if match is not None:
            web_ten = match.get('Name', 'N/A')
            web_imo = match.get('IMO', 'N/A')
            web_co = match.get('Flag', 'N/A')
            currently_listed = str(match.get('CurrentlyListed', 'False')).strip().upper()

            thong_tin = f"[Tên: {web_ten} | IMO: {web_imo} | Cờ: {web_co}]"

            if currently_listed == "TRUE":
                return {"status": "warning", "message": f"🚨 RỦI RO NGHIÊM TRỌNG: Tàu nằm trong DANH SÁCH ĐEN IUU TOÀN CẦU. {thong_tin}", "source": "offline"}
            else:
                return {"status": "info", "message": f"Tàu từng bị cảnh báo IUU nhưng hiện tại đã được gỡ (CurrentlyListed=False). {thong_tin}", "source": "offline"}
        else:
            return {"status": "success", "message": "Hợp lệ. Không tìm thấy tàu trong danh sách đen IUU toàn cầu.", "source": "online" if self.online_engine else "offline"}

    def verify_ho_so(self, extracted_data):
        """
        Đối chiếu toàn bộ hồ sơ khai báo với IUU Global và 4 tổ chức RFMO.
        Trả về: (ho_so_report, vessel_results)
        Hỗ trợ phòng vệ đa hình: payload rỗng, kiểu dữ liệu sai lệch (string/int thay list),
        chuỗi danh sách tàu chưa bóc tách, hoặc các phần tử trong danh sách không phải dict.
        """
        if not isinstance(extracted_data, dict):
            return {"has_violation": False, "total_vessels": 0, "summary": "Không có thông tin tàu để đối chiếu."}, []

        raw_tau = extracted_data.get("tau_danh_bat")
        if not raw_tau:
            return {"has_violation": False, "total_vessels": 0, "summary": "Không có thông tin tàu để đối chiếu."}, []

        # 1. Chuẩn hóa container tau_danh_bat
        if isinstance(raw_tau, (list, tuple, set)):
            tau_list = list(raw_tau)
        elif isinstance(raw_tau, dict):
            tau_list = [raw_tau]
        elif isinstance(raw_tau, str):
            tau_list = [s.strip() for s in re.split(r'[\r\n,;]+', raw_tau) if s.strip()]
        else:
            tau_list = []

        if not tau_list:
            return {"has_violation": False, "total_vessels": 0, "summary": "Không có thông tin tàu để đối chiếu."}, []

        vessel_results = []
        has_violation = False

        for idx, tau in enumerate(tau_list):
            ten = ""
            imo = ""
            dang_ky = ""
            co = ""
            vung_bien = ""
            ngu_cu = ""

            # 2. Bóc tách an toàn tùy thuộc kiểu của từng phần tử
            if isinstance(tau, dict):
                ten = str(tau.get("ten_tau") or tau.get("ten") or tau.get("name") or "").strip()
                imo = str(tau.get("so_imo") or tau.get("imo") or "").strip()
                dang_ky = str(tau.get("so_dang_ky") or tau.get("dang_ky") or "").strip()
                co = str(tau.get("quoc_tich") or tau.get("co") or tau.get("flag") or "").strip()
                vung_bien = str(tau.get("vung_bien") or "").strip().upper()
                ngu_cu = str(tau.get("ngu_cu") or tau.get("gear") or "").strip()
            elif isinstance(tau, str):
                tau_str = tau.strip()
                if not tau_str:
                    continue
                # Bóc tách số IMO 7 chữ số nếu có
                imo_match = re.search(r'\b(?:IMO\s*[:#]?\s*)?([1-9]\d{6})\b', tau_str, flags=re.IGNORECASE)
                if imo_match:
                    imo = imo_match.group(1)
                    ten_candidate = re.sub(r'\(?\s*IMO\s*[:#]?\s*\d+\s*\)?', '', tau_str, flags=re.IGNORECASE).strip()
                    ten = clean_vessel_name(ten_candidate) if (ten_candidate and ten_candidate != imo) else ""
                else:
                    ten = clean_vessel_name(tau_str)
            elif isinstance(tau, (int, float)):
                digits = re.sub(r'[^0-9]', '', str(int(tau)))
                if len(digits) >= 6:
                    imo = digits
                else:
                    continue
            else:
                continue

            v_info = {
                "ten_tau": ten,
                "so_imo": imo,
                "so_dang_ky": dang_ky,
                "quoc_tich": co,
                "is_iuu_listed": False,
                "iuu_status": "Clean",
                "rfmo_urls": {},
                "gear_found": None,
                "fao_found": None,
                "message": ""
            }

            # 3. Kiểm tra IUU Global
            iuu_res = self.check_iuu_global(imo, ten)
            if iuu_res.get("status") == "warning":
                v_info["is_iuu_listed"] = True
                v_info["iuu_status"] = "Currently Listed"
                has_violation = True
            elif iuu_res.get("status") == "info":
                v_info["iuu_status"] = "Delisted"

            # 4. Kiểm tra RFMO theo vùng
            is_ind = any(k in vung_bien for k in ["51", "57", "IND", "IO"])
            is_atl = any(k in vung_bien for k in ["31", "41", "34", "47", "ATL"])
            is_epo = any(k in vung_bien for k in ["77", "87", "EPO", "ETP"])
            is_taiwan = any(k in co.upper() for k in ["TAIWAN", "TWN", "CHINESE TAIPEI", "ĐÀI LOAN"])

            if is_ind:
                iotc_res = self.check_iotc(imo, ten, online_fallback=True)
                if iotc_res.get("url"):
                    v_info["rfmo_urls"]["IOTC"] = iotc_res["url"]
                else:
                    v_info["rfmo_urls"]["IOTC"] = "https://rav.iotc.org/"
                if is_taiwan:
                    v_info["rfmo_urls"]["Cục Ngư nghiệp Đài Loan"] = "https://en.fa.gov.tw/"
            elif is_atl:
                iccat_res = self.check_iccat(imo, ten, online_fallback=True)
                if iccat_res.get("url"):
                    v_info["rfmo_urls"]["ICCAT"] = iccat_res["url"]
            elif is_epo:
                iattc_res = self.check_iattc(imo, ten, online_fallback=True)
                if iattc_res.get("url"):
                    v_info["rfmo_urls"]["IATTC"] = iattc_res["url"]
            else:
                wcpfc_res = self.check_wcpfc(imo, ten, online_fallback=True)
                if wcpfc_res.get("url"):
                    v_info["rfmo_urls"]["WCPFC"] = wcpfc_res["url"]
                else:
                    v_info["rfmo_urls"]["WCPFC"] = "https://vessels.wcpfc.int/"

            vessel_results.append(v_info)

        ho_so_report = {
            "has_violation": has_violation,
            "total_vessels": len(vessel_results),
            "summary": "Phát hiện tàu vi phạm IUU!" if has_violation else "Tất cả các tàu hợp lệ."
        }

        return ho_so_report, vessel_results

# --- TEST LUỒNG HỆ THỐNG ---
RFMOChecker = RFMOCheckerOffline

if __name__ == "__main__":
    import time
    checker = RFMOCheckerOffline()