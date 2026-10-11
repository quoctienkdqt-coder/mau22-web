"""
vessel_utils.py
Các hàm tiện ích chuẩn hóa tên tàu, loại bỏ tiền tố FV/MV, gộp trùng tàu (Deduplication),
và đối chiếu chính xác nhóm ngư cụ (ISSCFG Gear Classification) cho hệ thống IUU/RFMO.
"""

import re

# =============================================================================
# 1. BẢNG PHÂN LOẠI NHÓM NGƯ CỤ CHUẨN QUỐC TẾ (ISSCFG & THỰC TẾ KHAI BÁO)
# =============================================================================
GEAR_FAMILIES = {
    "PS": {
        "name": "Lưới vây (Purse seine)",
        "keywords": [
            "PURSE SEINE", "PURSE-SEINE", "PURSE SEINES", "PURSE SEINER",
            "PURSE", "SEINE", "SEINES", "SEINER",
            "ONE BOAT OPERATED PURSE SEINES", "TWO BOATS OPERATED PURSE SEINES",
            "LƯỚI VÂY", "LUOI VAY", "VÂY", "VAY",
            "SURROUNDING", "RING NET"
        ],
        "regex": [r"\bPS\b", r"\bLP\b"]
    },
    "LL": {
        "name": "Câu vàng (Longline)",
        "keywords": [
            "LONGLINE", "LONG LINE", "LONG-LINE", "LONGLINER", "LONGLINES",
            "DRIFTING LONGLINE", "DRIFTING LONGLINES", "SET LONGLINE", "SET LONGLINES",
            "HOOK AND LINE", "HOOKS AND LINES", "HOOK & LINE",
            "CÂU VÀNG", "CAU VANG", "CÂU TẦNG PHỦ"
        ],
        "regex": [r"\bLL\b", r"\bLHP\b", r"\bLTL\b"]
    },
    "PL": {
        "name": "Câu cần (Pole and line)",
        "keywords": [
            "POLE AND LINE", "POLE & LINE", "POLE-AND-LINE", "POLE LINE",
            "BAITBOAT", "CÂU CẦN", "CAU CAN"
        ],
        "regex": [r"\bPL\b", r"\bBB\b"]
    },
    "HL": {
        "name": "Câu tay (Handline)",
        "keywords": [
            "HANDLINE", "HAND LINE", "HAND-LINE", "HANDLINES",
            "CÂU TAY", "CAU TAY"
        ],
        "regex": [r"\bHL\b"]
    },
    "TR": {
        "name": "Lưới kéo (Trawl)",
        "keywords": [
            "TRAWL", "TRAWLER", "TRAWLS", "OTTER TRAWL", "PELAGIC TRAWL",
            "BOTTOM TRAWL", "BEAM TRAWL", "LƯỚI KÉO", "LUOI KEO"
        ],
        "regex": [r"\bTR\b", r"\bOTB\b", r"\bPTM\b", r"\bTBN\b"]
    },
    "GN": {
        "name": "Lưới rê (Gillnet)",
        "keywords": [
            "GILLNET", "GILL NET", "GILL-NET", "GILLNETS", "DRIFTNET", "DRIFT NET",
            "LƯỚI RÊ", "LUOI RE"
        ],
        "regex": [r"\bGN\b", r"\bGNS\b", r"\bGND\b"]
    },
    "CAR": {
        "name": "Tàu chuyển tải (Carrier)",
        "keywords": [
            "CARRIER", "FISH CARRIER", "REEFER", "TRANSPORT",
            "CHUYỂN TẢI", "CHUYEN TAI"
        ],
        "regex": [r"\bCAR\b"]
    },
    "SUP": {
        "name": "Tàu hỗ trợ (Support)",
        "keywords": [
            "SUPPORT", "SUPPLY", "BUNKER", "TENDER", "HỖ TRỢ", "HO TRO"
        ],
        "regex": [r"\bSUP\b"]
    }
}


def detect_gear_family(gear_text: str) -> str | None:
    """
    Xác định mã nhóm ngư cụ chuẩn (PS, LL, PL, HL, TR, GN, CAR, SUP) từ chuỗi mô tả ngư cụ
    hoặc loại tàu (Vessel Type / Gear Type).
    """
    if not gear_text:
        return None
    gt = str(gear_text).strip().upper()
    if gt in ["", "N/A", "NONE", "UNKNOWN", "NULL", "NAN", "WEB KHÔNG HIỂN THỊ"]:
        return None

    # 1. Quét theo từ khóa dài trước
    for code, conf in GEAR_FAMILIES.items():
        for kw in conf["keywords"]:
            if kw in gt:
                return code

    # 2. Quét theo regex ranh giới từ (cho các mã viết tắt 2 ký tự như PS, LL, PL...)
    for code, conf in GEAR_FAMILIES.items():
        for pat in conf.get("regex", []):
            if re.search(pat, gt):
                return code

    return None


