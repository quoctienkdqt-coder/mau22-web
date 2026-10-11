import os
import json
import time
import re
from concurrent.futures import ThreadPoolExecutor
from google import genai
from google.genai import types
from config import BASE_DIR
from gfw_checker import GFWChecker
from vessel_utils import clean_vessel_name, clean_imo_number, deduplicate_vessels
class ExtractionResult(dict):
    """
    Kết quả trích xuất kép:
    - Vừa là dict chuẩn có các keys: status, data, execution_time, message (theo hợp đồng PROJECT.md)
    - Vừa chứa trực tiếp các trường nghiệp vụ top-level (ten_co_so, tau_danh_bat...) phục vụ UI Streamlit
    - Ép kiểu boolean thông minh: False khi lỗi hoặc trạng thái không thành công
    """
    def __bool__(self):
        return self.get("status") == "success"

# Alias để bảo đảm tương thích cả với ExtractResult và ExtractionResult
ExtractResult = ExtractionResult

class AIService:
    def __init__(self, api_key):
        self.client = genai.Client(api_key=api_key)

    @classmethod
    def extract_data(cls, file_paths, prompt_type="LUONG_1", api_key=None, progress_callback=None, model_name="gemini-3.8-flash", luong_type=None, **kwargs):
        """
        Classmethod adapter đa năng kết nối Web Streamlit và Backend AI Service.
        Hỗ trợ cả prompt_type và luong_type, tự động phân giải API key đa tầng.
        """
        from config import get_gemini_api_key
        
        t0 = time.perf_counter()
        effective_key = (api_key or "").strip() or get_gemini_api_key()
        if not effective_key:
            return ExtractionResult({
                "status": "error",
                "data": {},
                "execution_time": 0.0,
                "message": "Không tìm thấy Gemini API Key hợp lệ."
            })

        if not file_paths:
            return ExtractionResult({
                "status": "error",
                "data": {},
                "execution_time": 0.0,
                "message": "Danh sách tệp tài liệu trống."
            })

        # Chuẩn hóa luồng nghiệp vụ
        if luong_type:
            effective_luong = luong_type
        elif prompt_type:
            p_str = str(prompt_type).lower()
            if "22" in p_str or "mau22" in p_str:
                effective_luong = "LUONG_2"
            else:
                effective_luong = "LUONG_1"
        else:
            effective_luong = "LUONG_1"

        if callable(progress_callback):
            try:
                progress_callback("Đang nạp và trích xuất qua Gemini AI...", 25)
            except Exception:
                pass

        try:
            service = cls(api_key=effective_key)
            success, raw_data, err_msg, in_tok, out_tok = service.process_document(
                file_paths=file_paths,
                model_name=model_name,
                luong_type=effective_luong
            )
            exec_time = round(time.perf_counter() - t0, 2)

            if success and isinstance(raw_data, dict):
                result_payload = {
                    "status": "success",
                    "data": raw_data,
                    "execution_time": exec_time,
                    "message": "Trích xuất thành công",
                    "in_tokens": in_tok,
                    "out_tokens": out_tok,
                    **raw_data
                }
                return ExtractionResult(result_payload)
            else:
                return ExtractionResult({
                    "status": "error",
                    "data": {},
                    "execution_time": exec_time,
                    "message": err_msg or "Không trích xuất được dữ liệu."
                })
        except Exception as ex:
            exec_time = round(time.perf_counter() - t0, 2)
            return ExtractionResult({
                "status": "error",
                "data": {},
                "execution_time": exec_time,
                "message": str(ex)
            })

    def _load_prompt(self, file_name, default_prompt):
        """Đọc file prompt, nếu chưa có thì tự tạo (dùng đường dẫn tuyệt đối)"""
        full_path = os.path.join(BASE_DIR, file_name) if not os.path.isabs(file_name) else file_name
        if not os.path.exists(full_path):
            try:
                with open(full_path, 'w', encoding='utf-8') as f: 
                    f.write(default_prompt.strip())
            except Exception: pass
            return default_prompt.strip()
        else:
            try:
                with open(full_path, 'r', encoding='utf-8') as f: 
                    return f.read().strip()
            except Exception: 
                return default_prompt.strip()

    def process_document(self, file_paths, model_name, luong_type="LUONG_1"):
        """
        Hàm xử lý chung cho cả 2 luồng.
        Trả về: (success, extracted_data, error_msg, in_tokens, out_tokens)
        """
        uploaded_files = []
        try:
            # 1. Chuẩn bị Prompt tùy theo luồng
            if luong_type == "LUONG_1":
                default_prompt = """You are an expert Customs Officer and an IUU Fishing Vessel Assessor... (Trích xuất chứng từ gốc)
                Strictly return JSON.""" # Ghi chú: Bạn có thể đưa full text prompt vào đây
                prompt_file = "prompt_chungtu.txt"
            else:
                default_prompt = """Bạn là chuyên gia số hóa dữ liệu hải quan hải quan Việt Nam (Mẫu 22.KT)... (Số hóa Mẫu 22 cũ)
                Strictly return JSON.""" # Ghi chú: Đưa full text prompt tiếng Việt vào đây
                prompt_file = "prompt_mau22.txt"

            actual_prompt = self._load_prompt(prompt_file, default_prompt)

            # 2. Upload files lên Google Cloud (đa luồng song song tăng tốc độ tải)
            t_upload_start = time.time()

            def _upload_single(item):
                idx, fp = item
                ext = os.path.splitext(fp)[1].lower()
                mime = "application/pdf" if ext == ".pdf" else ("image/jpeg" if ext in [".jpg", ".jpeg"] else ("image/png" if ext == ".png" else "application/octet-stream"))
                safe_name = f"doc_{idx}{ext}"
                try:
                    with open(fp, "rb") as f_stream:
                        uf = self.client.files.upload(
                            file=f_stream,
                            config=dict(mime_type=mime, display_name=safe_name)
                        )
                    wait_count = 0
                    while uf.state.name == "PROCESSING" and wait_count < 30:
                        time.sleep(0.4)
                        uf = self.client.files.get(name=uf.name)
                        wait_count += 1
                    if uf.state.name == "FAILED":
                        raise Exception("Google Cloud báo tệp FAILED")
                    return idx, uf
                except Exception:
                    # Dự phòng tức thì nạp dữ liệu trực tiếp in-memory qua types.Part.from_bytes
                    with open(fp, "rb") as f_stream:
                        file_bytes = f_stream.read()
                    part = types.Part.from_bytes(data=file_bytes, mime_type=mime)
                    return idx, part

            max_workers = min(len(file_paths), 5) if len(file_paths) > 1 else 1
            if max_workers > 1:
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    results = list(executor.map(_upload_single, enumerate(file_paths, 1)))
                    results.sort(key=lambda x: x[0])
                    uploaded_files = [r[1] for r in results]
            else:
                idx, uf = _upload_single((1, file_paths[0]))
                uploaded_files = [uf]

            t_upload_duration = round(time.time() - t_upload_start, 2)
            
            contents = [actual_prompt] + uploaded_files

            # 3. Chuyển đổi tên model từ UI sang API chuẩn
            model_mapping = {
                "Gemini 3.8 Flash": "gemini-3.8-flash",
                "gemini-3.8-flash": "gemini-3.8-flash",
                "Gemini 3.5 Flash": "gemini-3.5-flash",
                "gemini-3.5-flash": "gemini-3.5-flash",
                "gemini-2.5-flash": "gemini-3.8-flash",  # Tự động nâng cấp phiên bản đã ngừng cung cấp
                "gemini-2.0-flash": "gemini-3.8-flash",
                "gemini-1.5-flash": "gemini-3.8-flash",
                "gemini-3.1-pro-preview": "gemini-3.1-pro-preview",
                "Gemini 3.1 Pro": "gemini-3.1-pro-preview"
            }
            api_model_name = model_mapping.get(model_name, "gemini-3.8-flash")
            if not api_model_name or "2.5-flash" in str(api_model_name):
                api_model_name = "gemini-3.8-flash"

            # 4. Gọi API
            t_ai_start = time.time()
            response = None
            last_error = "" 
            for _ in range(3):
                try:
                    response = self.client.models.generate_content(
                        model=api_model_name,
                        contents=contents, 
                        config=types.GenerateContentConfig(temperature=0.0, response_mime_type="application/json")
                    )
                    break
                except Exception as e:
                    last_error = str(e)
                    time.sleep(3)
            
            if not response:
                raise Exception(f"Lỗi kết nối máy chủ AI: {last_error}")
            t_ai_duration = round(time.time() - t_ai_start, 2)

            # 5. Parse kết quả làm sạch markdown
            t_post_start = time.time()
            resp_text = response.text.strip()
            if resp_text.startswith("```"):
                lines = resp_text.splitlines()
                if lines and lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                resp_text = "\n".join(lines).strip()

            # Bóc tách JSON khối an toàn nếu có text rác xung quanh
            json_match = re.search(r'(\{[\s\S]*\})', resp_text)
            clean_json_str = json_match.group(1) if json_match else resp_text
            extracted_data = json.loads(clean_json_str)
            extracted_data = self._post_process_data(extracted_data, raw_text=response.text)
            t_post_duration = round(time.time() - t_post_start, 2)
            t_total_duration = round(time.time() - t_upload_start, 2)
            
            try:
                print(f"[THOI GIAN AI] Tai file: {t_upload_duration}s | Suy luan: {t_ai_duration}s | Hau xu ly: {t_post_duration}s | Tong: {t_total_duration}s")
            except Exception:
                pass
            
            try:
                in_tok = response.usage_metadata.prompt_token_count
                out_tok = response.usage_metadata.candidates_token_count
            except:
                in_tok, out_tok = 0, 0

            return True, extracted_data, "", in_tok, out_tok

        except Exception as e:
            return False, {}, str(e), 0, 0
        finally:
            # Luôn dọn dẹp file trên Cloud kể cả khi có lỗi xảy ra
            for f in uploaded_files:
                if hasattr(f, "name") and f.name:
                    try: self.client.files.delete(name=f.name)
                    except: pass

    def _post_process_data(self, data, raw_text=""):
        """Chuẩn hóa dữ liệu sau khi nhận từ AI theo quy chuẩn nghiệp vụ Mẫu 22 KT"""
        if not isinstance(data, dict):
            return data

        # 1. Chuẩn hóa bảng Sản phẩm (san_pham)
        dia_chi_cs = str(data.get("dia_chi", "")).strip()
        tuna_map = {
            "yellowfin": "Cá ngừ vây vàng",
            "thunnus albacares": "Cá ngừ vây vàng",
            "yft": "Cá ngừ vây vàng",
            "albacore": "Cá ngừ vây dài",
            "thunnus alalunga": "Cá ngừ vây dài",
            "alb": "Cá ngừ vây dài",
            "bigeye": "Cá ngừ mắt to",
            "thunnus obesus": "Cá ngừ mắt to",
            "bet": "Cá ngừ mắt to",
            "skipjack": "Cá ngừ vằn",
            "katsuwonus pelamis": "Cá ngừ vằn",
            "skj": "Cá ngừ vằn",
            "swordfish": "Cá kiếm",
            "xiphias gladius": "Cá kiếm",
            "swo": "Cá kiếm",
            "black marlin": "Cá đen",
            "marlin": "Cá cờ",
            "istiompax indica": "Cá cờ",
            "blm": "Cá cờ",
            "mackerel": "Cá thu"
        }

        if "san_pham" in data and isinstance(data["san_pham"], list):
            for sp in data["san_pham"]:
                if not isinstance(sp, dict): continue
                # Kích cỡ luôn luôn là Nhiều Size
                sp["kich_co"] = "Nhiều Size"

                # Mã HS chuẩn hóa 8 số không phân cách
                if "hs_code" in sp:
                    digits = re.sub(r'[^0-9]', '', str(sp["hs_code"]))
                    sp["hs_code"] = digits[:8] if len(digits) >= 8 else digits

                # Chuẩn hóa tên loài sang tiếng Việt nếu còn sót tiếng Anh
                loai_curr = str(sp.get("loai", "")).strip()
                loai_lower = loai_curr.lower()
                for en_key, vn_val in tuna_map.items():
                    if re.search(r'\b' + re.escape(en_key) + r'\b', loai_lower):
                        sp["loai"] = vn_val
                        break

        # 1.5. Chuẩn hóa & Gộp trùng bảng Tàu đánh bắt (tau_danh_bat):
        # Tự động loại bỏ tiền tố tàu (FV, F/V, MV, M/V...), chuẩn hóa số IMO và khử trùng lặp
        if "tau_danh_bat" in data and isinstance(data["tau_danh_bat"], list):
            data["tau_danh_bat"] = deduplicate_vessels(data["tau_danh_bat"])

            # Đảm bảo ngư cụ không bị khuyết: nếu AI bỏ sót, tự động lấy từ văn bản gốc
            has_gear = any(str(v.get("ngu_cu", "")).strip() for v in data["tau_danh_bat"] if isinstance(v, dict))
            if not has_gear and raw_text:
                rt_upper = raw_text.upper()
                fallback_gear = ""
                if "PURSE SEINE" in rt_upper or "PURSE-SEINE" in rt_upper:
                    fallback_gear = "Purse Seine"
                elif "LONGLINE" in rt_upper or "LONG LINE" in rt_upper:
                    fallback_gear = "Longline"
                elif "POLE AND LINE" in rt_upper:
                    fallback_gear = "Pole and Line"
                elif "TRAWL" in rt_upper:
                    fallback_gear = "Trawl"

                if fallback_gear:
                    for v in data["tau_danh_bat"]:
                        if isinstance(v, dict) and not str(v.get("ngu_cu", "")).strip():
                            v["ngu_cu"] = fallback_gear

        # 2. Chuẩn hóa bảng Chuyển tải (thong_tin_chuyen_tai): Ngày bắt đầu dd/mm/yyyy & Làm sạch tên tàu
        if "thong_tin_chuyen_tai" in data and isinstance(data["thong_tin_chuyen_tai"], list):
            for ct in data["thong_tin_chuyen_tai"]:
                if not isinstance(ct, dict): continue
                # Làm sạch tên tàu khai thác và tàu nhận (loại bỏ FV, F/V, MV...)
                if "tau_khai_thac" in ct:
                    ct["tau_khai_thac"] = clean_vessel_name(ct["tau_khai_thac"])
                if "tau_nhan" in ct:
                    ct["tau_nhan"] = clean_vessel_name(ct["tau_nhan"])
                if "imo" in ct:
                    c_imo = clean_imo_number(ct["imo"])
                    if c_imo: ct["imo"] = c_imo
                tg = str(ct.get("thoi_gian", "")).strip()
                if tg:
                    # TH 1: Dạng ISO 'YYYY-MM-DD' hoặc 'YYYY/MM/DD'
                    m_iso = re.search(r'(\d{4})[/.-](\d{1,2})[/.-](\d{1,2})', tg)
                    if m_iso:
                        ct["thoi_gian"] = f"{int(m_iso.group(3)):02d}/{int(m_iso.group(2)):02d}/{m_iso.group(1)}"
                    else:
                        # TH 2: Dạng dd/mm/yyyy đầy đủ
                        m_full = re.search(r'(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})', tg)
                        if m_full:
                            d, m, y = m_full.group(1), m_full.group(2), m_full.group(3)
                            prefix = tg[:m_full.start()].strip()
                            m_pre = re.search(r'(?:^|[^\d])(\d{1,2})\s*[-–]\s*$', prefix)
                            if m_pre:
                                d = m_pre.group(1)
                            ct["thoi_gian"] = f"{int(d):02d}/{int(m):02d}/{y}"

        # 2.5. Chuẩn hóa bảng Giấy phép chuyển tải (giay_phep_chuyen_tai):
        if "giay_phep_chuyen_tai" in data and isinstance(data["giay_phep_chuyen_tai"], list):
            gp_seen = set()
            new_gp_list = []
            for gp in data["giay_phep_chuyen_tai"]:
                if not isinstance(gp, dict): continue
                if "tau_chuyen_tai" in gp:
                    gp["tau_chuyen_tai"] = clean_vessel_name(gp["tau_chuyen_tai"])
                if "imo" in gp:
                    c_imo = clean_imo_number(gp["imo"])
                    if c_imo: gp["imo"] = c_imo
                key_gp = (gp.get("tau_chuyen_tai", "").upper(), gp.get("imo", ""), gp.get("giay_phep", ""))
                if key_gp not in gp_seen:
                    gp_seen.add(key_gp)
                    new_gp_list.append(gp)
            data["giay_phep_chuyen_tai"] = new_gp_list

        # 2.6. Chuẩn hóa bảng Sản lượng cập bến (san_luong_cap_ben):
        if "san_luong_cap_ben" in data and isinstance(data["san_luong_cap_ben"], list):
            for sl in data["san_luong_cap_ben"]:
                if not isinstance(sl, dict): continue
                if "tau" in sl:
                    sl["tau"] = clean_vessel_name(sl["tau"])
                if "imo" in sl:
                    c_imo = clean_imo_number(sl["imo"])
                    if c_imo: sl["imo"] = c_imo

        # 3. Chuẩn hóa bảng Container (cong_ten_no):
        if "cong_ten_no" in data and isinstance(data["cong_ten_no"], list):
            for cn in data["cong_ten_no"]:
                if not isinstance(cn, dict): continue
                # Tàu chở: chỉ lấy tên tàu, loại bỏ FV/MV và số chuyến V.2608N, VOY 12, 2402S...
                tau = str(cn.get("tau_cho", "")).strip()
                if tau:
                    tau_clean = clean_vessel_name(tau)
                    tau_clean = re.sub(r'[\s,/]+(?:V(?:OY)?\.?|\bVOYAGE\.?)\s*[\d]+[A-Za-z0-9\-\.]*$', '', tau_clean, flags=re.IGNORECASE).strip()
                    tau_clean = re.sub(r'[\s,/]+\d{2,4}[EWNSewns]$', '', tau_clean).strip()
                    cn["tau_cho"] = tau_clean or tau

                # Cảng xuất: chỉ lấy tên cảng, loại bỏ tên quốc gia sau dấu phẩy/ngoặc
                cang = str(cn.get("cang_xuat", "")).strip()
                if cang:
                    cang_clean = re.split(r'[,/–\-\(]', cang)[0].strip()
                    cn["cang_xuat"] = cang_clean or cang

                # Địa chỉ kho: tự động lấy theo địa chỉ cơ sở nếu trống
                if dia_chi_cs and (not cn.get("dia_chi_kho") or str(cn.get("dia_chi_kho")).strip() in ["", "N/A", "None", "null"]):
                    cn["dia_chi_kho"] = dia_chi_cs

            # 4. Tra cứu IMO cho tàu container: CHỈ TRA CỨU 1 LẦN cho mỗi tên tàu duy nhất rồi điền cho tất cả các dòng
            vessel_imo_map = {}
            for cn in data["cong_ten_no"]:
                if not isinstance(cn, dict): continue
                tau_name = str(cn.get("tau_cho", "")).strip()
                existing_imo = str(cn.get("imo", "")).strip()
                if tau_name and existing_imo and existing_imo not in ["", "N/A", "None", "null"]:
                    vessel_imo_map[tau_name.upper()] = existing_imo

            # Chỉ gọi mạng GFW một lần duy nhất cho những tàu chưa có IMO
            gfw_client = None
            for cn in data["cong_ten_no"]:
                if not isinstance(cn, dict): continue
                tau_name = str(cn.get("tau_cho", "")).strip()
                if not tau_name: continue
                tau_upper = tau_name.upper()
                
                if tau_upper not in vessel_imo_map:
                    if gfw_client is None:
                        gfw_client = GFWChecker()
                    try:
                        imo_found = gfw_client.get_imo_by_name(tau_name)
                        if imo_found:
                            vessel_imo_map[tau_upper] = imo_found
                        else:
                            vessel_imo_map[tau_upper] = ""  # Ghi nhớ không có để không tra lại
                    except Exception:
                        vessel_imo_map[tau_upper] = ""

            # Điền số IMO đồng loạt cho tất cả các dòng container tương ứng
            for cn in data["cong_ten_no"]:
                if not isinstance(cn, dict): continue
                if not cn.get("imo") or str(cn.get("imo", "")).strip() in ["", "N/A", "None", "null"]:
                    tau_name = str(cn.get("tau_cho", "")).strip().upper()
                    if tau_name in vessel_imo_map and vessel_imo_map[tau_name]:
                        cn["imo"] = vessel_imo_map[tau_name]

        return data