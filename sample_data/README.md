# BỘ DỮ LIỆU MẪU CHUẨN NGHIỆP VỤ THỦY SẢN (SAMPLE DATA PACKAGE)
## HỆ THỐNG KIỂM TRA HỒ SƠ THỦY SẢN KHAI IUU & MẪU 22.KT (PRO)

---

### 1. GIỚI THIỆU TỔNG QUAN

Thư mục `sample_data/` chứa gói dữ liệu mẫu nghiệp vụ chuẩn hóa phục vụ:
- **Trải nghiệm ngay lập tức (1-Click Demo)**: Giúp người dùng, kiểm toán viên và cơ quan thẩm quyền trải nghiệm toàn bộ tính năng của hệ thống mà không cần chuẩn bị sẵn file quét (PDF/Ảnh) hay tiêu tốn hạn mức Google Gemini API.
- **Kiểm thử tự động (E2E & Pre-deploy Testing)**: Cung cấp nguồn dữ liệu chuẩn để kiểm tra chức năng xuất Word Mẫu 22.KT, đối soát IUU/RFMO Live, và lưu trữ vào cơ sở dữ liệu SQLite `dulieu_tau.db`.
- **Hồ sơ thực tế chuẩn mực**: Dữ liệu được mô phỏng dựa trên lô hàng nhập khẩu cá ngừ viễn dương thực tế của doanh nghiệp thủy sản lớn tại tỉnh Khánh Hòa (**Công Ty TNHH Cá Ngừ Việt Nam**, KCN Suối Dầu - khớp 100% với danh mục doanh nghiệp trong `Danh_sach_cong_ty.xlsx`).

---

### 2. TỪ ĐIỂN DỮ LIỆU & ÁNH XẠ 8 TAB NGHIỆP VỤ

Tệp `sample_data/mau_chuan_thuy_san.json` bao phủ toàn diện 8 khối thông tin cấu trúc tương ứng 8 tab trên giao diện:

| Khối / Tab | Tên nghiệp vụ | Khóa JSON (`key`) | Mô tả chi tiết |
|:---|:---|:---|:---|
| **Header & Tab 1** | Thông tin cơ sở & Lô hàng | `kinh_gui`, `ten_co_so`, `dia_chi`, `nguoi_dai_dien`, `sdt`, `email`, `so_to_khai`, `ngay_to_khai`, `tong_san_luong`, `thoi_gian_boc_do`, `dia_diem_boc_do` | Cơ quan tiếp nhận: Chi cục Thủy sản tỉnh Khánh Hòa. Doanh nghiệp nhập khẩu: Công Ty TNHH Cá Ngừ Việt Nam. Tờ khai: 105892348120 ngày 15/03/2024. Tổng sản lượng: 125,480 kg. |
| **Bảng 1 / Tab 2** | Sản phẩm thủy sản nhập khẩu | `san_pham` (danh sách) | 3 dòng sản phẩm cá ngừ đại dương: Cá ngừ vây vàng đông lạnh (HS `03034200`, 65,200 kg), Cá ngừ mắt to đông lạnh (HS `03034400`, 42,150 kg), Cá ngừ vằn đông lạnh (HS `03034300`, 18,130 kg). Tổng khối lượng cộng dồn: 125,480 kg. |
| **Bảng 2 / Tab 3** | Tàu đánh bắt & Ngư cụ | `tau_danh_bat` (danh sách) | 2 tàu đánh bắt chuẩn 10 trường dữ liệu: `TALENT 36` (IMO `8745814`, Hô hiệu `S7TB`, IOTC, Lưới vây) và `OCEAN HARVEST 8` (IMO `9123847`, Hô hiệu `V4OH`, IOTC, Câu cá ngừ). Cả 2 tàu đều sạch trong danh sách đen IUU và đã đăng ký hợp lệ tại IOTC. |
| **Bảng 3 / Tab 4** | Thông tin chuyển tải | `thong_tin_chuyen_tai` (danh sách) | 2 đợt chuyển tải trên biển từ tàu khai thác sang tàu thu mua cấp đông `PACIFIC REEFER 1` (IMO `8912345`, Cờ Panama) tại Ấn Độ Dương. |
| **Bảng 4 / Tab 5** | Giấy phép chuyển tải | `giay_phep_chuyen_tai` (danh sách) | Giấy phép chuyển tải `TS-AUTH-IOTC-2024-012` do Cơ quan Hàng hải Panama cấp cho tàu `PACIFIC REEFER 1` (hạn đến 30/06/2025). |
| **Bảng 5 / Tab 6** | Sản lượng cập bến | `san_luong_cap_ben` (danh sách) | Tàu nhận `PACIFIC REEFER 1` cập cảng `Port Victoria, Seychelles` ngày 28/02/2024, khối lượng 125,480 kg. |
| **Bảng 6 / Tab 7** | Thông tin công ten nơ | `cong_ten_no` (danh sách) | 3 container lạnh tiêu chuẩn ISO (`TGHU9234812`, `MSKU5198234`, `CMAU7321945`) kèm số chì niêm phong, vận chuyển bởi tàu `MAERSK VISBY` (IMO `9412836`) về Kho Lạnh Hải Vương (Khánh Hòa). |
| **Bảng Đối soát / Tab 8** | Đối soát IUU & RFMO Live | Tự động sinh từ `tau_danh_bat` | Đối soát chéo với CSDL IUU Global (`IUUList.xls`) và 4 tổ chức nghề cá khu vực (IOTC, ICCAT, WCPFC, IATTC). Kết quả: **🟢 AN TOÀN TUYỆT ĐỐI (0 VI PHẠM)**. |