def check_gear_match(declared_gear: str, rfmo_gear_or_vessel_type: str) -> tuple[bool, str]:
    """
    Kiểm tra đối chiếu ngư cụ giữa tờ khai (AI bóc tách) và CSDL RFMO (Trực tuyến hoặc Offline).
    Trả về: (is_match: bool, reason: str)
    """
    g_dec = str(declared_gear or "").strip()
    g_rfmo = str(rfmo_gear_or_vessel_type or "").strip()

    # Nếu một trong hai bên không có thông tin ngư cụ -> Coi như đạt (không bắt lỗi oan)
    if not g_dec or g_dec.upper() in ["", "N/A", "NONE", "UNKNOWN", "NAN"]:
        return True, "Tờ khai không ghi ngư cụ"
    if not g_rfmo or g_rfmo.upper() in ["", "N/A", "NONE", "UNKNOWN", "NAN", "WEB KHÔNG HIỂN THỊ"]:
        return True, "RFMO không có dữ liệu ngư cụ"

    fam_dec = detect_gear_family(g_dec)
    fam_rfmo = detect_gear_family(g_rfmo)

    # Nếu cả 2 đều nhận diện được nhóm ngư cụ
    if fam_dec and fam_rfmo:
        if fam_dec == fam_rfmo:
            return True, f"Khớp nhóm ngư cụ ({fam_dec} - {GEAR_FAMILIES[fam_dec]['name']})"
        else:
            return False, f"Lệch nhóm ngư cụ: Tờ khai thuộc nhóm '{fam_dec}' ({g_dec}), nhưng RFMO ghi nhóm '{fam_rfmo}' ({g_rfmo})"

    # Dự phòng: Kiểm tra từ khóa giao nhau trực tiếp (ví dụ cả 2 đều có chữ PURSE hoặc SEINE hoặc LONGLINE)
    words_dec = set(re.findall(r'[A-Za-z]{3,}', g_dec.upper()))
    words_rfmo = set(re.findall(r'[A-Za-z]{3,}', g_rfmo.upper()))
    common_words = words_dec.intersection(words_rfmo)
    # Loại trừ các từ chung chung
    common_words.difference_update({"BOAT", "OPERATED", "TYPE", "FISHING", "VESSEL", "AND", "THE"})
    if common_words:
        return True, f"Khớp từ khóa ngư cụ ({', '.join(common_words)})"

    # Nếu một bên không nhận diện được mã và không giao từ khóa nhưng không xác định rõ
    # Nếu tờ khai hoặc RFMO chứa chuỗi của nhau
    if g_dec.upper() in g_rfmo.upper() or g_rfmo.upper() in g_dec.upper():
        return True, "Chuỗi ngư cụ trùng khớp tương đối"

    # Không khớp thực sự
    return False, f"Lệch ngư cụ: Tờ khai ghi '{g_dec}', CSDL RFMO ghi '{g_rfmo}'"


# =============================================================================
# 2. LÀM SẠCH TÊN TÀU & LOẠI BỎ TIỀN TỐ (FV, F/V, MV, M/V...)
# =============================================================================
def clean_vessel_name(name: str) -> str:
    """
    Loại bỏ tiền tố phân loại tàu phổ biến (FV, F/V, MV, M/V, TV, MT, Tàu cá...)
    và các ký tự đặc biệt ở đầu/cuối tên tàu.
    Ví dụ:
      'FV GABRIELLE L.T.'    -> 'GABRIELLE L.T.'
      'F/V GABRIELLE L.T.'   -> 'GABRIELLE L.T.'
      'F.V. GABRIELLE L.T.'  -> 'GABRIELLE L.T.'
      'MV SAWASDEE ALTAIR'   -> 'SAWASDEE ALTAIR'
      'Tàu cá THÀNH ĐẠT'     -> 'THÀNH ĐẠT'
    """
    if not name:
        return ""
    n = str(name).strip()
    if not n:
        return ""

    # Biểu thức chính quy bắt các tiền tố ở đầu: F/V, FV, F.V., M/V, MV, M.V., T/V, TV, M/T, MT, S/V, SV, TÀU CÁ, TÀU...
    prefix_pattern = r'^(?:(?:F\s*[\./]?\s*V|M\s*[\./]?\s*V|T\s*[\./]?\s*V|M\s*[\./]?\s*T|S\s*[\./]?\s*V|TÀU\s+CÁ|TAU\s+CA|TÀU|TAU)[\s\.\:\-_/]+)+'
    cleaned = re.sub(prefix_pattern, '', n, flags=re.IGNORECASE).strip()

    # Dọn dẹp dấu nháy kép, nháy đơn, ngoặc thừa ở 2 đầu (không xóa dấu chấm cuối vì tên có thể kết thúc bằng chữ viết tắt như L.T.)
    cleaned = re.sub(r'^[\s"\'\-:;.]+', '', cleaned)
    cleaned = re.sub(r'[\s"\'\-:;]+$', '', cleaned)
    return cleaned if cleaned else n


