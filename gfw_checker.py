import requests
import json
import os
import re
import urllib.parse
from datetime import datetime
from config import BASE_DIR

class GFWChecker:
    def __init__(self):
        # Token siêu bảo mật của anh Tiến
        self.token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6ImtpZEtleSJ9.eyJkYXRhIjp7Im5hbWUiOiJUaWVuIiwidXNlcklkIjo1MjM1NSwiYXBwbGljYXRpb25OYW1lIjoiVGllbiIsImlkIjoxNTA2MiwidHlwZSI6InVzZXItYXBwbGljYXRpb24ifSwiaWF0IjoxNzkwMzM4NjI4LCJleHAiOjIxMDU2OTg2MjgsImF1ZCI6ImdmdyIsImlzcyI6ImdmdyJ9.Ac3-G0ml0Bb6AJs-pZRczilQFolkKdrhF1qnhLuLcG4lcz55arxsksrudH03hzRSy8TNXhiVZG9bApc-Lg84cDz7_SFkaIxZa1POWm1SGRDDxp9Trt4YhTh7opKFUf-ZqtzuMxeeJgK98H1yw2NgyljLFCNvmqJY8Sx4cGzeGIruICTeTvkDSdzNy46gSogRlss5u5zw4PSY-bcuuPLkBgLT1rFLi1In68-F34t3S0dJ52iGn0agCwCPrcdbaPadZzTVGxBIGtIFLB1xlQfHofqmzVdGSeJ4cMT7wVSc3L2E6syULLnlQpdTNafx-Y0iLZvcqo8RqUhPXiepAUmj3jK3pWQDJ72G6jSy5V2jrvHF7fy7x5o7ceh9r8NV0ivfAOWNowW0Av34oEh8ZIBOd5i0zcSTU0FOEIUkYjrcc5Q2GV4PlBEy43ZClYdxnl1K888pYhaMymO6yDOtyaZWYDYZFTS2rvkkj-OYuel6cWR_VvQPLlXT-7dnx9x54AVG"
        self.base_url = "https://gateway.api.globalfishingwatch.org/v3"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        self.cache_file = os.path.join(BASE_DIR, "gfw_cache.json")
        self.cache = self._load_cache()

    def _load_cache(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f: return json.load(f)
            except: return {}
        return {}

    def _save_cache(self):
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f: json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @staticmethod
    def parse_date_to_iso(date_str):
        """Chuyển đổi linh hoạt mọi định dạng ngày (Việt/Anh/ISO) sang YYYY-MM-DD chuẩn GFW"""
        if not date_str: return ""
        s = str(date_str).strip()
        formats = [
            "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d",
            "%b %d, %Y", "%d %b %Y", "%B %d, %Y", "%d %B %Y",
            "%Y%m%d", "%d.%m.%Y"
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(s, fmt)
                return dt.strftime("%Y-%m-%d")
            except Exception:
                pass
        m1 = re.search(r'(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})', s)
        if m1:
            return f"{m1.group(1)}-{int(m1.group(2)):02d}-{int(m1.group(3)):02d}"
        m2 = re.search(r'(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})', s)
        if m2:
            return f"{m2.group(3)}-{int(m2.group(2)):02d}-{int(m2.group(1)):02d}"
        return ""

    def check_ais(self, imo, ten_tau="", tu_ngay="", den_ngay=""):
        imo_clean = str(imo).replace(".0", "").strip().upper() if imo else ""
        if not imo_clean or imo_clean in ["N/A", "NONE", "NAN"]:
            return {"status": "error", "message": "Thiếu số IMO.", "map_url": "", "vessel_info": {}}

        # Nếu tu_ngay chứa cả dải ngày (ví dụ: '15/02/2024 - 20/05/2024')
        if tu_ngay and not den_ngay:
            split_patterns = [r'\s+to\s+', r'\s*-\s*', r'\s+đến\s+', r'\s*~\s*']
            for pat in split_patterns:
                parts = re.split(pat, str(tu_ngay).strip(), flags=re.IGNORECASE)
                if len(parts) == 2:
                    tu_ngay, den_ngay = parts[0].strip(), parts[1].strip()
                    break

        start_iso = self.parse_date_to_iso(tu_ngay)
        end_iso = self.parse_date_to_iso(den_ngay)

        cache_key = f"{imo_clean}_{start_iso}_{end_iso}"
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            # Chỉ dùng lại cache nếu có URL hợp lệ dạng vessel profile
            if cached.get("map_url") and "/vessel/" in cached.get("map_url", ""):
                return cached

        try:
            url = f"{self.base_url}/vessels/search"
            dataset = "public-global-vessel-identity:latest"
            # Tìm kiếm trực tiếp bằng số IMO chuẩn để không bị nhầm lẫn
            params = {"query": imo_clean, "datasets[0]": dataset, "limit": 10}
            
            res = requests.get(url, headers=self.headers, params=params, timeout=10)
            
            if res.status_code == 200:
                data = res.json()
                entries = data.get("entries", [])
                
                # Fallback tìm kiếm bằng tên tàu nếu tìm theo IMO không ra
                if not entries and ten_tau:
                    params["query"] = str(ten_tau).strip()
                    res = requests.get(url, headers=self.headers, params=params, timeout=10)
                    if res.status_code == 200:
                        entries = res.json().get("entries", [])
                
                if entries:
                    # Tìm bản ghi khớp chính xác nhất với IMO mục tiêu
                    matched_entry = None
                    matched_shipname = ""
                    matched_flag = ""
                    matched_dataset = entries[0].get("dataset", "public-global-vessel-identity:v4.0")
                    
                    for entry in entries:
                        for reg in entry.get("registryInfo", []):
                            if str(reg.get("imo", "")).strip().upper() == imo_clean:
                                matched_entry = entry
                                matched_shipname = reg.get("shipname", "")
                                matched_flag = reg.get("flag", "")
                                break
                        if matched_entry: break
                        
                        for self_rep in entry.get("selfReportedInfo", []):
                            if str(self_rep.get("imo", "")).strip().upper() == imo_clean:
                                matched_entry = entry
                                matched_shipname = self_rep.get("shipname", "")
                                matched_flag = self_rep.get("flag", "")
                                break
                        if matched_entry: break
                        
                    if not matched_entry:
                        matched_entry = entries[0]
                        if matched_entry.get("registryInfo"):
                            matched_shipname = matched_entry["registryInfo"][0].get("shipname", "")
                            matched_flag = matched_entry["registryInfo"][0].get("flag", "")
                        elif matched_entry.get("selfReportedInfo"):
                            matched_shipname = matched_entry["selfReportedInfo"][0].get("shipname", "")
                            matched_flag = matched_entry["selfReportedInfo"][0].get("flag", "")
                    
                    # Bóc tách ID tàu chuẩn xác từ cấu trúc lồng nhau của GFW
                    vessel_id = None
                    if matched_entry.get("combinedSourcesInfo"):
                        vessel_id = matched_entry["combinedSourcesInfo"][0].get("vesselId")
                    if not vessel_id and matched_entry.get("selfReportedInfo"):
                        vessel_id = matched_entry["selfReportedInfo"][0].get("id")
                    if not vessel_id and matched_entry.get("registryInfo"):
                        vessel_id = matched_entry["registryInfo"][0].get("id")
                    
                    vessel_info = {
                        "vessel_id": vessel_id,
                        "shipname": matched_shipname or ten_tau,
                        "flag": matched_flag,
                        "imo": imo_clean
                    }
                    
                    # Khởi tạo Map URL chuẩn dẫn trực tiếp vào Vessel Profile (giao diện chi tiết tàu)
                    # Khi mở link này, trình duyệt sẽ nhảy THẲNG vào giao diện chi tiết của tàu
                    # với thanh thời gian và hải trình được vẽ sẵn từ ngày A đến ngày B
                    if vessel_id:
                        if start_iso and end_iso:
                            map_url = f"https://globalfishingwatch.org/map/vessel/{vessel_id}?start={start_iso}&end={end_iso}"
                        elif start_iso:
                            map_url = f"https://globalfishingwatch.org/map/vessel/{vessel_id}?start={start_iso}"
                        else:
                            map_url = f"https://globalfishingwatch.org/map/vessel/{vessel_id}"
                    else:
                        map_url = f"https://globalfishingwatch.org/map/?q={imo_clean}"
                    
                    msg_text = f"Có tín hiệu AIS [{matched_shipname or ten_tau} - IMO: {imo_clean}]"
                    if start_iso and end_iso:
                        msg_text += f" (Thời gian CS: {start_iso} đến {end_iso})"
                    elif start_iso:
                        msg_text += f" (Từ ngày CS: {start_iso})"
                    
                    result = {
                        "status": "success",
                        "message": msg_text,
                        "map_url": map_url,
                        "vessel_info": vessel_info,
                        "start_iso": start_iso,
                        "end_iso": end_iso
                    }
                    self.cache[cache_key] = result
                    self._save_cache()
                    return result
                else:
                    msg_warn = f"Tàu không phát tín hiệu AIS / Tắt định vị (IMO: {imo_clean})"
                    if start_iso and end_iso:
                        msg_warn += f" [CS: {start_iso} ~ {end_iso}]"
                    result = {
                        "status": "warning",
                        "message": msg_warn,
                        "map_url": f"https://globalfishingwatch.org/map/?q={imo_clean}",
                        "vessel_info": {"imo": imo_clean, "shipname": ten_tau}
                    }
                    self.cache[cache_key] = result
                    self._save_cache()
                    return result
            else:
                return {"status": "error", "message": f"GFW chặn truy vấn ({res.status_code})", "map_url": f"https://globalfishingwatch.org/map/?q={imo_clean}", "vessel_info": {}}
        except Exception as e:
            return {"status": "error", "message": f"Lỗi mạng: {str(e)}", "map_url": f"https://globalfishingwatch.org/map/?q={imo_clean}", "vessel_info": {}}

    def get_imo_by_name(self, ten_tau: str) -> str | None:
        """Search GFW vessel database by ship name and return the IMO if found.
        Returns None if no IMO could be retrieved.
        """
        if not ten_tau:
            return None
        try:
            url = f"{self.base_url}/vessels/search"
            dataset = "public-global-vessel-identity:latest"
            params = {"query": ten_tau.strip(), "datasets[0]": dataset, "limit": 10}
            res = requests.get(url, headers=self.headers, params=params, timeout=10)
            if res.status_code != 200:
                return None
            data = res.json()
            entries = data.get("entries", [])
            for entry in entries:
                for reg in entry.get("registryInfo", []):
                    imo_val = str(reg.get("imo", "")).strip()
                    if imo_val and imo_val.upper() not in ["N/A", "NONE", "NAN"]:
                        return imo_val
                for self_rep in entry.get("selfReportedInfo", []):
                    imo_val = str(self_rep.get("imo", "")).strip()
                    if imo_val and imo_val.upper() not in ["N/A", "NONE", "NAN"]:
                        return imo_val
            return None
        except Exception:
            return None