---

### 3. HƯỚNG DẪN SỬ DỤNG

#### Cách 1: Nạp 1-Click trên Giao diện Web
1. Mở ứng dụng Web Streamlit.
2. Tại thanh điều khiển hàng trên, nhấp nút **"🚀 NẠP DỮ LIỆU MẪU"** (hoặc nhấp nút **"🚀 NẠP MẪU F3.6"** ở thanh công cụ đáy).
3. Hệ thống sẽ tự động đọc `sample_data/mau_chuan_thuy_san.json`, điền đầy đủ 8 tab dữ liệu, kích hoạt đối soát IUU và chuyển sang chế độ làm việc Bước 3.

#### Cách 2: Tải lên qua Bộ Nạp Bản Nháp JSON
1. Mở mục **"📂 NẠP BẢN NHÁP JSON ĐÃ LƯU"** trên giao diện chính.
2. Kéo thả tệp `sample_data/mau_chuan_thuy_san.json`.
3. Hệ thống sẽ giải mã và khôi phục toàn bộ hồ sơ trong vòng 1 giây.

#### Cách 3: Nạp trực tiếp bằng mã lệnh Python
```python
import json
from services.export_service import ExportService
from rfmo_checker import RFMOChecker

# Đọc tệp dữ liệu mẫu
with open("sample_data/mau_chuan_thuy_san.json", "r", encoding="utf-8") as f:
    dossier = json.load(f)

# 1. Thẩm định IUU
checker = RFMOChecker()
report, vessel_results = checker.verify_ho_so(dossier)
print(f"IUU Violation: {report['has_violation']}")  # False

# 2. Xuất file Word Mẫu 22.KT
docx_bytes = ExportService.export_mau22(dossier)
print(f"Generated Word size: {len(docx_bytes)} bytes")
```

---

### 4. KỊCH BẢN THẨM ĐỊNH MẪU (E2E WALKTHROUGH)

1. **Bước 1**: Nhấn "🚀 NẠP DỮ LIỆU MẪU" $\rightarrow$ Kiểm tra thông tin doanh nghiệp tại Tab 1 và sản phẩm tại Tab 2.
2. **Bước 2**: Chuyển sang Tab 8 $\rightarrow$ Xác nhận trạng thái `🟢 AN TOÀN TUYỆT ĐỐI`, 2/2 tàu sạch IUU.
3. **Bước 3**: Nhấn nút **"📥 TẢI BÁO CÁO THẨM ĐỊNH IUU"** tại Tab 8 $\rightarrow$ Lưu tệp văn bản đối soát chi tiết.
4. **Bước 4**: Nhấn nút **"📄 XUẤT WORD"** ở thanh công cụ đáy $\rightarrow$ Nhận tệp `Mau22_KT_*.docx` khổ ngang hoàn chỉnh với 6 bảng biểu và lề 1.5cm.
5. **Bước 5**: Nhấn nút **"💾 LƯU CSDL"** $\rightarrow$ Hồ sơ được lưu trữ an toàn vào SQLite `dulieu_tau.db`.