def clean_imo_number(imo: str) -> str:
    """Lấy số IMO chuẩn (chỉ giữ lại các chữ số)."""
    if not imo:
        return ""
    digits = re.sub(r'[^0-9]', '', str(imo).strip())
    # Số IMO chuẩn hàng hải thế giới có độ dài 7 chữ số (hoặc 6-8 chữ số)
    return digits if len(digits) >= 6 else ""


# =============================================================================
# 3. GỘP TRÙNG DỮ LIỆU TÀU (DEDUPLICATION THEO IMO VÀ TÊN)
# =============================================================================
def deduplicate_vessels(vessel_list: list[dict]) -> list[dict]:
    """
    Khử trùng lặp danh sách tàu đánh bắt:
    - Loại bỏ tiền tố tàu (FV, F/V, MV...).
    - Nếu cùng 1 tàu có NHIỀU GIẤY PHÉP KHÁC NHAU (VD: OPRS... và PNG-062) -> BẮT BUỘC GIỮ THÀNH TỪNG DÒNG ĐỘC LẬP.
    - Chỉ gộp khi trùng hoàn toàn cả Tàu + Giấy phép, hoặc gộp dòng thừa không có giấy phép vào dòng có giấy phép.
    """
    if not vessel_list or not isinstance(vessel_list, list):
        return []

    # Nếu có dòng bị gộp sẵn bằng dấu chấm phẩy do dữ liệu cũ, tự động tách ra thành từng dòng độc lập
    expanded_list = []
    for v in vessel_list:
        if not isinstance(v, dict): continue
        raw_gp = str(v.get("giay_phep", "")).strip()
        # Kiểm tra nếu ô giấy phép bị gộp nhiều số giấy phép bằng dấu ';'
        if ";" in raw_gp:
            gps = [g.strip() for g in raw_gp.split(";") if g.strip()]
            for g_item in gps:
                v_single = dict(v)
                v_single["giay_phep"] = g_item
                expanded_list.append(v_single)
        else:
            expanded_list.append(v)

    merged_map = {}
    ordered_keys = []
    vessel_has_license = {}

    for v in expanded_list:
        v_copy = dict(v)

        raw_name = str(v_copy.get("ten", "")).strip()
        cleaned_name = clean_vessel_name(raw_name)
        v_copy["ten"] = cleaned_name

        raw_imo = str(v_copy.get("imo", "")).strip()
        cleaned_imo = clean_imo_number(raw_imo)
        if cleaned_imo:
            v_copy["imo"] = cleaned_imo
            v_id = f"IMO:{cleaned_imo}"
        elif cleaned_name:
            v_id = f"NAME:{cleaned_name.upper()}"
        else:
            continue

        raw_gp = str(v_copy.get("giay_phep", "")).strip()
        norm_gp = re.sub(r'[^A-Za-z0-9]', '', raw_gp).upper()

        if norm_gp:
            vessel_has_license[v_id] = True

        # Định danh độc lập: Tàu + Số giấy phép
        key = (v_id, norm_gp)

        if key not in merged_map:
            merged_map[key] = v_copy
            ordered_keys.append(key)
        else:
            # Trùng lặp hoàn toàn cùng 1 giấy phép -> Bổ sung các trường còn thiếu
            existing = merged_map[key]
            for f in ["ho_hieu", "rfmo", "co_quan", "ngay_het_han", "khu_vuc", "doi_tuong", "ngu_cu", "tu_ngay", "den_ngay", "xuat_xu", "fao"]:
                val_exist = str(existing.get(f, "")).strip()
                val_new = str(v_copy.get(f, "")).strip()
                if (not val_exist or val_exist.upper() in ["N/A", "NONE"]) and val_new and val_new.upper() not in ["N/A", "NONE"]:
                    existing[f] = val_new

    # Loại bỏ dòng trống giấy phép thừa nếu tàu đó đã có ít nhất một dòng có giấy phép
    final_rows = []
    for k in ordered_keys:
        v_id, norm_gp = k
        if not norm_gp and vessel_has_license.get(v_id, False):
            # Chuyển tiếp các thông tin phụ (ngày khai thác, hô hiệu...) sang dòng có giấy phép
            empty_row = merged_map[k]
            for licensed_k in ordered_keys:
                if licensed_k[0] == v_id and licensed_k[1]:
                    target = merged_map[licensed_k]
                    for f in ["ho_hieu", "rfmo", "khu_vuc", "doi_tuong", "ngu_cu", "tu_ngay", "den_ngay", "co_quan", "ngay_het_han"]:
                        if not str(target.get(f, "")).strip() and str(empty_row.get(f, "")).strip():
                            target[f] = empty_row[f]
            continue
        final_rows.append(merged_map[k])

    # 1. Lan truyền thông tin chung (ngư cụ, hô hiệu, RFMO, vùng biển, đối tượng, ngày khai thác)
    # giữa các dòng giấy phép của CÙNG 1 CON TÀU
    vessel_shared_info = {}
    dossier_gear = ""
    for r in final_rows:
        v_id = r.get("imo") or r.get("ten")
        if not v_id: continue
        if v_id not in vessel_shared_info:
            vessel_shared_info[v_id] = {}
        for f in ["ngu_cu", "ho_hieu", "rfmo", "khu_vuc", "doi_tuong", "tu_ngay", "den_ngay", "xuat_xu", "fao"]:
            val = str(r.get(f, "")).strip()
            if val and val.upper() not in ["N/A", "NONE", "NULL"]:
                if f not in vessel_shared_info[v_id]:
                    vessel_shared_info[v_id][f] = val
                if f == "ngu_cu" and not dossier_gear:
                    dossier_gear = val

    for r in final_rows:
        v_id = r.get("imo") or r.get("ten")
        if v_id and v_id in vessel_shared_info:
            for f, val in vessel_shared_info[v_id].items():
                curr_val = str(r.get(f, "")).strip()
                if not curr_val or curr_val.upper() in ["N/A", "NONE", "NULL"]:
                    r[f] = val
        # Nếu vẫn còn khuyết ngư cụ nhưng toàn bộ lô hàng có ngư cụ chung (VD: Purse Seine)
        if dossier_gear and (not str(r.get("ngu_cu", "")).strip() or str(r.get("ngu_cu", "")).strip().upper() in ["N/A", "NONE", "NULL"]):
            r["ngu_cu"] = dossier_gear

    return final_rows


