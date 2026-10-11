"""
rfmo_online_engine.py
Module tra cứu trực tuyến trực tiếp trên các cổng thông tin RFMO:
- WCPFC (Western and Central Pacific Fisheries Commission)
- ICCAT (International Commission for the Conservation of Atlantic Tunas)
- IOTC (Indian Ocean Tuna Commission)
- IATTC (Inter-American Tropical Tuna Commission)

Hỗ trợ tra cứu song song đa luồng (Concurrent ThreadPool), trả về kết quả chuẩn hóa.
"""

import re
import urllib3
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from vessel_utils import clean_vessel_name, clean_imo_number

urllib3.disable_warnings()

COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
}


class RFMOOnlineEngine:
    """Công cụ truy vấn trực tiếp dữ liệu tàu từ website của 4 tổ chức RFMO."""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=25, pool_maxsize=25, max_retries=1)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update(COMMON_HEADERS)

    # =========================================================================
    # 1. WCPFC LIVE SEARCH
    # =========================================================================
    def search_wcpfc(self, query: str) -> list[dict]:
        """
        Tra cứu trên WCPFC (vessels.wcpfc.int).
        Tìm kiếm theo tên tàu, số IMO, WIN hoặc IRCS qua autocomplete JSON API.
        """
        query = str(query).strip()
        if not query:
            return []

        # Tự động làm sạch tên tàu (loại bỏ FV, F/V, MV...) trước khi tra cứu
        is_num = query.isdigit() and len(query) >= 6
        clean_q = query if is_num else clean_vessel_name(query)
        if not clean_q:
            clean_q = query

        search_url = f"https://vessels.wcpfc.int/vessel/results?q={requests.utils.quote(clean_q)}"
        results = []

        headers = {
            **COMMON_HEADERS,
            "X-Requested-With": "XMLHttpRequest"
        }

        try:
            resp = self.session.get(search_url, headers=headers, timeout=self.timeout)
            if resp.status_code != 200:
                return []

            data = resp.json()
            if not isinstance(data, list):
                return []

            for item in data[:5]:  # Lấy tối đa 5 kết quả phù hợp nhất
                val_str = item.get("value", "")
                label = item.get("label", "")
                if not val_str or "No vessel found" in label:
                    continue

                m_name = re.match(r"^(.*?)\s*\(\s*VID:\s*(\d+)\s*\)", val_str)
                web_vessel_name = m_name.group(1).strip() if m_name else val_str
                vid = m_name.group(2) if m_name else None

                v_url = f"https://vessels.wcpfc.int/vessel/{vid}" if vid else search_url
                details = {}

                if vid:
                    try:
                        r_sub = self.session.get(v_url, headers=COMMON_HEADERS, timeout=8)
                        if r_sub.status_code == 200:
                            s_sub = BeautifulSoup(r_sub.text, "html.parser")
                            for d in s_sub.find_all("div", class_=lambda c: c and "d-flex" in c):
                                lbl = d.find("div", class_="field__label")
                                val_div = d.find("div", class_="field__item") or d.find("div", class_="field__items")
                                if lbl and val_div:
                                    k = re.sub(r"[:\s]+$", "", lbl.get_text(strip=True))
                                    v = val_div.get_text(separator=", ", strip=True)
                                    details[k] = v
                    except Exception:
                        pass

                valid_from = details.get("Start of period of validity of authorization", "")
                valid_to = details.get("End of period of validity of authorization", "")
                valid_period = f"{valid_from} -> {valid_to}" if (valid_from or valid_to) else "N/A"

                auth_status = details.get("Authorization status", "Đang ủy quyền")

                # Kết hợp đầy đủ Ngư cụ (Gear Type) và Loại tàu (Vessel Type)
                gear_val = details.get("Gear Type", "").strip()
                v_type_val = details.get("Vessel Type", "").strip()
                if gear_val and v_type_val and gear_val.lower() != v_type_val.lower():
                    gear_display = f"{gear_val} ({v_type_val})"
                else:
                    gear_display = gear_val or v_type_val or "N/A"

                results.append({
                    "rfmo": "WCPFC",
                    "vessel_name": web_vessel_name,
                    "imo": details.get("IMO/LR", query if query.isdigit() and len(query) == 7 else ""),
                    "ircs": details.get("IRCS", ""),
                    "flag": details.get("Vessel Flag", ""),
                    "gear_type": gear_display,
                    "auth_period": valid_period,
                    "status": "Ủy quyền (Authorized)" if "Authorized" in auth_status else auth_status,
                    "rfmo_id": vid or "",
                    "url": v_url,
                    "raw": details
                })
        except Exception as e:
            try:
                print(f"[WCPFC] Lỗi tra cứu: {e}")
            except Exception:
                pass

        return results

    # =========================================================================
    # 2. ICCAT LIVE SEARCH
    # =========================================================================
    def search_iccat(self, query: str) -> list[dict]:
        """
        Tra cứu trên ICCAT (ioms.iccat.int API v2).
        Tìm kiếm theo IMO hoặc tên tàu.
        """
        query = str(query).strip()
        if not query:
            return []

        base_url = "https://ioms.iccat.int/vesselspublic-api/v2/vessels/search"
        results = []

        is_imo = query.isdigit() and len(query) >= 6

        if is_imo:
            params = {"filter": f"intRegNo=={query}"}
        else:
            c_name = clean_vessel_name(query)
            params = {"filter": f"vesselName==*{c_name}*"}

        try:
            r = self.session.get(base_url, params=params, verify=False, timeout=self.timeout)
            if r.status_code == 200:
                data = r.json()
                items = data.get("content", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])

                for item in items[:10]:
                    v_name = item.get("vesselName", "")
                    imo = item.get("intRegNo", "")
                    flag = item.get("flag", "")
                    ircs = item.get("ircs", "")
                    gear = item.get("isscfgCode", "")
                    v_type = item.get("vesselType", "")
                    active = item.get("active", True)
                    v_id = item.get("id", "")

                    auths = item.get("authList", [])
                    auth_str = ""
                    if auths and isinstance(auths, list):
                        latest_auth = auths[0]
                        d_from = latest_auth.get("dateFrom", "")
                        d_to = latest_auth.get("dateTo", "")
                        if d_from or d_to:
                            auth_str = f"{d_from} -> {d_to}"

                    gear_display = f"{gear} ({v_type})" if gear and v_type else (gear or v_type)

                    results.append({
                        "rfmo": "ICCAT",
                        "vessel_name": v_name,
                        "imo": str(imo) if imo else "",
                        "ircs": str(ircs) if ircs else "",
                        "flag": flag,
                        "gear_type": gear_display,
                        "auth_period": auth_str,
                        "status": "Hoạt động (Active)" if active else "Không hoạt động",
                        "rfmo_id": str(v_id),
                        "url": f"https://ioms.iccat.int/vessels/details/{v_id}" if v_id else "https://ioms.iccat.int/vessels",
                        "raw": item
                    })
        except Exception as e:
            print(f"[ICCAT] Lỗi tra cứu: {e}")

        return results

    # =========================================================================
    # 3. IOTC LIVE SEARCH
    # =========================================================================
    def search_iotc(self, query: str) -> list[dict]:
        """
        Tra cứu trên IOTC (rav.iotc.org API).
        Hỗ trợ tìm theo tên tàu, số IMO hoặc mã IOTC.
        """
        query = str(query).strip()
        if not query:
            return []

        url = "https://rav.iotc.org/domain/record/search"
        results = []

        is_imo = query.isdigit() and len(query) >= 6
        is_iotc_id = query.upper().startswith("IOTC")

        if is_imo:
            conditions = [{"vids": [f"TG-imo-scheme://{query}"]}]
        elif is_iotc_id:
            conditions = [{"ids": [f"TG-iotc-scheme://{query}"]}]
        else:
            c_name = clean_vessel_name(query)
            conditions = [{"names": [c_name]}]

        payload = {
            "language": "en",
            "sort": [{"field": "timestamp", "mode": "desc"}],
            "cursor": {"page": 1, "pageSize": 10},
            "conditions": conditions
        }

        try:
            r = self.session.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=self.timeout)
            if r.status_code == 200:
                data = r.json()
                raw_results = data.get("results", [])

                for item in raw_results:
                    details = item.get("details", {})
                    v_name = details.get("name", "")
                    flag = details.get("flagstate", {}).get("name", "") if isinstance(details.get("flagstate"), dict) else details.get("flagstate", "")
                    state = details.get("state", "")
                    gears = details.get("gears", [])
                    gear_str = ", ".join([g.replace("TG-", "").replace("-gear", "").upper() for g in gears]) if isinstance(gears, list) else str(gears)

                    identifiers = details.get("identifiers", [])
                    imo_found = ""
                    ircs_found = ""
                    for ident in identifiers:
                        if "imo-scheme://" in ident:
                            imo_found = ident.split("imo-scheme://")[-1]
                        elif "ircs-scheme://" in ident:
                            ircs_found = ident.split("ircs-scheme://")[-1]

                    uvi = item.get("uvi", "")
                    iotc_num = uvi.split("iotc-scheme://")[-1] if "iotc-scheme://" in uvi else uvi

                    avl = item.get("avl", {})
                    auth_decls = avl.get("declarations", [])
                    auth_str = ""
                    if auth_decls and isinstance(auth_decls, list):
                        years = [str(d.get("year")) for d in auth_decls if d.get("year")]
                        if years:
                            auth_str = f"Năm hoạt động: {', '.join(years[:3])}"

                    results.append({
                        "rfmo": "IOTC",
                        "vessel_name": v_name,
                        "imo": imo_found or (query if is_imo else ""),
                        "ircs": ircs_found,
                        "flag": flag.replace("T-", "") if flag else "",
                        "gear_type": gear_str,
                        "auth_period": auth_str,
                        "status": "Hoạt động (Active)" if state.lower() == "active" else f"Trạng thái: {state}",
                        "rfmo_id": iotc_num,
                        "url": f"https://rav.iotc.org/vessel/{iotc_num}" if iotc_num else "https://rav.iotc.org",
                        "raw": item
                    })
        except Exception as e:
            print(f"[IOTC] Lỗi tra cứu: {e}")

        return results

    # =========================================================================
    # 4. IATTC LIVE SEARCH
    # =========================================================================
    def search_iattc(self, query: str) -> list[dict]:
        """
        Tra cứu trên IATTC (iattc.org VesselRegister).
        Hỗ trợ tìm theo tên tàu, số IMO hoặc số IATTC.
        """
        query = str(query).strip()
        if not query:
            return []

        search_url = "https://www.iattc.org/en-US/Vessel/SearchVesselBy"
        results = []

        is_num = query.isdigit()
        is_imo = is_num and len(query) >= 6

        if is_imo:
            params = {"Data.Criterias.IMONo": query, "Data.Criterias.IsConfirmed": "O"}
        elif is_num and len(query) < 6:
            params = {"Data.Criterias.VRVesNo": query, "Data.Criterias.IsConfirmed": "O"}
        else:
            c_name = clean_vessel_name(query)
            params = {"Data.Criterias.VesselName": c_name, "Data.Criterias.IsConfirmed": "O"}

        headers = {**COMMON_HEADERS, "X-Requested-With": "XMLHttpRequest"}

        try:
            r = self.session.get(search_url, params=params, headers=headers, verify=False, timeout=self.timeout)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                table = soup.find("table")
                if table:
                    rows = table.find_all("tr")
                    for row in rows[1:]:
                        cols = row.find_all(["td", "th"])
                        if len(cols) < 5:
                            continue

                        iattc_no = cols[0].get_text(strip=True)
                        v_name = cols[1].get_text(strip=True)
                        gear = cols[2].get_text(strip=True)
                        flag = cols[3].get_text(strip=True)
                        length = cols[4].get_text(strip=True) if len(cols) > 4 else ""
                        capacity = cols[6].get_text(strip=True) if len(cols) > 6 else ""

                        imo_found = query if is_imo else ""
                        ircs_found = ""
                        auth_period = f"Dài: {length}m, Trọng tải: {capacity}t" if length else ""
                        detail_url = f"https://www.iattc.org/en-US/Vessel/Detail?vesselNo={iattc_no}"

                        try:
                            r_det = self.session.get(detail_url, headers=headers, verify=False, timeout=8)
                            if r_det.status_code == 200:
                                t_det = r_det.text
                                m_imo = re.search(r"IMO\s*#:\s*</b>\s*([0-9]{7})", t_det, re.IGNORECASE)
                                if m_imo:
                                    imo_found = m_imo.group(1)

                                m_call = re.search(r"Call\s*sign:\s*</b>\s*([A-Z0-9]+)", t_det, re.IGNORECASE)
                                if m_call:
                                    ircs_found = m_call.group(1)
                        except Exception:
                            pass

                        results.append({
                            "rfmo": "IATTC",
                            "vessel_name": v_name,
                            "imo": imo_found,
                            "ircs": ircs_found,
                            "flag": flag,
                            "gear_type": gear,
                            "auth_period": auth_period,
                            "status": "Có đăng ký (Registered)",
                            "rfmo_id": iattc_no,
                            "url": f"https://www.iattc.org/VesselRegister/VesselDetail.aspx?VesNo={iattc_no}",
                            "raw": {
                                "iattc_no": iattc_no,
                                "length": length,
                                "capacity": capacity
                            }
                        })
        except Exception as e:
            print(f"[IATTC] Lỗi tra cứu: {e}")

        return results

    # =========================================================================
    # 5. LIVE SEARCH TỔNG HỢP (TẤT CẢ 4 TỔ CHỨC CÙNG LÚC)
    # =========================================================================
    def search_all_concurrent(self, query: str) -> dict[str, list[dict]]:
        """
        Tra cứu song song trên cả 4 tổ chức WCPFC, ICCAT, IOTC, IATTC.
        Sử dụng ThreadPoolExecutor để phản hồi nhanh nhất.
        """
        results_by_rfmo = {
            "WCPFC": [],
            "ICCAT": [],
            "IOTC": [],
            "IATTC": []
        }

        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_rfmo = {
                executor.submit(self.search_wcpfc, query): "WCPFC",
                executor.submit(self.search_iccat, query): "ICCAT",
                executor.submit(self.search_iotc, query): "IOTC",
                executor.submit(self.search_iattc, query): "IATTC",
            }

            for future in as_completed(future_to_rfmo):
                rfmo_name = future_to_rfmo[future]
                try:
                    data = future.result()
                    results_by_rfmo[rfmo_name] = data
                except Exception as exc:
                    print(f"[{rfmo_name}] Ngoại lệ: {exc}")

        return results_by_rfmo

    # =========================================================================
    # 6. IUU GLOBAL LIVE SEARCH (https://www.iuu-vessels.org/Home/Search)
    # =========================================================================
    def search_iuu_global(self, query: str) -> list[dict]:
        """
        Tra cứu trực tuyến trên cổng danh sách đen IUU toàn cầu (https://www.iuu-vessels.org/Home/Search).
        Hỗ trợ tìm kiếm theo IMO hoặc tên tàu.
        """
        query = str(query).strip()
        if not query or query in ["N/A", "NAN", "NONE"]:
            return []

        url = "https://www.iuu-vessels.org/Home/Search"
        payload = {
            "SearchString": query,
            "Listed": "true",
            "Delisted": "true",
            "CCAMLR": "true",
            "IATTC": "true",
            "ICCAT": "true",
            "IOTC": "true",
            "NAFO": "true",
            "NEAFC": "true",
            "SEAFO": "true",
            "WCPFC": "true",
            "SPRFMO": "true",
            "GFCM": "true",
            "NPFC": "true",
            "SIOFA": "true",
            "CCSBT": "true"
        }
        results = []
        try:
            r = self.session.post(url, data=payload, headers={"User-Agent": "Mozilla/5.0"}, timeout=self.timeout)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                table = soup.find("table")
                if table:
                    rows = table.find_all("tr")[1:]
                    for tr in rows:
                        tds = [td.get_text(strip=True) for td in tr.find_all("td")]
                        if not tds:
                            continue
                        v_name = tds[0] if len(tds) > 0 else ""
                        imo_num = tds[1] if len(tds) > 1 else ""
                        ircs = tds[2] if len(tds) > 2 else ""
                        matches_info = tds[3] if len(tds) > 3 else ""

                        link = tr.find("a")
                        detail_href = link.get("href", "") if link else ""
                        detail_url = f"https://www.iuu-vessels.org{detail_href}" if detail_href.startswith("/") else detail_href

                        status = "Currently Listed"
                        flag = ""
                        if detail_url:
                            try:
                                r_detail = self.session.get(detail_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
                                if r_detail.status_code == 200:
                                    d_soup = BeautifulSoup(r_detail.text, "html.parser")
                                    h_text = " ".join([h.get_text(strip=True) for h in d_soup.find_all(["h1", "h2", "h3"])])
                                    if "Delisted" in h_text or "Previously Listed" in h_text:
                                        status = "Delisted"
                                    elif "Currently Listed" in h_text:
                                        status = "Currently Listed"

                                    for row_tr in d_soup.find_all("tr"):
                                        row_text = row_tr.get_text(strip=True)
                                        if "Flag" in row_text:
                                            cells = [c.get_text(strip=True) for c in row_tr.find_all(["td", "th"])]
                                            if len(cells) >= 2:
                                                flag = cells[1]
                                                break
                            except Exception:
                                pass

                        results.append({
                            "rfmo": "IUU_GLOBAL",
                            "vessel_name": v_name,
                            "imo": imo_num,
                            "ircs": ircs,
                            "flag": flag,
                            "status": status,
                            "url": detail_url,
                            "matches_info": matches_info
                        })
        except Exception as e:
            print(f"[IUU Global Online] Lỗi tra cứu: {e}")

        return results

# Singleton instance dùng chung
rfmo_engine = RFMOOnlineEngine()