# =============================================================================
# 4. CHUẨN HÓA CỜ QUỐC TỊCH (COUNTRY FLAGS)
# =============================================================================
COUNTRY_ALIAS = {
    "PAN": "PANAMA", "PA": "PANAMA",
    "PHL": "PHILIPPINES", "PH": "PHILIPPINES", "PHILIPPINE": "PHILIPPINES",
    "TWN": "CHINESE TAIPEI", "TW": "CHINESE TAIPEI", "TAIWAN": "CHINESE TAIPEI",
    "VNM": "VIETNAM", "VN": "VIETNAM", "VIỆT NAM": "VIETNAM",
    "KOR": "KOREA", "KR": "KOREA", "SOUTH KOREA": "KOREA",
    "JPN": "JAPAN", "JP": "JAPAN",
    "CHN": "CHINA", "CN": "CHINA",
    "COL": "COLOMBIA", "CO": "COLOMBIA",
    "AUS": "AUSTRALIA", "AU": "AUSTRALIA",
    "USA": "UNITED STATES", "US": "UNITED STATES",
    "IDN": "INDONESIA", "ID": "INDONESIA",
    "THA": "THAILAND", "TH": "THAILAND",
    "MYS": "MALAYSIA", "MY": "MALAYSIA",
    "FSM": "MICRONESIA", "FM": "MICRONESIA",
    "PNG": "PAPUA NEW GUINEA", "PG": "PAPUA NEW GUINEA",
    "KIR": "KIRIBATI", "KI": "KIRIBATI",
    "VUT": "VANUATU", "VU": "VANUATU",
    "MHL": "MARSHALL ISLANDS", "MH": "MARSHALL ISLANDS"
}

def normalize_country_flag(flag: str) -> str:
    """Chuẩn hóa tên quốc gia / cờ quốc tịch sang dạng chuẩn tiếng Anh."""
    if not flag:
        return ""
    f = str(flag).strip().upper()
    return COUNTRY_ALIAS.get(f, f)
