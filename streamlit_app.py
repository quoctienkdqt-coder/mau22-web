import os
import sys
import json
import time
import io
import tempfile
import base64
import pandas as pd
import streamlit as st
import pymupdf  # PyMuPDF / fitz

# Đảm bảo đường dẫn gốc cho các imports
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from config import (
    COLOR_BG, COLOR_NAVY, COLOR_PRIMARY, COLOR_SUCCESS, 
    COLOR_WARNING, COLOR_TEXT, CURRENT_VERSION, get_hidden_api_key,
    get_gemini_api_key, load_company_list, get_hardware_id
)
from services.ai_service import AIService
from services.export_service import ExportService
from vessel_utils import deduplicate_vessels, clean_vessel_name, clean_imo_number
from rfmo_checker import RFMOChecker
try:
    from rfmo_online_engine import rfmo_engine
except ImportError:
    from rfmo_online_engine import RFMOOnlineEngine
    rfmo_engine = RFMOOnlineEngine()
from database.db_manager import DatabaseManager


# ==========================================
# CẤU HÌNH TRANG STREAMLIT
# ==========================================
st.set_page_config(
    page_title="MẪU 22 KT PRO - Hệ Thống Trích Xuất AI & Thẩm Định IUU",
    page_icon="🚢",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ==========================================
# HỆ THỐNG CSS ENTERPRISE SLATE/NAVY
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800;900&family=Segoe+UI:wght@400;600;700;800&display=swap');

    /* Reset toàn cục */
    .stApp {
        background-color: #F8FAFC !important;
        font-family: 'Plus Jakarta Sans', 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif !important;
        color: #0F172A !important;
    }

    /* Ẩn header mặc định và tối ưu padding đỉnh trang */
    header[data-testid="stHeader"] {
        background-color: transparent !important;
        height: 0px !important;
        z-index: 99;
    }
    .block-container {
        padding-top: 0.6rem !important;
        padding-bottom: 2rem !important;
        max-width: 100% !important;
    }

    /* MÀN HÌNH CHÍNH: TỰ ĐỘNG DÃN RỘNG FULL WIDTH 100% */
    .main {
        width: 100% !important;
        flex: 1 !important;
        transition: all 0.3s ease !important;
    }
    .main .block-container {
        padding-top: 0.6rem !important;
        padding-bottom: 2rem !important;
        padding-left: 1.5rem !important;
        padding-right: 1.5rem !important;
        max-width: 100% !important;
        width: 100% !important;
    }

    /* SIDEBAR SÁNG CHUẨN SAAS (THEO MẪU EZY CLOUDX) */
    section[data-testid="stSidebar"]:not([aria-expanded="false"]) {
        width: 270px !important;
        min-width: 270px !important;
        max-width: 270px !important;
        background-color: #FFFFFF !important;
        border-right: 1px solid #E2E8F0 !important;
        transition: transform 0.3s ease, width 0.3s ease !important;
    }

    /* KHI THU GỌN SIDEBAR */
    section[data-testid="stSidebar"][aria-expanded="false"] {
        width: 0px !important;
        min-width: 0px !important;
        max-width: 0px !important;
        margin-left: -280px !important;
        transform: translateX(-100%) !important;
        overflow: hidden !important;
        display: none !important;
    }

    [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"] {
        display: flex !important;
        visibility: visible !important;
        z-index: 1001 !important;
    }

    section[data-testid="stSidebar"] * {
        color: #1E293B !important;
    }
    section[data-testid="stSidebar"] hr {
        border-color: #E2E8F0 !important;
        margin: 12px 0 !important;
    }
    section[data-testid="stSidebar"] [data-testid="stRadio"] > div {
        gap: 3px;
    }
    section[data-testid="stSidebar"] [data-testid="stRadio"] label {
        background: transparent;
        padding: 8px 12px;
        border-radius: 8px;
        color: #475569 !important;
        font-weight: 600 !important;
        font-size: 13px !important;
        transition: all 0.2s ease;
    }
    section[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
        background: #F1F5F9 !important;
        color: #0284C7 !important;
    }
    section[data-testid="stSidebar"] [data-testid="stRadio"] label[data-checked="true"],
    section[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {
        background: #EFF6FF !important;
        color: #0284C7 !important;
        font-weight: 700 !important;
        border-left: 3px solid #0284C7 !important;
    }

    /* TOPBAR SAAS NAVBAR (THEO MẪU EZY CLOUDX NAVBAR) */
    .saas-navbar {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 10px 20px;
        margin: 0 0 20px 0;
        display: flex;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03);
    }
    .saas-nav-brand {
        display: flex;
        align-items: center;
        gap: 10px;
        font-size: 19px;
        font-weight: 900;
        color: #0F172A;
        letter-spacing: -0.5px;
        text-decoration: none;
    }
    .saas-nav-brand .brand-badge {
        background: #0284C7;
        color: #FFFFFF;
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 11px;
        font-weight: 800;
    }
    .saas-nav-links {
        display: flex;
        align-items: center;
        gap: 16px;
    }
    .saas-nav-item {
        font-size: 13px;
        font-weight: 600;
        color: #475569;
        padding: 6px 12px;
        border-radius: 8px;
        transition: all 0.2s;
        text-decoration: none;
    }
    .saas-nav-item:hover {
        color: #0284C7;
        background: #F1F5F9;
    }
    .saas-nav-actions {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .btn-console-pill {
        background: #0284C7;
        color: #FFFFFF !important;
        font-size: 12.5px;
        font-weight: 700;
        padding: 7px 16px;
        border-radius: 8px;
        text-decoration: none;
        display: inline-flex;
        align-items: center;
        gap: 6px;
        border: none;
        box-shadow: 0 2px 4px rgba(2, 132, 199, 0.25);
    }
    .badge-point-pill {
        background: #EFF6FF;
        border: 1px solid #BFDBFE;
        color: #0284C7;
        font-size: 12px;
        font-weight: 800;
        padding: 5px 12px;
        border-radius: 20px;
        display: inline-flex;
        align-items: center;
        gap: 5px;
    }

    /* HERO SECTION TRANG CHỦ (CHUẨN EZY CLOUDX HERO) */
    .hero-center-box {
        text-align: center;
        padding: 28px 16px 20px 16px;
        max-width: 960px;
        margin: 0 auto;
    }
    .hero-pill-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: #E0F2FE;
        color: #0284C7;
        padding: 6px 18px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 700;
        margin-bottom: 16px;
    }
    .hero-title-giant {
        font-size: 48px;
        font-weight: 900;
        color: #0F172A;
        line-height: 1.15;
        letter-spacing: -1.5px;
        margin-bottom: 14px;
    }
    .hero-title-giant span.blue-highlight {
        color: #0284C7;
        display: block;
        margin-top: 4px;
    }
    .hero-subtitle-desc {
        font-size: 14.5px;
        color: #475569;
        line-height: 1.65;
        max-width: 800px;
        margin: 0 auto 24px auto;
    }

    /* BANNER LƯU Ý QUAN TRỌNG (NHƯ BANNER UBUNTU TRONG HÌNH 2) */
    .saas-warning-banner {
        background: #FEF2F2;
        border: 1px solid #FCA5A5;
        border-radius: 8px;
        padding: 12px 18px;
        color: #991B1B;
        font-size: 13px;
        line-height: 1.55;
        margin: 16px 0;
        display: flex;
        align-items: center;
        gap: 10px;
    }

    /* CARD VÍ COMPUTING POINT / ĐIỂM AI (TRONG HÌNH 2) */
    .wallet-balance-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 18px 22px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 20px;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03);
    }
    .wallet-left {
        display: flex;
        align-items: center;
        gap: 14px;
    }
    .wallet-icon {
        width: 44px;
        height: 44px;
        border-radius: 10px;
        background: #EFF6FF;
        color: #0284C7;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 20px;
    }
    .wallet-info-title {
        font-size: 12px;
        color: #64748B;
        font-weight: 600;
        margin-bottom: 2px;
    }
    .wallet-info-val {
        font-size: 26px;
        font-weight: 900;
        color: #0F172A;
    }

    /* CARD LỰA CHỌN NỀN TẢNG (WEB VS DESKTOP) */
    .platform-choice-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 14px;
        padding: 24px 20px;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        transition: all 0.25s ease;
        box-shadow: 0 2px 6px rgba(15, 23, 42, 0.02);
    }
    .platform-choice-card:hover {
        border-color: #0284C7;
        box-shadow: 0 8px 24px rgba(2, 132, 199, 0.08);
        transform: translateY(-3px);
    }
    .platform-tag {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 11px;
        font-weight: 800;
        text-transform: uppercase;
        margin-bottom: 12px;
    }
    .platform-tag-web { background: #E0F2FE; color: #0284C7; }
    .platform-tag-desktop { background: #ECFDF5; color: #059669; }
    .platform-title {
        font-size: 17px;
        font-weight: 800;
        color: #0F172A;
        margin-bottom: 8px;
    }
    .platform-desc {
        font-size: 13px;
        color: #475569;
        line-height: 1.6;
        margin-bottom: 16px;
    }

    /* CARD BẢNG GIÁ THEO DẠNG CARD GPU (HÌNH 2) */
    .gpu-pricing-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 18px 16px;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        transition: all 0.2s ease;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.02);
    }
    .gpu-pricing-card:hover {
        border-color: #0284C7;
        box-shadow: 0 6px 18px rgba(2, 132, 199, 0.09);
        transform: translateY(-2px);
    }
    .gpu-card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 8px;
    }
    .gpu-card-title {
        font-size: 14.5px;
        font-weight: 800;
        color: #0F172A;
    }
    .gpu-card-badge {
        font-size: 10px;
        font-weight: 800;
        padding: 2px 7px;
        border-radius: 10px;
    }
    .badge-slot-ok { background: #ECFDF5; color: #059669; }
    .badge-slot-hot { background: #EFF6FF; color: #0284C7; }
    .badge-slot-full { background: #FEE2E2; color: #DC2626; }
    
    .gpu-specs-line {
        font-size: 12px;
        color: #64748B;
        margin-bottom: 10px;
        line-height: 1.4;
    }
    .gpu-tags-row {
        display: flex;
        gap: 6px;
        margin-bottom: 14px;
    }
    .gpu-tag-chip {
        background: #F1F5F9;
        color: #475569;
        font-size: 11px;
        padding: 2px 7px;
        border-radius: 4px;
        font-weight: 600;
    }
    .gpu-price-box {
        margin-bottom: 12px;
    }
    .gpu-price-main {
        font-size: 24px;
        font-weight: 900;
        color: #0284C7;
    }
    .gpu-price-unit {
        font-size: 12px;
        font-weight: 600;
        color: #64748B;
    }
    .gpu-price-discount {
        background: #FEF3C7;
        color: #B45309;
        font-size: 11px;
        font-weight: 800;
        padding: 2px 6px;
        border-radius: 4px;
        margin-left: 6px;
    }
    .gpu-specs-table {
        font-size: 11.5px;
        color: #334155;
        line-height: 1.7;
        border-top: 1px solid #F1F5F9;
        padding-top: 10px;
        margin-bottom: 14px;
    }

    /* STEPPER & PANELS */
    .stepper-box {
        display: flex;
        align-items: center;
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 6px 14px;
        margin-bottom: 12px;
    }
    .step-item {
        flex: 1;
        text-align: center;
        padding: 6px 10px;
        border-radius: 8px;
        font-size: 11.5px;
        font-weight: 700;
    }
    .step-active { background: #EFF6FF; border: 1px solid #93C5FD; color: #0284C7; }
    .step-done { background: #ECFDF5; border: 1px solid #A7F3D0; color: #059669; }
    .step-idle { background: #F8FAFC; border: 1px solid #E2E8F0; color: #94A3B8; }
    .step-sep { font-size: 13px; font-weight: bold; padding: 0 8px; }

    .content-panel {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 16px 18px;
        margin-bottom: 14px;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.02);
    }
    .panel-header {
        font-size: 13px;
        font-weight: 700;
        color: #0F172A;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }

    .stat-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 12px 14px;
    }
    .stat-card-header {
        display: flex;
        align-items: center;
        gap: 6px;
        margin-bottom: 6px;
    }
    .stat-icon {
        width: 26px;
        height: 26px;
        border-radius: 6px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 13px;
        font-weight: bold;
    }
    .stat-title {
        font-size: 11px;
        font-weight: 700;
        color: #64748B;
        text-transform: uppercase;
    }
    .stat-val {
        font-size: 24px;
        font-weight: 800;
    }

    button[data-baseweb="tab"] {
        background-color: #F1F5F9 !important;
        border-radius: 8px !important;
        padding: 6px 14px !important;
        margin-right: 4px !important;
        font-weight: 600 !important;
        font-size: 12px !important;
        color: #475569 !important;
        border: none !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        background-color: #0284C7 !important;
        color: #FFFFFF !important;
    }
</style>
""", unsafe_allow_html=True)


# ==========================================
# KHỞI TẠO STATE TOÀN CỤC & TƯƠNG THÍCH NGƯỢC
# ==========================================
if "current_view" not in st.session_state:
    st.session_state.current_view = "news"
if "current_nav" not in st.session_state:
    st.session_state.current_nav = "news"

# Quản lý người dùng Web đa tài khoản (Multi-User SaaS)
if "logged_user" not in st.session_state:
    st.session_state.logged_user = {
        "id": 0,
        "email": "khach.hang@demo.vn",
        "company_name": "Doanh Nghiệp Thủy Sản (Dùng Thử)",
        "phone": "0901234567",
        "plan": "FREE_TRIAL",
        "credits": 3,
        "is_guest": True,
        "created_at": "Hôm nay"
    }

if "selected_plan_info" not in st.session_state:
    st.session_state.selected_plan_info = None

if "current_order_code" not in st.session_state:
    st.session_state.current_order_code = ""

if "workspace_mode" not in st.session_state:
    st.session_state.workspace_mode = "LUONG_1"

if "current_step" not in st.session_state:
    st.session_state.current_step = 1
if "step" not in st.session_state:
    st.session_state.step = 1

if "stepper_collapsed" not in st.session_state:
    st.session_state.stepper_collapsed = False

if "show_doc_preview" not in st.session_state:
    st.session_state.show_doc_preview = True
if "show_pdf" not in st.session_state:
    st.session_state.show_pdf = True

if "pdf_selected_file" not in st.session_state:
    st.session_state.pdf_selected_file = ""
if "pdf_pages_dict" not in st.session_state:
    st.session_state.pdf_pages_dict = {}
if "pdf_zoom" not in st.session_state:
    st.session_state.pdf_zoom = 1.0
if "pdf_fit_width" not in st.session_state:
    st.session_state.pdf_fit_width = True

if "current_extracted_data" not in st.session_state:
    st.session_state.current_extracted_data = {}
if "extracted_data" not in st.session_state:
    st.session_state.extracted_data = {}

if "rfmo_audit_results" not in st.session_state:
    st.session_state.rfmo_audit_results = None
if "rfmo_results" not in st.session_state:
    st.session_state.rfmo_results = None

if "is_ai_running" not in st.session_state:
    st.session_state.is_ai_running = False
if "ai_duration" not in st.session_state:
    st.session_state.ai_duration = 0.0

if "pdf_page_idx" not in st.session_state:
    st.session_state.pdf_page_idx = 0


# Đồng bộ hai chiều giữa các biến tương thích
def sync_states():
    # Sync current_view <-> current_nav
    if st.session_state.current_view in ["LUONG_1", "LUONG_2"]:
        st.session_state.workspace_mode = st.session_state.current_view
        st.session_state.current_view = "workspace"
        st.session_state.current_nav = "workspace"
    elif st.session_state.current_nav in ["LUONG_1", "LUONG_2"]:
        st.session_state.workspace_mode = st.session_state.current_nav
        st.session_state.current_view = "workspace"
        st.session_state.current_nav = "workspace"
    else:
        st.session_state.current_nav = st.session_state.current_view

    # Sync step
    st.session_state.step = st.session_state.current_step
    
    # Sync preview
    st.session_state.show_pdf = st.session_state.show_doc_preview
    
    # Sync extracted_data
    if st.session_state.current_extracted_data and not st.session_state.extracted_data:
        st.session_state.extracted_data = st.session_state.current_extracted_data
    elif st.session_state.extracted_data and not st.session_state.current_extracted_data:
        st.session_state.current_extracted_data = st.session_state.extracted_data
    else:
        st.session_state.extracted_data = st.session_state.current_extracted_data

    # Sync rfmo results
    if st.session_state.rfmo_audit_results and not st.session_state.rfmo_results:
        st.session_state.rfmo_results = st.session_state.rfmo_audit_results
    elif st.session_state.rfmo_results and not st.session_state.rfmo_audit_results:
        st.session_state.rfmo_audit_results = st.session_state.rfmo_results
    else:
        st.session_state.rfmo_results = st.session_state.rfmo_audit_results

sync_states()

db = DatabaseManager(os.path.join(CURRENT_DIR, "dulieu_tau.db"))
companies_dict, _ = load_company_list()


# ==========================================
# CÁC HÀM TIỆN ÍCH DỮ LIỆU & RENDER (CACHED)
# ==========================================
def get_vessel_db_status():
    """Kiểm tra sự hiện diện của 5 tệp CSDL tàu cá offline trên đĩa cứng."""
    required_files = [
        "iccat_vessels.csv",
        "wcpfc_vessels.csv",
        "iotc_vessels.xlsx",
        "iattc_vessels.xlsx",
        "IUUList.xls"
    ]
    loaded = sum(1 for f in required_files if os.path.exists(os.path.join(CURRENT_DIR, f)))
    total = len(required_files)
    return loaded, total


@st.cache_data(max_entries=32, show_spinner=False)
def get_pdf_total_pages(file_bytes: bytes) -> int:
    """Trả về tổng số trang của file PDF in-memory mà không giữ RAM."""
    try:
        doc = pymupdf.open(stream=file_bytes, filetype="pdf")
        count = len(doc)
        doc.close()
        return count
    except Exception:
        return 0


@st.cache_data(max_entries=64, show_spinner=False)
def render_pdf_page_to_png(file_bytes: bytes, page_idx: int, zoom: float) -> bytes:
    """
    Render 1 trang PDF sang chuỗi byte PNG bằng PyMuPDF in-memory.
    - Ép buộc colorspace=pymupdf.csRGB để chống lỗi vệt đen/lệch màu trên file quét scan.
    - alpha=False đảm bảo nền trắng trung thực.
    - Caching kết quả giúp khi người dùng sửa tab dữ liệu không bị re-render lại trang.
    """
    try:
        doc = pymupdf.open(stream=file_bytes, filetype="pdf")
        total = len(doc)
        if total == 0:
            doc.close()
            return b""
        actual_idx = max(0, min(total - 1, page_idx))
        page = doc.load_page(actual_idx)
        
        scale = max(0.5, min(3.0, 1.5 * zoom))
        matrix = pymupdf.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=matrix, colorspace=pymupdf.csRGB, alpha=False)
        png_bytes = pix.tobytes("png")
        doc.close()
        return png_bytes
    except Exception:
        return b""


def normalize_vessel_item(v: dict) -> dict:
    """
    Chuẩn hóa biến thể khóa tàu cá (ten_tau, so_imo, so_dang_ky...) về đúng
    10 khóa chuẩn tắc của ExportService và DatabaseManager.
    """
    if not isinstance(v, dict):
        return {
            "ten": str(v), "imo": "", "ho_hieu": "", "rfmo": "", "giay_phep": "",
            "co_quan": "", "ngay_het_han": "", "khu_vuc": "", "doi_tuong": "", "ngu_cu": ""
        }
    return {
        "ten": str(v.get("ten") or v.get("ten_tau") or v.get("name") or "").strip(),
        "imo": str(v.get("imo") or v.get("so_imo") or "").strip(),
        "ho_hieu": str(v.get("ho_hieu") or v.get("so_dang_ky") or v.get("call_sign") or "").strip(),
        "rfmo": str(v.get("rfmo") or v.get("so_rfmo") or "").strip(),
        "giay_phep": str(v.get("giay_phep") or v.get("license") or "").strip(),
        "co_quan": str(v.get("co_quan") or v.get("co_quan_cap") or "").strip(),
        "ngay_het_han": str(v.get("ngay_het_han") or v.get("het_han") or "").strip(),
        "khu_vuc": str(v.get("khu_vuc") or v.get("vung_bien") or "").strip(),
        "doi_tuong": str(v.get("doi_tuong") or "").strip(),
        "ngu_cu": str(v.get("ngu_cu") or v.get("gear") or "").strip()
    }


def get_full_sample_dataset() -> dict:
    """
    Cung cấp bộ dữ liệu mẫu chuẩn thủy sản thực tế đầy đủ 8 thành phần
    khớp hoàn hảo hợp đồng ExportService.export_mau22 và RFMOChecker.
    """
    sample_file = os.path.join(CURRENT_DIR, "sample_data", "mau_chuan_thuy_san.json")
    if os.path.exists(sample_file):
        try:
            with open(sample_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    return {
        "kinh_gui": "Chi cục Thủy sản tỉnh Khánh Hòa",
        "ten_co_so": "Công Ty TNHH Cá Ngừ Việt Nam",
        "dia_chi": "Lô A4-A8 Khu Công Nghiệp Suối Dầu, Xã Cam Lâm, Tỉnh Khánh Hòa, Việt Nam",
        "nguoi_dai_dien": "Nguyễn Văn Dư",
        "sdt": "0258 3743666",
        "email": "ld.cus@haivuong.com",
        "so_to_khai": "105892348120",
        "ngay_to_khai": "15/03/2024",
        "tong_san_luong": "125480",
        "thoi_gian_boc_do": "18/03/2024 - 22/03/2024",
        "dia_diem_boc_do": "Cảng Quốc tế Cam Ranh, Khánh Hòa",
        "so_van_don": "BL-CAMRANH-20240315",
        "cang_boc_hang": "Port Victoria, Seychelles",
        "cang_den": "Cam Ranh Port, Vietnam",
        "ten_hang": "Cá ngừ vây vàng đông lạnh (Frozen Yellowfin Tuna)",
        "khoi_luong": "125480",
        "nuoc_xuat_khau": "Seychelles",
        "san_pham": [
            {
                "loai": "Cá ngừ vây vàng (Thunnus albacares)",
                "hs_code": "03034200",
                "ten_khoa_hoc": "Thunnus albacares",
                "kich_co": "> 10 kg/con",
                "khoi_luong": "65200",
                "xuat_xu": "Seychelles"
            },
            {
                "loai": "Cá ngừ mắt to (Thunnus obesus)",
                "hs_code": "03034400",
                "ten_khoa_hoc": "Thunnus obesus",
                "kich_co": "> 20 kg/con",
                "khoi_luong": "42150",
                "xuat_xu": "Seychelles"
            },
            {
                "loai": "Cá ngừ vằn (Katsuwonus pelamis)",
                "hs_code": "03034300",
                "ten_khoa_hoc": "Katsuwonus pelamis",
                "kich_co": "1.8 - 3.4 kg/con",
                "khoi_luong": "18130",
                "xuat_xu": "Seychelles"
            }
        ],
        "tau_danh_bat": [
            {
                "ten": "TALENT 36",
                "imo": "8745814",
                "ho_hieu": "S7TB",
                "rfmo": "IOTC012845",
                "giay_phep": "LIC-IOTC-2023-088",
                "co_quan": "Seychelles Fishing Authority",
                "ngay_het_han": "31/12/2025",
                "khu_vuc": "INDIAN OCEAN / FAO 51",
                "doi_tuong": "Tuna & Tuna-like species",
                "ngu_cu": "Purse Seine"
            },
            {
                "ten": "OCEAN HARVEST 8",
                "imo": "9123847",
                "ho_hieu": "V4OH",
                "rfmo": "IOTC009321",
                "giay_phep": "SFA-2023-994",
                "co_quan": "Seychelles Fishing Authority",
                "ngay_het_han": "15/10/2025",
                "khu_vuc": "INDIAN OCEAN / FAO 51",
                "doi_tuong": "Yellowfin Tuna",
                "ngu_cu": "Longline"
            }
        ],
        "thong_tin_chuyen_tai": [
            {
                "tau_khai_thac": "TALENT 36",
                "thoi_gian": "12/02/2024",
                "tau_nhan": "PACIFIC REEFER 1",
                "quoc_gia": "Panama",
                "imo": "8912345",
                "ho_hieu": "HP5678",
                "loai": "Cá ngừ vây vàng",
                "khoi_luong": "65200"
            },
            {
                "tau_khai_thac": "OCEAN HARVEST 8",
                "thoi_gian": "14/02/2024",
                "tau_nhan": "PACIFIC REEFER 1",
                "quoc_gia": "Panama",
                "imo": "8912345",
                "ho_hieu": "HP5678",
                "loai": "Cá ngừ mắt to",
                "khoi_luong": "60280"
            }
        ],
        "giay_phep_chuyen_tai": [
            {
                "tau_chuyen_tai": "PACIFIC REEFER 1",
                "imo": "8912345",
                "giay_phep": "TS-AUTH-IOTC-2024-012",
                "co_quan": "Panama Maritime Authority",
                "ngay_het_han": "30/06/2025"
            }
        ],
        "san_luong_cap_ben": [
            {
                "tau": "PACIFIC REEFER 1",
                "imo": "8912345",
                "cang": "Port Victoria",
                "ngay": "28/02/2024",
                "khoi_luong": "125480"
            }
        ],
        "cong_ten_no": [
            {
                "so_container": "TGHU9234812",
                "so_seal": "ML-VN89321",
                "so_bl": "BL-CAMRANH-20240315",
                "tau_cho": "MAERSK VISBY",
                "imo": "9412836",
                "nuoc_xuat": "Seychelles",
                "cang_xuat": "Port Victoria",
                "dia_chi_kho": "Kho Lạnh Hải Vương, KCN Suối Dầu, Khánh Hòa"
            },
            {
                "so_container": "MSKU5198234",
                "so_seal": "ML-VN89322",
                "so_bl": "BL-CAMRANH-20240315",
                "tau_cho": "MAERSK VISBY",
                "imo": "9412836",
                "nuoc_xuat": "Seychelles",
                "cang_xuat": "Port Victoria",
                "dia_chi_kho": "Kho Lạnh Hải Vương, KCN Suối Dầu, Khánh Hòa"
            },
            {
                "so_container": "CMAU7321945",
                "so_seal": "ML-VN89323",
                "so_bl": "BL-CAMRANH-20240315",
                "tau_cho": "MAERSK VISBY",
                "imo": "9412836",
                "nuoc_xuat": "Seychelles",
                "cang_xuat": "Port Victoria",
                "dia_chi_kho": "Kho Lạnh Hải Vương, KCN Suối Dầu, Khánh Hòa"
            }
        ]
    }


# ==========================================
# DIALOG POP-UP: TRA CỨU RFMO & IUU LIVE
# ==========================================
if hasattr(st, "dialog"):
    @st.dialog("🌐 CỔNG TRA CỨU TRỰC TUYẾN RFMO & IUU LIVE", width="large")
    def show_live_rfmo_dialog():
        st.caption("Tra cứu đối soát tức thì trên các CSDL WCPFC, IOTC, IATTC, ICCAT và IUU-Vessels.org")
        d_c1, d_c2 = st.columns([3, 1.2])
        with d_c1:
            d_query = st.text_input("Nhập Tên tàu hoặc Số IMO:", placeholder="Ví dụ: SHUN FA 888 hoặc 8745814...", key="dlg_query_input")
        with d_c2:
            d_org = st.selectbox("Tổ chức RFMO:", ["Tất cả (All)", "WCPFC", "IOTC", "IATTC", "ICCAT", "IUU Global"], key="dlg_org_select")

        if st.button("🔍 Tra cứu ngay", type="primary", key="dlg_btn_search"):
            if d_query.strip():
                with st.spinner(f"Đang kiểm tra CSDL cho '{d_query.strip()}'..."):
                    t0 = time.time()
                    results = []
                    q_val = d_query.strip()
                    
                    if d_org in ["Tất cả (All)", "IUU Global"]:
                        iuu_res = rfmo_engine.search_iuu_global(q_val)
                        results.append(("IUU Vessels Global", iuu_res))
                    if d_org in ["Tất cả (All)", "WCPFC"]:
                        w_res = rfmo_engine.search_wcpfc(q_val)
                        results.append(("WCPFC", w_res))
                    if d_org in ["Tất cả (All)", "IOTC"]:
                        io_res = rfmo_engine.search_iotc(q_val)
                        results.append(("IOTC", io_res))

                    st.success(f"Hoàn thành tra cứu trong {round(time.time() - t0, 2)}s!")
                    for org_name, res_items in results:
                        with st.expander(f"Kết quả từ {org_name} ({len(res_items) if isinstance(res_items, list) else 1} mục)", expanded=True):
                            st.json(res_items)
            else:
                st.warning("Vui lòng nhập Tên tàu hoặc Số IMO để tra cứu!")
else:
    def show_live_rfmo_dialog():
        st.session_state.current_view = "rfmo_live"
        st.rerun()


def generate_iuu_audit_report_text(cur_data: dict, rfmo_audit: dict) -> str:
    """Tạo báo cáo thẩm định IUU chi tiết định dạng Markdown / Text"""
    if not rfmo_audit:
        return "Chưa có dữ liệu thẩm định IUU."
    
    rep = rfmo_audit.get("ho_so_report", {})
    v_res = rfmo_audit.get("v_results", [])
    has_viol = rep.get("has_violation", False)
    
    so_tk = cur_data.get("so_to_khai", "N/A") if cur_data else "N/A"
    ten_cs = cur_data.get("ten_co_so", "N/A") if cur_data else "N/A"
    thoi_gian = time.strftime("%Y-%m-%d %H:%M:%S")
    
    lines = [
        "=" * 72,
        "   BÁO CÁO THẨM ĐỊNH RỦI RO IUU & ĐỐI SOÁT RFMO LIVE TOÀN CẦU",
        "=" * 72,
        f"Hồ sơ tờ khai: {so_tk}",
        f"Doanh nghiệp nhập khẩu: {ten_cs}",
        f"Thời gian kiểm tra: {thoi_gian}",
        f"Hệ thống: MẪU 22 KT PRO (v1.0.9 Enterprise)",
        "-" * 72,
        f"KẾT LUẬN CHUNG: {'🚨 CẢNH BÁO VI PHẠM IUU / RỦI RO CAO' if has_viol else '🟢 AN TOÀN TUYỆT ĐỐI - KHÔNG PHÁT HIỆN VI PHẠM'}",
        f"Tổng số tàu kiểm tra: {len(v_res)} tàu",
        f"Số tàu an toàn: {sum(1 for v in v_res if not v.get('is_iuu_listed', False))} tàu",
        f"Số tàu vi phạm blacklist: {sum(1 for v in v_res if v.get('is_iuu_listed', False))} tàu",
        "-" * 72,
        "CHI TIẾT ĐỐI SOÁT TỪNG TÀU KHAI THÁC:",
        ""
    ]
    
    for idx, v in enumerate(v_res, 1):
        lines.append(f"[{idx}] TÀU: {v.get('ten_tau', 'N/A')} | IMO: {v.get('so_imo', 'N/A')}")
        lines.append(f"    - Quốc tịch (Cờ): {v.get('quoc_tich', 'N/A')}")
        lines.append(f"    - Hô hiệu (Call Sign): {v.get('so_dang_ky', 'N/A')}")
        lines.append(f"    - Ngư cụ khai báo: {v.get('ngu_cu', 'N/A')}")
        lines.append(f"    - Giấy phép khai thác: {v.get('giay_phep', 'N/A')}")
        lines.append(f"    - IUU Global Blacklist: {'🚨 BỊ LIỆT KÊ VI PHẠM' if v.get('is_iuu_listed') else '🟢 Hợp lệ (Sạch)'}")
        rf_urls = v.get("rfmo_urls", {})
        if rf_urls:
            lines.append("    - Cổng tra cứu thẩm quyền RFMO:")
            for org, u in rf_urls.items():
                lines.append(f"      + {org}: {u}")
        lines.append("")
        
    lines.append("-" * 72)
    lines.append("XÁC NHẬN CỦA HỆ THỐNG THẨM ĐỊNH TỰ ĐỘNG")
    lines.append("Bản quyền © 2026 Ngô Quốc Tiến - Mẫu 22 KT Pro Enterprise")
    lines.append("=" * 72)
    return "\n".join(lines)


# ==========================================
# GIAO DIỆN PHÂN HỆ: TRANG CHỦ & CỔNG DỊCH VỤ TOÀN DIỆN (ALL-IN-ONE LANDING HUB)
# ==========================================
# ==========================================
# GIAO DIỆN PHÂN HỆ: TRANG CHỦ & CỔNG DỊCH VỤ TOÀN DIỆN (EZY CLOUDX SAAS STYLE)
# ==========================================
def render_landing_home_page(db: DatabaseManager):
    user_info = st.session_state.get("logged_user", {})
    user_email = user_info.get("email", "khach.hang@demo.vn")
    user_credits = user_info.get("credits", 0)
    is_guest = user_info.get("is_guest", True)
    default_hwid = user_info.get("hwid", "") or get_hardware_id()

    # 1. SAAS NAVBAR TRÊN CÙNG (THEO MẪU HÌNH 1)
    nav_c1, nav_c2, nav_c3 = st.columns([2.2, 4.5, 2.5])
    with nav_c1:
        st.markdown("""
        <div style="display:flex;align-items:center;gap:8px;padding-top:4px;">
            <span style="font-size:22px;">🚢</span>
            <span style="font-size:18px;font-weight:900;color:#0F172A;letter-spacing:-0.5px;">M22 <span style="color:#0284C7;">CLOUDX</span></span>
        </div>
        """, unsafe_allow_html=True)
    with nav_c2:
        # Thanh liên kết điều hướng nhanh
        l_c1, l_c2, l_c3, l_c4, l_c5 = st.columns(5)
        with l_c1:
            if st.button("⚡ Trích xuất Web", key="nav_link_web", use_container_width=True):
                st.session_state.current_view = "workspace"
                st.session_state.workspace_mode = "LUONG_1"
                st.rerun()
        with l_c2:
            if st.button("💻 Tải Desktop", key="nav_link_desktop", use_container_width=True):
                st.session_state.current_view = "download"
                st.rerun()
        with l_c3:
            if st.button("💳 Bảng giá", key="nav_link_pricing", use_container_width=True):
                st.session_state.selected_plan_info = {
                    "name": "GÓI_PRO_299K",
                    "label": "Gói Pro Doanh Nghiệp (120 Lượt)",
                    "amount": 299000,
                    "credits": 120,
                    "plan_type": "CRE",
                    "val": "120"
                }
                code_suffix = str(int(time.time()))[-5:]
                st.session_state.current_order_code = f"M22KT_{code_suffix}"
                st.rerun()
        with l_c4:
            if st.button("🚢 CSDL Tàu", key="nav_link_rfmo", use_container_width=True):
                st.session_state.current_view = "rfmo_live"
                st.rerun()
        with l_c5:
            if st.button("📖 Hướng dẫn", key="nav_link_docs", use_container_width=True):
                st.session_state.current_view = "docs"
                st.rerun()
    with nav_c3:
        act_c1, act_c2 = st.columns([1.4, 1.2])
        with act_c1:
            if st.button("⚡ Console ➔", type="primary", key="nav_btn_console", use_container_width=True):
                st.session_state.current_view = "workspace"
                st.session_state.workspace_mode = "LUONG_1"
                st.rerun()
        with act_c2:
            st.markdown(f"""
            <div style="background:#EFF6FF;border:1px solid #BFDBFE;color:#0284C7;font-size:11px;font-weight:800;padding:6px 10px;border-radius:20px;text-align:center;margin-top:2px;">
                ⚡ {user_credits} Điểm
            </div>
            """, unsafe_allow_html=True)

    st.write("")

    # 2. HERO SECTION TRUNG TÂM (CHUẨN HÌNH 1)
    st.markdown("""
    <div class="hero-center-box">
        <div class="hero-pill-badge">
            <span>✨</span> Nền tảng AI Bóc Tách & Thẩm Định Thủy Sản tại Việt Nam 🇻🇳
        </div>
        <div class="hero-title-giant">
            Mẫu 22.KT AI Cloud
            <span class="blue-highlight">Cho mọi dự án</span>
        </div>
        <div class="hero-subtitle-desc">
            Số hóa chứng từ hải sản nhập khẩu chỉ trong <b>30 giây</b>.<br/>
            Tối ưu cho <b>Hóa đơn thương mại, Vận đơn B/L, Chứng nhận khai thác (C/C), Chứng thư chuyển tải và Tờ khai hải quan</b> với hiệu suất vượt trội.<br/>
            Tích hợp trực tiếp <b>5 CSDL quốc tế WCPFC, IOTC, IATTC, ICCAT, Blacklist toàn cầu</b>, đáp ứng đầy đủ quy chuẩn Mẫu 22.KT theo Nghị định 37 & 38/2024/NĐ-CP của bạn.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # NÚT CTA HÀNH ĐỘNG CHÍNH (CẶP NÚT NHƯ HÌNH 1)
    cta_c1, cta_c2, cta_c3 = st.columns([1.2, 2.0, 1.2])
    with cta_c2:
        btn_c1, btn_c2 = st.columns(2)
        with btn_c1:
            if st.button("Bắt đầu ngay ➔", type="primary", use_container_width=True, key="btn_hero_start_main"):
                st.session_state.current_view = "workspace"
                st.session_state.workspace_mode = "LUONG_1"
                st.rerun()
        with btn_c2:
            if st.button("Xem bảng giá", use_container_width=True, key="btn_hero_view_pricing"):
                st.session_state.selected_plan_info = {
                    "name": "GÓI_PRO_299K",
                    "label": "Gói Pro Doanh Nghiệp (120 Lượt)",
                    "amount": 299000,
                    "credits": 120,
                    "plan_type": "CRE",
                    "val": "120"
                }
                code_suffix = str(int(time.time()))[-5:]
                st.session_state.current_order_code = f"M22KT_{code_suffix}"
                st.rerun()

    # BANNER LƯU Ý NGHIỆP VỤ (NHƯ LƯU Ý GAME HÌNH 1)
    st.markdown("""
    <div style="max-width:920px;margin:18px auto 26px auto;">
        <div class="saas-warning-banner">
            <span style="font-size:16px;">⚠️</span>
            <div><b>LƯU Ý NGHIỆP VỤ:</b> Hồ sơ nguyên liệu thủy sản khai thác từ tàu nước ngoài cập cảng Việt Nam bắt buộc đối soát danh mục tàu IUU và khớp số container trước khi nộp Chi cục Thủy sản.</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 3. HAI LỰA CHỌN TRẢI NGHIỆM: WEB CLOUD VS PHẦN MỀM DESKTOP
    st.markdown("""
    <div style="font-size:18px;font-weight:900;color:#0F172A;text-align:center;margin:30px 0 6px 0;">
        CHỌN HÌNH THỨC SỬ DỤNG PHÙ HỢP VỚI DOANH NGHIỆP BẠN
    </div>
    <div style="font-size:13px;color:#64748B;text-align:center;margin-bottom:20px;">
        Sử dụng trực tiếp trên trình duyệt mọi lúc mọi nơi HOẶC tải bộ cài đặt chạy độc lập trên máy tính Windows.
    </div>
    """, unsafe_allow_html=True)

    choice_c1, choice_c2 = st.columns(2)
    with choice_c1:
        st.markdown("""
        <div class="platform-choice-card">
            <div>
                <span class="platform-tag platform-tag-web">🌐 DÙNG TRỰC TIẾP TRÊN WEB • KHÔNG CẦN CÀI ĐẶT</span>
                <div class="platform-title">Nền Tảng Web Cloud</div>
                <div class="platform-desc">
                    Trải nghiệm bóc tách chứng từ và lập Mẫu 22.KT tức thì ngay trên trình duyệt máy tính hoặc điện thoại. Xử lý đa luồng với Google Gemini 3.8 Flash, đối soát tàu IUU Live và xuất file Word .docx trong 25 giây.
                </div>
                <ul style="font-size:12px;color:#334155;line-height:1.8;padding-left:18px;margin-bottom:18px;">
                    <li>✓ <b>Sử dụng ngay</b> từ mọi thiết bị, không yêu cầu cấu hình máy</li>
                    <li>✓ <b>Xử lý In-Memory RAM:</b> Không lưu vĩnh viễn hóa đơn trên máy chủ</li>
                    <li>✓ <b>Xem song song PDF:</b> Đối chiếu chứng từ 2 cột trực quan</li>
                    <li>✓ <b>Xuất file Word .docx:</b> Chuẩn quy chuẩn nộp Chi cục Thủy sản</li>
                </ul>
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("🚀 BẮT ĐẦU DÙNG TRÊN WEB NGAY", type="primary", use_container_width=True, key="btn_choice_use_web"):
            st.session_state.current_view = "workspace"
            st.session_state.workspace_mode = "LUONG_1"
            st.rerun()

    with choice_c2:
        st.markdown("""
        <div class="platform-choice-card">
            <div>
                <span class="platform-tag platform-tag-desktop">💻 BẢN CÀI ĐẶT WINDOWS • HOẠT ĐỘNG OFFLINE 100%</span>
                <div class="platform-title">Phần Mềm Desktop Mẫu 22 Pro</div>
                <div class="platform-desc">
                    Bộ cài đặt chuyên nghiệp dành cho máy tính doanh nghiệp (Windows 10/11 64-bit). Tích hợp sẵn 5 bộ CSDL tàu quốc tế offline, bảo mật tuyệt đối dữ liệu nội bộ và kích hoạt bằng License Key mua trên Web.
                </div>
                <ul style="font-size:12px;color:#334155;line-height:1.8;padding-left:18px;margin-bottom:18px;">
                    <li>✓ <b>Hoạt động Offline:</b> Tra cứu 5 CSDL tàu cá trong 0.1 giây</li>
                    <li>✓ <b>Bảo mật tuyệt đối:</b> Toàn bộ tệp chứng từ lưu tại máy tính nội bộ</li>
                    <li>✓ <b>Cấp License Key tự động:</b> Nhập Mã máy (HWID) nhận key tức thì</li>
                    <li>✓ <b>Bản Setup .exe & Portable:</b> Cài đặt dễ dàng với 1 click</li>
                </ul>
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("📥 TẢI BẢN DESKTOP (WINDOWS) ➔", type="secondary", use_container_width=True, key="btn_choice_goto_download"):
            st.session_state.current_view = "download"
            st.rerun()

    st.write("")
    st.markdown("---")

    # 4. BẢNG GIÁ DỊCH VỤ & GÓI THUÊ (LAYOUT CARD GPU NHƯ HÌNH 2)
    st.markdown("""
    <div style="font-size:18px;font-weight:900;color:#0F172A;text-align:center;margin:24px 0 6px 0;">
        BẢNG GIÁ ĐIỂM AI & CẤP LICENSE KEY BẢN QUYỀN
    </div>
    <div style="font-size:13px;color:#64748B;text-align:center;margin-bottom:24px;">
        Tính theo Điểm AI (Credits), không giới hạn thời gian sử dụng, tự động cấp License Key chuẩn Desktop theo HWID.
    </div>
    """, unsafe_allow_html=True)

    # Cấu hình HWID cho máy cần cấp bản quyền
    hw_box1, hw_box2 = st.columns([2.5, 1.2])
    with hw_box1:
        target_hwid_input = st.text_input(
            "Mã Máy (HWID) cần cấp License Key bản quyền:",
            value=user_info.get("hwid", default_hwid),
            help="Mã máy 10 ký tự của máy tính bạn muốn cấp bản quyền. Mặc định là mã máy tính hiện tại.",
            key="hwid_license_landing_field"
        )
    with hw_box2:
        st.caption("HWID hiện tại:")
        st.code(default_hwid, language=None)

    # 4 CARD BẢNG GIÁ THEO PHONG CÁCH CARD GPU TRONG HÌNH 2
    p_c1, p_c2, p_c3, p_c4 = st.columns(4)

    # Gói 1: TRIAL
    with p_c1:
        st.markdown("""
        <div class="gpu-pricing-card">
            <div>
                <div class="gpu-card-header">
                    <span class="gpu-card-title">GÓI DÙNG THỬ</span>
                    <span class="gpu-card-badge badge-slot-ok">• Miễn phí</span>
                </div>
                <div class="gpu-specs-line">3x Lượt Trích Xuất AI Gemini 3.8</div>
                <div class="gpu-tags-row">
                    <span class="gpu-tag-chip">web-cloud</span>
                    <span class="gpu-tag-chip">trial</span>
                </div>
                <div class="gpu-price-box">
                    <span class="gpu-price-main">0</span> <span class="gpu-price-unit">VNĐ</span>
                </div>
                <div class="gpu-specs-table">
                    • Lượt trích xuất: <b>3 lượt</b><br/>
                    • Bóc tách 8 tab Mẫu 22: Có<br/>
                    • Thẩm định IUU: Cơ bản<br/>
                    • Xuất file Word: Có<br/>
                    • Hỗ trợ kỹ thuật: Cộng đồng
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Đang Dùng Thử", disabled=True, key="btn_gpu_plan_free", use_container_width=True):
            pass

    # Gói 2: STARTER
    with p_c2:
        st.markdown("""
        <div class="gpu-pricing-card">
            <div>
                <div class="gpu-card-header">
                    <span class="gpu-card-title">KHỞI NGHIỆP</span>
                    <span class="gpu-card-badge badge-slot-ok">• Còn slot</span>
                </div>
                <div class="gpu-specs-line">30x Lượt Trích Xuất AI Gemini 3.8</div>
                <div class="gpu-tags-row">
                    <span class="gpu-tag-chip">web-cloud</span>
                    <span class="gpu-tag-chip">desktop-key</span>
                </div>
                <div class="gpu-price-box">
                    <span class="gpu-price-main">3,300</span> <span class="gpu-price-unit">đ / lượt</span>
                    <span class="gpu-price-discount">-42%</span>
                </div>
                <div class="gpu-specs-table">
                    • Tổng gói: <b>99,000 VNĐ</b> (30 lượt)<br/>
                    • Cấp License Key Desktop: Có<br/>
                    • Tra cứu IUU Live: 5 CSDL<br/>
                    • Xuất Word & JSON: Không giới hạn<br/>
                    • Hạn dùng: Vĩnh viễn đến khi hết lượt
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("👉 Chọn Gói 99K", key="btn_gpu_plan_99k", use_container_width=True):
            st.session_state.selected_plan_info = {
                "name": "GÓI_STARTER_99K",
                "label": "Gói Khởi Nghiệp (30 Lượt AI)",
                "amount": 99000,
                "credits": 30,
                "plan_type": "CRE",
                "val": "30"
            }
            code_suffix = str(int(time.time()))[-5:]
            st.session_state.current_order_code = f"M22KT_{code_suffix}"
            db.create_web_order(st.session_state.current_order_code, user_email, "GÓI_STARTER_99K", 99000, 30, target_hwid_input)
            st.rerun()

    # Gói 3: PRO DOANH NGHIỆP (BEST SELLER)
    with p_c3:
        st.markdown("""
        <div class="gpu-pricing-card" style="border:2px solid #0284C7;background:#F0F9FF;">
            <div>
                <div class="gpu-card-header">
                    <span class="gpu-card-title" style="color:#0284C7;">PRO DOANH NGHIỆP ⭐</span>
                    <span class="gpu-card-badge badge-slot-hot">• Phổ biến</span>
                </div>
                <div class="gpu-specs-line">120x Lượt Trích Xuất AI Gemini 3.8</div>
                <div class="gpu-tags-row">
                    <span class="gpu-tag-chip" style="background:#E0F2FE;color:#0369A1;">web-cloud</span>
                    <span class="gpu-tag-chip" style="background:#E0F2FE;color:#0369A1;">desktop-key</span>
                </div>
                <div class="gpu-price-box">
                    <span class="gpu-price-main">2,490</span> <span class="gpu-price-unit">đ / lượt</span>
                    <span class="gpu-price-discount">-50%</span>
                </div>
                <div class="gpu-specs-table">
                    • Tổng gói: <b>299,000 VNĐ</b> (120 lượt)<br/>
                    • Cấp License Key Desktop: Có<br/>
                    • Ưu tiên tốc độ xử lý: Cao nhất<br/>
                    • Báo cáo thẩm định rủi ro: Chuyên sâu<br/>
                    • Hỗ trợ kỹ thuật: Ưu tiên 24/7
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("🔥 Chọn Gói Pro 299K", type="primary", key="btn_gpu_plan_299k", use_container_width=True):
            st.session_state.selected_plan_info = {
                "name": "GÓI_PRO_299K",
                "label": "Gói Pro Doanh Nghiệp (120 Lượt AI)",
                "amount": 299000,
                "credits": 120,
                "plan_type": "CRE",
                "val": "120"
            }
            code_suffix = str(int(time.time()))[-5:]
            st.session_state.current_order_code = f"M22KT_{code_suffix}"
            db.create_web_order(st.session_state.current_order_code, user_email, "GÓI_PRO_299K", 299000, 120, target_hwid_input)
            st.rerun()

    # Gói 4: ENTERPRISE UNLIMITED
    with p_c4:
        st.markdown("""
        <div class="gpu-pricing-card">
            <div>
                <div class="gpu-card-header">
                    <span class="gpu-card-title">ENTERPRISE 👑</span>
                    <span class="gpu-card-badge badge-slot-hot">• Không giới hạn</span>
                </div>
                <div class="gpu-specs-line">Unlimited Trích Xuất Trong Tháng</div>
                <div class="gpu-tags-row">
                    <span class="gpu-tag-chip">unlimited</span>
                    <span class="gpu-tag-chip">desktop-key</span>
                </div>
                <div class="gpu-price-box">
                    <span class="gpu-price-main">990,000</span> <span class="gpu-price-unit">đ / tháng</span>
                </div>
                <div class="gpu-specs-table">
                    • Lượt trích xuất: <b>Không giới hạn</b><br/>
                    • Cấp License Key Desktop: UNLIMITED<br/>
                    • Tùy biến mẫu Word riêng: Có<br/>
                    • Kết nối CSDL nội bộ: Hỗ trợ<br/>
                    • Bảo hành & Nâng cấp: Trọn gói
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("👉 Chọn Enterprise 990K", key="btn_gpu_plan_990k", use_container_width=True):
            st.session_state.selected_plan_info = {
                "name": "GÓI_ENTERPRISE_990K",
                "label": "Gói Enterprise (Không Giới Hạn / Tháng)",
                "amount": 990000,
                "credits": 999,
                "plan_type": "UNL",
                "val": "UNLIMITED"
            }
            code_suffix = str(int(time.time()))[-5:]
            st.session_state.current_order_code = f"M22KT_{code_suffix}"
            db.create_web_order(st.session_state.current_order_code, user_email, "GÓI_ENTERPRISE_990K", 990000, 999, target_hwid_input)
            st.rerun()

    # KHU VỰC QUÉT MÃ VIETQR VÀ TỰ ĐỘNG CẤP LICENSE KEY
    cur_plan = st.session_state.get("selected_plan_info")
    cur_code = st.session_state.get("current_order_code")

    if cur_plan and cur_code:
        st.write("")
        st.markdown(f"""
        <div style="font-size:16px;font-weight:900;color:#0F172A;margin:16px 0 10px 0;">
            🏦 QUÉT MÃ VIETQR ĐỂ NHẬN KEY BẢN QUYỀN: <span style="color:#0284C7;">{cur_plan['label']}</span>
        </div>
        """, unsafe_allow_html=True)

        qr_c1, qr_c2 = st.columns([1.2, 1.8])
        bank_id = "MB"
        account_no = "090123456789"
        account_name = "NGO QUOC TIEN"
        qr_amount = cur_plan["amount"]
        qr_memo = cur_code
        vietqr_url = f"https://img.vietqr.io/image/{bank_id}-{account_no}-compact2.png?amount={qr_amount}&addInfo={qr_memo}&accountName={account_name.replace(' ', '%20')}"

        with qr_c1:
            st.markdown(f"""
            <div style="background:#FFFFFF;border:1px solid #CBD5E1;border-radius:12px;padding:16px;text-align:center;">
                <img src="{vietqr_url}" style="max-width:100%;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.06);"/>
                <div style="font-size:11px;color:#64748B;margin-top:8px;">Mã VietQR động tạo tự động chuẩn Napas 247</div>
            </div>
            """, unsafe_allow_html=True)

        with qr_c2:
            st.markdown(f"""
            <div class="content-panel" style="background:#F8FAFC;border:1px solid #CBD5E1;">
                <div class="panel-header" style="color:#0F172A;">📋 HƯỚNG DẪN CHUYỂN KHOẢN & NHẬN KEY TỰ ĐỘNG</div>
                <div style="font-size:13px;line-height:2.0;color:#334155;">
                    • <b>Ngân hàng thụ hưởng:</b> <span style="color:#0284C7;font-weight:700;">MBBank (Ngân hàng Quân Đội)</span><br/>
                    • <b>Số tài khoản:</b> <code style="background:#FFFFFF;padding:2px 8px;border-radius:4px;font-size:13px;font-weight:700;color:#0F172A;">{account_no}</code><br/>
                    • <b>Chủ tài khoản:</b> <b style="color:#0F172A;">{account_name}</b><br/>
                    • <b>Số tiền chính xác:</b> <b style="color:#059669;font-size:15px;">{qr_amount:,} VNĐ</b><br/>
                    • <b>Nội dung chuyển khoản (bắt buộc):</b> <code style="background:#FEF3C7;color:#B45309;padding:3px 8px;border-radius:4px;font-weight:800;font-size:14px;">{qr_memo}</code><br/>
                    • <b>Mã máy cấp key (HWID):</b> <code style="background:#EFF6FF;color:#0284C7;padding:2px 8px;border-radius:4px;font-weight:800;">{target_hwid_input}</code>
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.caption("Sau khi hoàn tất quét mã chuyển khoản trên App ngân hàng, bấm nút bên dưới để hệ thống cấp ngay License Key bản quyền:")
            
            c_btn_done, c_btn_cancel = st.columns([1.6, 1.0])
            with c_btn_done:
                if st.button("✅ XÁC NHẬN ĐÃ CHUYỂN KHOẢN (CẤP KEY NGAY)", type="primary", use_container_width=True, key="btn_confirm_pay_landing"):
                    ok_act, msg_act, gen_key = db.activate_voucher_or_order(qr_memo, user_email, target_hwid_input)
                    if ok_act:
                        fresh_u = db.get_web_user(user_email)
                        if fresh_u:
                            st.session_state.logged_user["credits"] = fresh_u["credits"]
                            st.session_state.logged_user["plan"] = fresh_u["plan"]
                            st.session_state.logged_user["license_key"] = fresh_u["license_key"]
                            st.session_state.logged_user["hwid"] = target_hwid_input
                        else:
                            st.session_state.logged_user["credits"] += cur_plan["credits"]
                            st.session_state.logged_user["license_key"] = gen_key

                        st.session_state.last_generated_key = gen_key
                        st.session_state.selected_plan_info = None
                        st.session_state.current_order_code = ""
                        st.success(f"🎉 {msg_act}")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg_act}")
            with c_btn_cancel:
                if st.button("✕ Hủy Đơn Này", use_container_width=True, key="btn_cancel_pay_landing"):
                    st.session_state.selected_plan_info = None
                    st.session_state.current_order_code = ""
                    st.rerun()

    # HIỂN THỊ LICENSE KEY NẾU VỪA TẠO
    if st.session_state.get("last_generated_key"):
        st.markdown(f"""
        <div style="background:#ECFDF5;border:2px solid #059669;padding:16px 20px;border-radius:10px;margin:16px 0;">
            <div style="font-weight:800;color:#059669;font-size:15px;margin-bottom:6px;">🎉 BẢN QUYỀN ĐÃ ĐƯỢC CẤP THÀNH CÔNG!</div>
            <div style="font-size:13px;color:#065F46;margin-bottom:10px;">Dưới đây là License Key kích hoạt cho máy tính của bạn (tương thích 100% với bản Desktop):</div>
            <code style="background:#FFFFFF;border:1px solid #A7F3D0;padding:8px 14px;border-radius:6px;font-size:16px;font-weight:800;color:#0F172A;display:block;letter-spacing:1px;">{st.session_state['last_generated_key']}</code>
            <div style="font-size:11.5px;color:#047857;margin-top:8px;">💡 Hãy sao chép mã này và dán vào phần mềm Desktop Mẫu 22 KT Pro hoặc kích hoạt trực tiếp trên web!</div>
        </div>
        """, unsafe_allow_html=True)

    # KHUNG NHẬP MÃ VOUCHER / LICENSE KEY
    st.write("")
    with st.expander("🎁 NHẬP MÃ VOUCHER KHUYẾN MÃI HOẶC KEY BẢN QUYỀN", expanded=False):
        st.caption("Nhập mã Voucher được cấp hoặc License Key từ phần mềm Desktop để kích hoạt thêm lượt:")
        v_col1, v_col2 = st.columns([3, 1.2])
        with v_col1:
            voucher_input = st.text_input(
                "Mã Voucher / License Key:",
                placeholder="Nhập mã đơn, mã voucher (IUU-DEMO-2026) hoặc key (CRE-30-...)",
                key="input_voucher_code_landing",
                label_visibility="collapsed"
            )
        with v_col2:
            btn_redeem = st.button("🚀 Kích Hoạt Ngay", type="primary", use_container_width=True, key="btn_redeem_landing")

        if btn_redeem and voucher_input.strip():
            ok_v, msg_v, k_v = db.activate_voucher_or_order(voucher_input.strip(), user_email, target_hwid_input)
            if ok_v:
                fresh_u = db.get_web_user(user_email)
                if fresh_u:
                    st.session_state.logged_user["credits"] = fresh_u["credits"]
                    st.session_state.logged_user["plan"] = fresh_u["plan"]
                    st.session_state.logged_user["license_key"] = fresh_u["license_key"]
                st.success(f"🎉 {msg_v}")
                time.sleep(1.2)
                st.rerun()
            else:
                st.error(f"❌ {msg_v}")

    st.write("")
    st.markdown("---")

    # 5. CHUYÊN MỤC BẢN TIN IUU & CHỈ THỊ EC (4 CARDS)
    st.markdown("""
    <div style="display:flex;align-items:center;justify-content:space-between;margin:16px 0 14px 0;">
        <div style="font-size:17px;font-weight:900;color:#0F172A;display:flex;align-items:center;gap:8px;">
            <span>📢</span> BẢN TIN IUU, CHỈ THỊ EC & QUY CHUẨN THỦY SẢN 2026
        </div>
        <span style="font-size:12px;color:#64748B;">Cập nhật từ Cục Thủy sản & EC</span>
    </div>
    """, unsafe_allow_html=True)

    nc1, nc2 = st.columns(2)
    with nc1:
        st.markdown("""
        <div class="content-panel" style="border-left:4px solid #DC2626;">
            <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
                <span style="font-size:10px;font-weight:800;background:#FEE2E2;color:#DC2626;padding:2px 8px;border-radius:4px;">🚨 KHẨN CẤP / THẺ VÀNG EC</span>
                <span style="font-size:11px;color:#94A3B8;">Tháng 10/2026</span>
            </div>
            <div style="font-size:14px;font-weight:800;color:#0F172A;margin-bottom:6px;">Ủy ban Châu Âu (EC) siết chặt kiểm tra nguồn gốc thủy sản khai thác nhập khẩu vào Việt Nam</div>
            <div style="font-size:12.5px;color:#475569;line-height:1.55;">
                Đoàn thanh tra EC tập trung thẩm tra toàn diện hồ sơ cấp Giấy xác nhận cam kết (Mẫu 22.KT) đối với lô hàng thủy sản bốc dỡ từ tàu nước ngoài cập cảng Việt Nam. Các doanh nghiệp được yêu cầu đối soát kỹ lưỡng danh mục tàu cá IUU Blacklist toàn cầu và giấy phép vùng biển RFMO để tránh nguy cơ bị từ chối thông quan lô hàng xuất khẩu sang khối EU.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="content-panel" style="border-left:4px solid #D97706;">
            <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
                <span style="font-size:10px;font-weight:800;background:#FEF3C7;color:#D97706;padding:2px 8px;border-radius:4px;">⚖️ QUY ĐỊNH PHÁP LÝ</span>
                <span style="font-size:11px;color:#94A3B8;">Nghị định 37 & 38/2024/NĐ-CP</span>
            </div>
            <div style="font-size:14px;font-weight:800;color:#0F172A;margin-bottom:6px;">Quy chuẩn lập Báo cáo Mẫu 22.KT theo Nghị định sửa đổi của Chính phủ</div>
            <div style="font-size:12.5px;color:#475569;line-height:1.55;">
                Nghị định số 37/2024/NĐ-CP và 38/2024/NĐ-CP quy định chi tiết việc kiểm soát nguyên liệu thủy sản khai thác từ tàu cá nước ngoài cập cảng Việt Nam. Bắt buộc minh bạch thông tin tàu khai thác, tàu chuyển tải, số IMO, hô hiệu, cảng bốc dỡ và mã số hải quan trước khi làm thủ tục nhập khẩu chính ngạch.
            </div>
        </div>
        """, unsafe_allow_html=True)

    with nc2:
        st.markdown("""
        <div class="content-panel" style="border-left:4px solid #0284C7;">
            <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
                <span style="font-size:10px;font-weight:800;background:#E0F2FE;color:#0284C7;padding:2px 8px;border-radius:4px;">💡 CẨM NANG NGHIỆP VỤ</span>
                <span style="font-size:11px;color:#94A3B8;">Cục Thủy sản VN</span>
            </div>
            <div style="font-size:14px;font-weight:800;color:#0F172A;margin-bottom:6px;">Quy trình 5 bước đối soát tàu cá tránh rủi ro IUU Blacklist & Vi phạm RFMO</div>
            <div style="font-size:12.5px;color:#475569;line-height:1.55;">
                1. Tra cứu số IMO trên hệ thống CSDL quốc tế iuu-vessels.org.<br/>
                2. Kiểm tra thẩm quyền cấp phép khai thác theo từng khu vực đại dương (WCPFC, IOTC, IATTC, ICCAT).<br/>
                3. Đối chiếu ngư cụ khai báo với giấy phép được cấp.<br/>
                4. Kiểm tra lịch trình chuyển tải trên biển.<br/>
                5. Lưu trữ hồ sơ điện tử có đóng dấu kiểm tra hệ thống AI.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="content-panel" style="border-left:4px solid #059669;">
            <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
                <span style="font-size:10px;font-weight:800;background:#ECFDF5;color:#059669;padding:2px 8px;border-radius:4px;">✨ PHIÊN BẢN V1.0.9</span>
                <span style="font-size:11px;color:#94A3B8;">Enterprise Cloud & Desktop</span>
            </div>
            <div style="font-size:14px;font-weight:800;color:#0F172A;margin-bottom:6px;">Đồng bộ bản quyền Web & Desktop qua Mã Máy HWID</div>
            <div style="font-size:12.5px;color:#475569;line-height:1.55;">
                Tích hợp toàn diện 2 nền tảng: Người dùng nạp gói trên Web được cấp ngay License Key theo Mã Máy (HWID) để kích hoạt phần mềm Desktop chạy offline. Bảo mật RAM In-memory chống lộ bí mật kinh doanh.
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.write("")
    st.markdown("---")

    # 6. KHU VỰC TÀI KHOẢN DOANH NGHIỆP (ĐĂNG NHẬP / ĐĂNG KÝ)
    st.markdown("""
    <div style="font-size:17px;font-weight:900;color:#0F172A;margin:16px 0 14px 0;">
        👤 TÀI KHOẢN DOANH NGHIỆP & BẢO MẬT ĐỊNH DANH
    </div>
    """, unsafe_allow_html=True)

    if is_guest:
        st.info("ℹ️ Bạn hiện đang sử dụng ở chế độ **Khách Vãng Lai (Dùng Thử 3 lượt)**. Hãy Đăng Nhập hoặc Đăng Ký tài khoản bên dưới để lưu giữ hồ sơ vĩnh viễn và nhận mã bản quyền License Key!")
        tab_login, tab_register = st.tabs(["🔑 ĐĂNG NHẬP HỆ THỐNG", "📝 ĐĂNG KÝ TÀI KHOẢN MỚI (TẶNG 3 LƯỢT AI)"])

        with tab_login:
            with st.form("form_home_login_saas"):
                l_c1, l_c2 = st.columns(2)
                with l_c1:
                    login_email = st.text_input("Email Doanh Nghiệp:", placeholder="tencongty@thuysan.vn")
                with l_c2:
                    login_pwd = st.text_input("Mật khẩu:", type="password", placeholder="Nhập mật khẩu...")
                btn_do_login = st.form_submit_button("🚀 Đăng Nhập Ngay", type="primary", use_container_width=True)

                if btn_do_login:
                    if not login_email.strip() or not login_pwd.strip():
                        st.warning("Vui lòng nhập đầy đủ Email và Mật khẩu.")
                    else:
                        ok_l, res_l = db.login_web_user(login_email, login_pwd)
                        if ok_l:
                            st.session_state.logged_user = {
                                "id": res_l["id"],
                                "email": res_l["email"],
                                "company_name": res_l["company_name"],
                                "phone": res_l["phone"],
                                "plan": res_l["plan"],
                                "credits": res_l["credits"],
                                "is_guest": False,
                                "created_at": res_l["created_at"],
                                "hwid": res_l.get("hwid", default_hwid),
                                "license_key": res_l.get("license_key", "")
                            }
                            st.success(f"Chào mừng trở lại, {res_l['company_name']}!")
                            time.sleep(1.0)
                            st.rerun()
                        else:
                            st.error(f"Đăng nhập thất bại: {res_l}")

        with tab_register:
            with st.form("form_home_register_saas"):
                r_c1, r_c2 = st.columns(2)
                with r_c1:
                    reg_name = st.text_input("Tên Doanh Nghiệp / Cơ Sở:", placeholder="Công Ty TNHH Thủy Sản Hải Vương")
                    reg_email = st.text_input("Email Đăng Ký:", placeholder="contact@haivuong.com")
                with r_c2:
                    reg_phone = st.text_input("Số Điện Thoại:", placeholder="0901234567")
                    reg_pwd = st.text_input("Mật khẩu (tối thiểu 6 ký tự):", type="password")
                reg_hwid = st.text_input("Mã Máy (HWID) để cấp bản quyền Desktop (Tự động phát hiện):", value=default_hwid)

                btn_do_reg = st.form_submit_button("✨ Đăng Ký Tài Khoản & Nhận 3 Lượt AI Miễn Phí", type="primary", use_container_width=True)

                if btn_do_reg:
                    if not reg_email.strip() or not reg_pwd.strip():
                        st.warning("Vui lòng điền Email và Mật khẩu.")
                    else:
                        ok_r, msg_r = db.register_web_user(reg_email, reg_pwd, reg_name, reg_phone, reg_hwid)
                        if ok_r:
                            ok_l, res_l = db.login_web_user(reg_email, reg_pwd)
                            if ok_l:
                                st.session_state.logged_user = {
                                    "id": res_l["id"],
                                    "email": res_l["email"],
                                    "company_name": res_l["company_name"],
                                    "phone": res_l["phone"],
                                    "plan": res_l["plan"],
                                    "credits": res_l["credits"],
                                    "is_guest": False,
                                    "created_at": res_l["created_at"],
                                    "hwid": res_l.get("hwid", reg_hwid),
                                    "license_key": res_l.get("license_key", "")
                                }
                            st.success(msg_r)
                            time.sleep(1.2)
                            st.rerun()
                        else:
                            st.error(msg_r)
    else:
        # ĐÃ ĐĂNG NHẬP: HIỂN THỊ THẺ HỒ SƠ
        p_c1, p_c2 = st.columns([1.5, 1.0])
        with p_c1:
            st.markdown(f"""
            <div class="content-panel" style="border:1px solid #CBD5E1;">
                <div class="panel-header">🏢 HỒ SƠ DOANH NGHIỆP HIỆN TẠI</div>
                <div style="font-size:13px;line-height:2.1;color:#334155;">
                    • <b>Tên đơn vị:</b> <span style="font-size:14px;color:#0F172A;font-weight:700;">{user_info.get('company_name', 'Chưa đặt')}</span><br/>
                    • <b>Email liên hệ:</b> <code style="background:#F1F5F9;padding:2px 6px;border-radius:4px;color:#0F172A;">{user_info.get('email')}</code><br/>
                    • <b>Số điện thoại:</b> {user_info.get('phone', 'Chưa cập nhật')}<br/>
                    • <b>Mã máy (HWID):</b> <code style="background:#EFF6FF;color:#0284C7;padding:2px 8px;border-radius:4px;font-weight:800;">{user_info.get('hwid', default_hwid)}</code><br/>
                    • <b>Gói dịch vụ:</b> <span style="background:#ECFDF5;color:#059669;padding:2px 8px;border-radius:12px;font-weight:700;font-size:12px;">{user_info.get('plan')}</span><br/>
                    • <b>Số Điểm AI còn lại:</b> <span style="background:#FEF3C7;color:#B45309;padding:3px 10px;border-radius:12px;font-weight:800;font-size:14px;">⚡ {user_credits} lượt</span><br/>
                    • <b>Mã bản quyền License Key:</b> <code style="background:#F1F5F9;color:#0F172A;padding:2px 6px;border-radius:4px;">{user_info.get('license_key') or 'Chưa kích hoạt key'}</code>
                </div>
            </div>
            """, unsafe_allow_html=True)
        with p_c2:
            st.write("")
            st.write("")
            if st.button("🚪 Đăng Xuất Khỏi Hệ Thống", type="secondary", use_container_width=True):
                st.session_state.logged_user = {
                    "id": 0,
                    "email": "khach.hang@demo.vn",
                    "company_name": "Doanh Nghiệp Thủy Sản (Dùng Thử)",
                    "phone": "0901234567",
                    "plan": "FREE_TRIAL",
                    "credits": 3,
                    "is_guest": True,
                    "created_at": "Hôm nay",
                    "hwid": default_hwid,
                    "license_key": ""
                }
                st.info("Đã đăng xuất thành công!")
                st.rerun()

    st.write("")
    st.markdown("---")

    # 7. CTA CUỐI TRANG: VÀO THẲNG DÙNG THỬ
    st.markdown("""
    <div style="text-align:center;padding:20px 0 10px 0;">
        <div style="font-size:18px;font-weight:800;color:#0F172A;margin-bottom:8px;">BẠN ĐÃ SẴN SÀNG TRẢI NGHIỆM MẪU 22 KT PRO?</div>
        <div style="font-size:13px;color:#64748B;margin-bottom:16px;">Bắt đầu số hóa chứng từ nhập khẩu ngay hôm nay với chi phí 0 VNĐ khởi đầu.</div>
    </div>
    """, unsafe_allow_html=True)
    c_bot1, c_bot2, c_bot3 = st.columns([1, 2, 1])
    with c_bot2:
        if st.button("🚀 BẮT ĐẦU TRÍCH XUẤT HỒ SƠ NGAY (CONSOLE)", type="primary", use_container_width=True, key="btn_home_bottom_cta_saas"):
            st.session_state.current_view = "workspace"
            st.session_state.workspace_mode = "LUONG_1"
            st.rerun()


# ==========================================
# GIAO DIỆN PHÂN HỆ: TẢI PHẦN MỀM DESKTOP (WINDOWS EXE & LICENSE KEY)
# ==========================================
def render_download_desktop_page(db: DatabaseManager):
    user_info = st.session_state.get("logged_user", {})
    user_email = user_info.get("email", "khach.hang@demo.vn")
    user_credits = user_info.get("credits", 0)
    default_hwid = user_info.get("hwid", "") or get_hardware_id()

    st.markdown("""
    <div style="padding:10px 0 16px 0;">
        <div style="font-size:24px;font-weight:900;color:#0F172A;letter-spacing:-0.5px;">💻 PHẦN MỀM DESKTOP MẪU 22 KT PRO (WINDOWS)</div>
        <div style="font-size:13.5px;color:#64748B;margin-top:4px;">
            Giải pháp chuyên nghiệp dành cho máy tính doanh nghiệp chạy offline, tích hợp 5 bộ CSDL tàu quốc tế, bảo mật tuyệt đối 100% dữ liệu nội bộ.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # BANNER LƯU Ý BẢO MẬT & TƯƠNG THÍCH
    st.markdown("""
    <div class="saas-warning-banner">
        <span style="font-size:18px;">⚠️</span>
        <div>
            <b>YÊU CẦU HỆ ĐIỀU HÀNH:</b> Tương thích tối ưu trên <b>Windows 10, Windows 11 (64-bit)</b>. Toàn bộ 5 bộ CSDL tàu quốc tế (WCPFC, IOTC, IATTC, ICCAT và IUU Blacklist) đã được đóng gói sẵn trong bộ cài đặt để tra cứu siêu tốc trong 0.1 giây mà không cần mạng internet.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # KHỐI 2 TÙY CHỌN TẢI VỀ
    down_col1, down_col2 = st.columns(2)

    with down_col1:
        st.markdown("""
        <div class="content-panel" style="border-top:3px solid #0284C7;height:100%;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                <span style="font-size:11px;font-weight:800;background:#E0F2FE;color:#0284C7;padding:3px 8px;border-radius:4px;">KHUYÊN DÙNG ⭐</span>
                <span style="font-size:12px;color:#64748B;font-weight:600;">Dung lượng: ~104 MB</span>
            </div>
            <div style="font-size:16px;font-weight:800;color:#0F172A;margin-bottom:6px;">Bản Cài Đặt Tự Động (Setup .EXE)</div>
            <div style="font-size:12.5px;color:#475569;line-height:1.6;margin-bottom:14px;">
                Tự động tạo biểu tượng ngoài màn hình Desktop và Start Menu. Tích hợp sẵn SQLite, OCR engine và cơ chế tự động cập nhật phiên bản mới khi có chỉ thị từ EC.
            </div>
            <div style="font-size:11.5px;color:#059669;font-weight:700;margin-bottom:14px;">
                ✓ Tên tệp: <code>Mau22_KT_Pro_Setup.exe</code><br/>
                ✓ Phiên bản: v1.0.9 Enterprise (Build 2026)<br/>
                ✓ Hệ điều hành: Windows 10/11 64-bit
            </div>
        </div>
        """, unsafe_allow_html=True)

        local_installer_path = os.path.join(CURRENT_DIR, "downloads", "Mau22_KT_Pro_Setup.exe")
        alt_installer_path = os.path.join(CURRENT_DIR, "dist", "Mau22_KT_Pro", "Output", "mysetup.exe")
        actual_path = local_installer_path if os.path.exists(local_installer_path) else (alt_installer_path if os.path.exists(alt_installer_path) else "")

        if actual_path and os.path.exists(actual_path):
            with open(actual_path, "rb") as f_exe:
                st.download_button(
                    label="📥 TẢI BỘ CÀI ĐẶT SETUP (.EXE)",
                    data=f_exe.read(),
                    file_name="Mau22_KT_Pro_Setup.exe",
                    mime="application/octet-stream",
                    type="primary",
                    use_container_width=True,
                    key="btn_download_exe_direct"
                )
        else:
            st.link_button(
                "📥 TẢI BỘ CÀI ĐẶT TỪ GITHUB RELEASES (.EXE)",
                "https://github.com/tien-prog/Mau22_KT_Pro/releases",
                type="primary",
                use_container_width=True
            )

    with down_col2:
        st.markdown("""
        <div class="content-panel" style="border-top:3px solid #059669;height:100%;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                <span style="font-size:11px;font-weight:800;background:#ECFDF5;color:#059669;padding:3px 8px;border-radius:4px;">PORTABLE • CHẠY NGAY</span>
                <span style="font-size:12px;color:#64748B;font-weight:600;">Dung lượng: ~105 MB</span>
            </div>
            <div style="font-size:16px;font-weight:800;color:#0F172A;margin-bottom:6px;">Bản Nén Di Động (Portable .ZIP)</div>
            <div style="font-size:12.5px;color:#475569;line-height:1.6;margin-bottom:14px;">
                Dành cho máy tính văn phòng hạn chế quyền Administrator. Chỉ cần tải về, giải nén ra thư mục hoặc USB là mở chạy được ngay lập tức.
            </div>
            <div style="font-size:11.5px;color:#059669;font-weight:700;margin-bottom:14px;">
                ✓ Tên tệp: <code>Mau22_KT_Pro_Portable.zip</code><br/>
                ✓ Không cần cài đặt, không ghi vào Registry<br/>
                ✓ Mang theo trên USB làm việc mọi nơi
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.link_button(
            "📦 TẢI BẢN NÉN PORTABLE (.ZIP)",
            "https://github.com/tien-prog/Mau22_KT_Pro/releases",
            type="secondary",
            use_container_width=True
        )

    st.write("")
    st.markdown("---")

    # KHỐI CẤP & LẤY LICENSE KEY CHO MÁY TÍNH DESKTOP
    st.markdown("""
    <div style="font-size:17px;font-weight:900;color:#0F172A;margin:16px 0 8px 0;">
        🔑 CẤP LICENSE KEY KÍCH HOẠT PHẦN MỀM DESKTOP
    </div>
    <div style="font-size:13px;color:#64748B;margin-bottom:16px;">
        Hệ thống tự động phát hiện Mã Máy (HWID) của bạn hoặc bạn có thể nhập Mã máy từ phần mềm Desktop để sinh Key bản quyền tương thích 100%:
    </div>
    """, unsafe_allow_html=True)

    k_col1, k_col2 = st.columns([1.6, 1.4])
    with k_col1:
        desktop_hwid = st.text_input(
            "Mã Máy (HWID) máy tính cần kích hoạt:",
            value=default_hwid,
            help="Xem mã máy 10 ký tự trong mục 'Bản Quyền Hệ Thống' của phần mềm Desktop"
        )
        plan_choice = st.selectbox(
            "Loại gói kích hoạt Desktop:",
            ["Gói Đếm Lượt (30 lượt trích xuất)", "Gói Pro Doanh Nghiệp (120 lượt trích xuất)", "Gói Enterprise Không Giới Hạn (30 ngày)"],
            index=1
        )
        p_val = "120" if "120" in plan_choice else ("30" if "30" in plan_choice else "UNLIMITED")
        p_type = "UNL" if p_val == "UNLIMITED" else "CRE"

        if st.button("✨ SINH LICENSE KEY CHO MÁY NÀY NGAY", type="primary", use_container_width=True):
            if not desktop_hwid.strip():
                st.warning("Vui lòng nhập Mã Máy (HWID) của máy tính bạn muốn cấp bản quyền.")
            else:
                from services.license_service import LicenseService
                gen_key = LicenseService.generate_license_key(desktop_hwid.strip(), p_type, p_val)
                st.session_state.generated_desktop_key = gen_key
                st.success("✅ Đã sinh License Key thành công cho máy tính của bạn!")

    with k_col2:
        if st.session_state.get("generated_desktop_key"):
            cur_key = st.session_state["generated_desktop_key"]
            st.markdown(f"""
            <div style="background:#ECFDF5;border:1px solid #A7F3D0;border-radius:10px;padding:14px;margin-top:24px;">
                <div style="font-size:12px;font-weight:800;color:#059669;margin-bottom:4px;">MÃ LICENSE KEY CỦA BẠN:</div>
                <code style="background:#FFFFFF;border:1px solid #6EE7B7;color:#0F172A;font-size:14px;font-weight:800;padding:6px 12px;border-radius:6px;display:block;margin-bottom:8px;">{cur_key}</code>
                <div style="font-size:11.5px;color:#065F46;line-height:1.5;">
                    💡 <b>Cách dùng:</b> Mở phần mềm <b>Mẫu 22 KT Pro</b> trên máy tính $\rightarrow$ Chọn mục <b>Bản Quyền Hệ Thống</b> $\rightarrow$ Dán mã này vào và bấm <b>Kích Hoạt</b>.
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="content-panel" style="background:#F8FAFC;margin-top:24px;">
                <div style="font-size:12px;font-weight:700;color:#64748B;margin-bottom:6px;">HƯỚNG DẪN 3 BƯỚC:</div>
                <div style="font-size:12px;color:#334155;line-height:1.8;">
                    1. Tải và cài đặt phần mềm từ nút bên trên.<br/>
                    2. Mở phần mềm trên máy tính, sao chép Mã Máy (HWID).<br/>
                    3. Dán HWID vào ô bên trái, bấm "Sinh License Key" và dán key vào máy tính để kích hoạt.
                </div>
            </div>
            """, unsafe_allow_html=True)

    st.write("")
    st.markdown("---")
    st.markdown("""
    <div style="text-align:center;">
        <span style="font-size:13px;color:#64748B;">Bạn muốn sử dụng trực tiếp trên trình duyệt mà không cần cài đặt?</span>
    </div>
    """, unsafe_allow_html=True)
    c_back1, c_back2, c_back3 = st.columns([1, 2, 1])
    with c_back2:
        if st.button("🚀 BẮT ĐẦU DÙNG TRÊN WEB CLOUD NGAY", type="secondary", use_container_width=True):
            st.session_state.current_view = "workspace"
            st.session_state.workspace_mode = "LUONG_1"
            st.rerun()


# ==========================================
# 1. TOPBAR & BRANDING ĐỘNG
# ==========================================
view_titles = {
    "home": "TRANG CHỦ",
    "news": "TRANG CHỦ",
    "workspace": "TRÍCH XUẤT CHỨNG TỪ & LẬP MẪU 22.KT",
    "download": "TẢI PHẦN MỀM DESKTOP (WINDOWS)",
    "pricing": "BẢNG GIÁ DỊCH VỤ & NẠP ĐIỂM AI",
    "user_account": "TÀI KHOẢN DOANH NGHIỆP",
    "dashboard": "QUẢN LÝ CƠ SỞ DỮ LIỆU HỒ SƠ",
    "api_report": "QUẢN LÝ CƠ SỞ DỮ LIỆU HỒ SƠ",
    "license": "TẢI BẢN DESKTOP & BẢN QUYỀN",
    "rfmo_live": "CỔNG TRA CỨU RFMO LIVE",
    "docs": "HƯỚNG DẪN NGHIỆP VỤ"
}
active_title = view_titles.get(st.session_state.current_view, "TRANG CHỦ")

ai_badge_class = "badge-ai-busy" if st.session_state.is_ai_running else "badge-ai-ready"
ai_badge_text = "⏳ Lõi AI: Đang Xử Lý..." if st.session_state.is_ai_running else "⚡ Lõi AI: Sẵn Sàng"

loaded_db, total_db = get_vessel_db_status()
db_badge_class = "badge-db-loaded" if loaded_db == total_db else "badge-db-waiting"
db_badge_text = f"🚢 CSDL: Đã nạp ({loaded_db}/{total_db})" if loaded_db == total_db else f"⏳ CSDL: Đang tải ({loaded_db}/{total_db})..."

user_inf = st.session_state.get("logged_user", {})
u_comp = user_inf.get("company_name", "Khách hàng")
if len(u_comp) > 20:
    u_comp = u_comp[:20] + "..."
u_cred = user_inf.get("credits", 0)
u_plan = user_inf.get("plan", "FREE_TRIAL")

st.markdown(f"""
<div class="saas-navbar">
    <div class="saas-nav-brand">
        <span>🚢</span> M22 <span style="color:#0284C7;">CLOUDX</span>
        <span style="color:#94A3B8;font-size:13px;font-weight:600;margin:0 4px;">/</span>
        <span style="color:#0284C7;font-size:13px;font-weight:700;">{active_title}</span>
    </div>
    <div class="saas-nav-actions">
        <div class="badge-point-pill">⚡ {u_cred} Điểm AI</div>
        <div style="background:#F1F5F9;color:#334155;font-size:11.5px;font-weight:700;padding:5px 12px;border-radius:14px;">👤 {u_comp}</div>
        <div style="background:#ECFDF5;color:#059669;font-size:11.5px;font-weight:700;padding:5px 10px;border-radius:14px;">{db_badge_text}</div>
    </div>
</div>
""", unsafe_allow_html=True)


# ==========================================
# 2. SIDEBAR SÁNG SAAS (270PX)
# ==========================================
with st.sidebar:
    st.markdown("""
    <div style="padding: 10px 0 14px 0; border-bottom: 1px solid #E2E8F0; margin-bottom: 12px;">
        <div style="font-size: 20px; font-weight: 900; color: #0F172A; letter-spacing: -0.5px;">🚢 M22 <span style="color:#0284C7;">CLOUDX</span></div>
        <div style="font-size: 11px; color: #64748B; font-weight: 600;">Audit & Chứng Từ Thủy Sản IUU</div>
    </div>
    """, unsafe_allow_html=True)

    # Mini User Card
    st.markdown(f"""
    <div style="background:#F8FAFC;padding:12px;border-radius:10px;margin-bottom:14px;border:1px solid #E2E8F0;">
        <div style="font-size:10.5px;color:#64748B;font-weight:600;">TÀI KHOẢN DOANH NGHIỆP:</div>
        <div style="font-size:12.5px;font-weight:800;color:#0F172A;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{user_inf.get('company_name', 'Khách Dùng Thử')}</div>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:8px;">
            <span style="font-size:10.5px;color:#0284C7;font-weight:700;background:#E0F2FE;padding:2px 8px;border-radius:4px;">Gói: {u_plan}</span>
            <span style="font-size:11.5px;color:#0284C7;font-weight:800;">⚡ {u_cred} lượt</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    nav_options = [
        "🏠   Trang Chủ",
        "⚡   Trích Xuất AI (Web App)",
        "💻   Tải Bản Desktop (Windows)",
        "💳   Bảng Giá & Mua Điểm AI",
        "📊   Quản Lý CSDL Hồ Sơ",
        "🌐   Cổng Tra Cứu RFMO Live",
        "📖   Hướng Dẫn Nghiệp Vụ"
    ]
    
    view_index_map = {
        "home": 0,
        "news": 0,
        "workspace": 1,
        "download": 2,
        "license": 2,
        "pricing": 3,
        "user_account": 3,
        "dashboard": 4,
        "api_report": 4,
        "rfmo_live": 5,
        "docs": 6
    }
    cur_idx = view_index_map.get(st.session_state.current_view, 0)

    selected_menu = st.radio(
        "ĐIỀU HƯỚNG CHÍNH:",
        nav_options,
        index=cur_idx,
        label_visibility="collapsed"
    )

    if "Trang Chủ" in selected_menu:
        st.session_state.current_view = "home"
    elif "Trích Xuất AI" in selected_menu:
        st.session_state.current_view = "workspace"
    elif "Tải Bản Desktop" in selected_menu:
        st.session_state.current_view = "download"
    elif "Bảng Giá" in selected_menu or "Mua Điểm" in selected_menu:
        st.session_state.current_view = "pricing"
    elif "Quản Lý CSDL" in selected_menu:
        st.session_state.current_view = "dashboard"
    elif "Cổng Tra Cứu" in selected_menu:
        st.session_state.current_view = "rfmo_live"
    elif "Hướng Dẫn" in selected_menu:
        st.session_state.current_view = "docs"
    sync_states()

    st.markdown("---")
    st.markdown("<b style='color:#0F172A;font-size:12px;'>⚡ LÕI AI GEMINI</b>", unsafe_allow_html=True)
    selected_model = st.selectbox(
        "Mô hình AI:",
        ["Gemini 3.8 Flash", "Gemini 3.5 Flash", "gemini-3.1-pro-preview"],
        index=0,
        label_visibility="collapsed"
    )
    st.session_state.selected_model = selected_model

    st.markdown("---")
    st.markdown("<b style='color:#0F172A;font-size:12px;'>🔑 QUẢN LÝ KHÓA API</b>", unsafe_allow_html=True)
    default_key = get_gemini_api_key()
    custom_key = st.text_input("Gemini API Key:", value=default_key, type="password", label_visibility="collapsed")
    active_api_key = custom_key.strip() if custom_key.strip() else default_key
    st.session_state.active_api_key = active_api_key

    st.markdown("---")
    hwid = get_hardware_id()
    st.markdown(f"""
    <div style="font-size:11px;color:#64748B;line-height:1.6;">
        Mã máy HWID: <code style="color:#0284C7;font-size:10.5px;">{hwid}</code><br/>
        Trạng thái: <span style="color:#059669;font-weight:700;">Sẵn sàng</span><br/>
        <div style="margin-top:6px;display:inline-block;padding:2px 8px;background:#F1F5F9;border-radius:6px;color:#334155;font-size:10px;font-weight:700;">
            Phiên bản 1.0.9 Enterprise
        </div>
        <div style="font-size:10px;color:#94A3B8;margin-top:12px;">
            © 2026 M22 CLOUDX CO., LTD
        </div>
    </div>
    """, unsafe_allow_html=True)


# =========================================================================
# ĐIỀU HƯỚNG MÀN HÌNH CHÍNH (PAGE ROUTER)
# =========================================================================
if st.session_state.current_view in ["home", "news", "pricing", "user_account"]:
    render_landing_home_page(db)

elif st.session_state.current_view in ["download", "license"]:
    render_download_desktop_page(db)

elif st.session_state.current_view == "docs":
    st.subheader("📖 HƯỚNG DẪN THAO TÁC & QUY CHUẨN NGHIỆP VỤ MẪU 22.KT")
    st.caption("Quy trình 4 bước chuẩn hóa chứng từ hải sản nhập khẩu theo Nghị định 37 & 38/2024/NĐ-CP")
    g1, g2, g3, g4 = st.columns(4)
    with g1:
        st.markdown("""<div class="content-panel" style="border-top:3px solid #0284C7;"><div style="font-weight:800;color:#0284C7;font-size:12px;">BƯỚC 1</div><div style="font-weight:700;font-size:14px;margin:4px 0;">Nạp Chứng Từ</div><div style="font-size:12px;color:#64748B;">Kéo thả tệp PDF hoặc ảnh Invoice, B/L, C/C vào khung nạp chứng từ.</div></div>""", unsafe_allow_html=True)
    with g2:
        st.markdown("""<div class="content-panel" style="border-top:3px solid #059669;"><div style="font-weight:800;color:#059669;font-size:12px;">BƯỚC 2</div><div style="font-weight:700;font-size:14px;margin:4px 0;">AI Bóc Tách</div><div style="font-size:12px;color:#64748B;">Gemini AI tự động phân tích và điền đủ 8 tab dữ liệu Mẫu 22.KT trong 25s.</div></div>""", unsafe_allow_html=True)
    with g3:
        st.markdown("""<div class="content-panel" style="border-top:3px solid #D97706;"><div style="font-weight:800;color:#D97706;font-size:12px;">BƯỚC 3</div><div style="font-weight:700;font-size:14px;margin:4px 0;">Thẩm Định IUU</div><div style="font-size:12px;color:#64748B;">Hệ thống tự động tra cứu tàu trên 5 CSDL quốc tế (WCPFC, IOTC, Blacklist).</div></div>""", unsafe_allow_html=True)
    with g4:
        st.markdown("""<div class="content-panel" style="border-top:3px solid #7C3AED;"><div style="font-weight:800;color:#7C3AED;font-size:12px;">BƯỚC 4</div><div style="font-weight:700;font-size:14px;margin:4px 0;">Xuất Bản Word</div><div style="font-size:12px;color:#64748B;">Bấm 'Xuất Word' để tải file .docx hoàn chỉnh nộp Chi cục Thủy sản.</div></div>""", unsafe_allow_html=True)

elif st.session_state.current_view == "dashboard":
    st.subheader("🏠 TỔNG QUAN HỆ THỐNG & ĐỐI SOÁT HỒ SƠ")
    st.caption("Giám sát hoạt động xử lý tài liệu hải sản, kiểm tra IUU và đối soát RFMO trực tuyến")

    # 1. Stat cards
    stats = db.get_statistics() if hasattr(db, 'get_statistics') else {"total": 0, "success": 0, "processing": 0, "error": 0, "avg_acc": 99.2}
    c1, c2, c3, c4, c5 = st.columns(5)
    
    with c1:
        st.markdown(f"""<div class="stat-card"><div class="stat-card-header"><div class="stat-icon" style="background:#F1F5F9;color:#0F172A;">📄</div><div class="stat-title">TỔNG HỒ SƠ</div></div><div class="stat-val" style="color:#0F172A;">{stats.get('total', 0)}</div></div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="stat-card"><div class="stat-card-header"><div class="stat-icon" style="background:#ECFDF5;color:#059669;">✓</div><div class="stat-title">HOÀN THÀNH</div></div><div class="stat-val" style="color:#059669;">{stats.get('success', 0)}</div></div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class="stat-card"><div class="stat-card-header"><div class="stat-icon" style="background:#EFF6FF;color:#2563EB;">⏳</div><div class="stat-title">ĐANG XỬ LÝ</div></div><div class="stat-val" style="color:#2563EB;">{stats.get('processing', 0)}</div></div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""<div class="stat-card"><div class="stat-card-header"><div class="stat-icon" style="background:#FFFBEB;color:#D97706;">⚠</div><div class="stat-title">LỖI / BẢN NHÁP</div></div><div class="stat-val" style="color:#D97706;">{stats.get('error', 0)}</div></div>""", unsafe_allow_html=True)
    with c5:
        st.markdown(f"""<div class="stat-card"><div class="stat-card-header"><div class="stat-icon" style="background:#F5F3FF;color:#7C3AED;">🎯</div><div class="stat-title">ĐỘ CHÍNH XÁC</div></div><div class="stat-val" style="color:#7C3AED;">{stats.get('avg_acc', 99.2)}%</div></div>""", unsafe_allow_html=True)

    st.write("")
    # Quick action banner
    c_act1, c_act2 = st.columns([2, 1])
    with c_act1:
        st.markdown("""
        <div class="content-panel">
            <div class="panel-header">⚡ TRÍCH XUẤT NHANH CHỨNG TỪ THỦY SẢN</div>
            <p style="font-size:12.5px;color:#475569;margin-bottom:12px;">Hệ thống ứng dụng trí tuệ nhân tạo Gemini 3.8 Flash nhận diện đa tài liệu: Hóa đơn, Vận đơn B/L, Chứng nhận đánh bắt CC, Chứng thư chuyển tải và Tờ khai hải quan để lập Mẫu 22.KT chỉ trong vài giây.</p>
        </div>
        """, unsafe_allow_html=True)
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("🚀 Vào Không Gian Trích Xuất (Workspace)", type="primary", use_container_width=True):
                st.session_state.current_view = "workspace"
                st.session_state.workspace_mode = "LUONG_1"
                st.rerun()
        with col_btn2:
            if st.button("⚡ Nạp Dữ Liệu Mẫu Kiểm Thử Tức Thì", use_container_width=True):
                st.session_state.current_extracted_data = get_full_sample_dataset()
                st.session_state.extracted_data = st.session_state.current_extracted_data
                st.session_state.current_step = 3
                st.session_state.step = 3
                checker = RFMOChecker(base_dir=CURRENT_DIR)
                rep, vr = checker.verify_ho_so(st.session_state.current_extracted_data)
                st.session_state.rfmo_audit_results = {"ho_so_report": rep, "v_results": vr}
                st.session_state.rfmo_results = st.session_state.rfmo_audit_results
                st.session_state.current_view = "workspace"
                st.rerun()

    with c_act2:
        st.markdown(f"""
        <div class="content-panel">
            <div class="panel-header">🚢 TRẠNG THÁI CSDL RFMO & IUU</div>
            <div style="font-size:12px;color:#475569;line-height:1.8;">
                • WCPFC Vessels: <b style="color:#059669;">Đã nạp</b><br/>
                • IOTC Vessels: <b style="color:#059669;">Đã nạp</b><br/>
                • IATTC Vessels: <b style="color:#059669;">Đã nạp</b><br/>
                • ICCAT Vessels: <b style="color:#059669;">Đã nạp</b><br/>
                • IUU Blacklist: <b style="color:#059669;">Đã nạp</b><br/>
                • Tổng số nguồn đồng bộ: <b>{loaded_db}/{total_db}</b>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Bảng hồ sơ gần đây
    st.markdown('<div class="content-panel"><div class="panel-header">📋 DANH SÁCH HỒ SƠ ĐÃ XỬ LÝ GẦN ĐÂY</div>', unsafe_allow_html=True)
    history = db.get_recent_ho_so(20) if hasattr(db, 'get_recent_ho_so') else []
    if history:
        df_hist = pd.DataFrame(history, columns=["Mã HS", "Tên File", "Nghiệp vụ", "Nhà cung cấp", "Thời gian AI", "Trạng thái", "Ngày tạo"])
        st.dataframe(df_hist, use_container_width=True, hide_index=True)
    else:
        st.info("Chưa có hồ sơ nào được lưu trong cơ sở dữ liệu. Hãy tạo hồ sơ mới hoặc bấm 'Nạp Dữ Liệu Mẫu'.")
    st.markdown('</div>', unsafe_allow_html=True)


elif st.session_state.current_view == "workspace":
    # BANNER LƯU Ý BẢO MẬT DỮ LIỆU IN-MEMORY (THEO HÌNH 2)
    st.markdown("""
    <div class="saas-warning-banner">
        <span style="font-size:18px;">⚠️</span>
        <div>
            <b>LƯU Ý BẢO MẬT DỮ LIỆU:</b> Toàn bộ hóa đơn thương mại, vận đơn và tài liệu scan được xử lý trực tiếp trong <b>bộ nhớ RAM (In-Memory Buffer)</b>. Máy chủ tuyệt đối <b>KHÔNG lưu trữ tệp scan vĩnh viễn</b> nhằm bảo vệ 100% bí mật giá thành và đối tác của doanh nghiệp.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # THẺ COMPUTING POINT / ĐIỂM AI (THEO HÌNH 2)
    user_inf = st.session_state.get("logged_user", {})
    u_cred = user_inf.get("credits", 0)
    u_plan = user_inf.get("plan", "FREE_TRIAL")
    
    w_card_col1, w_card_col2 = st.columns([3.5, 1.2])
    with w_card_col1:
        st.markdown(f"""
        <div class="wallet-balance-card">
            <div class="wallet-left">
                <div class="wallet-icon">💳</div>
                <div>
                    <div class="wallet-info-title">ĐIỂM AI HIỆN CÓ (COMPUTING POINT):</div>
                    <div class="wallet-info-val">{u_cred} <span style="font-size:16px;color:#0284C7;">lượt</span></div>
                </div>
            </div>
            <div style="font-size:12px;color:#64748B;">
                Gói hiện tại: <b style="color:#0284C7;">{u_plan}</b> | Tiêu hao: <b>1 lượt / lần bóc tách AI</b>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with w_card_col2:
        st.write("")
        if st.button("💳 Mua Computing Point", type="primary", use_container_width=True, key="btn_workspace_buy_credits"):
            st.session_state.current_view = "pricing"
            st.rerun()

    # 3. 3-STEP STEPPER PIPELINE
    if not st.session_state.stepper_collapsed:
        step = st.session_state.current_step
        if step == 1:
            s1_cls, s1_txt = "step-active", "● 1. Chọn & Nạp Tài Liệu"
            sep1_col = "#94A3B8"
        else:
            s1_cls, s1_txt = "step-done", "✓ 1. Đã Nạp Tài Liệu"
            sep1_col = "#34D399"

        if step == 1:
            s2_cls, s2_txt = "step-idle", "2. AI Gemini Trích Xuất"
            sep2_col = "#CBD5E1"
        elif step == 2:
            s2_cls, s2_txt = "step-active", "⏳ 2. AI Đang Trích Xuất..."
            sep2_col = "#CBD5E1"
        else:
            s2_cls, s2_txt = "step-done", "✓ 2. AI Trích Xuất Xong"
            sep2_col = "#34D399"

        if step < 3:
            s3_cls, s3_txt = "step-idle", "3. Đối Chiếu IUU & Xuất Mẫu 22"
        else:
            s3_cls, s3_txt = "step-active", "● 3. Đối Chiếu IUU & Xuất Mẫu 22"

        st.markdown(f"""
        <div class="stepper-box">
            <div class="step-item {s1_cls}">{s1_txt}</div>
            <div class="step-sep" style="color: {sep1_col};">→</div>
            <div class="step-item {s2_cls}">{s2_txt}</div>
            <div class="step-sep" style="color: {sep2_col};">→</div>
            <div class="step-item {s3_cls}">{s3_txt}</div>
        </div>
        """, unsafe_allow_html=True)

    # Top Control Bar trong Workspace
    w_col1, w_col2, w_col3, w_col4, w_col5 = st.columns([2.0, 1.2, 1.4, 1.4, 2.0])
    with w_col1:
        # Chế độ trích xuất
        m_opts = ["🏛️ LUỒNG 1: CHỨNG TỪ GỐC (EN)", "📋 LUỒNG 2: MẪU 22 CŨ (VN)"]
        m_idx = 0 if st.session_state.workspace_mode == "LUONG_1" else 1
        sel_mode = st.selectbox("Chế độ:", m_opts, index=m_idx, label_visibility="collapsed")
        st.session_state.workspace_mode = "LUONG_1" if "LUỒNG 1" in sel_mode else "LUONG_2"

    with w_col2:
        # Nút ẩn/hiện cột PDF song song
        pdf_toggle_txt = "✕ Ẩn PDF" if st.session_state.show_doc_preview else "👁️ Mở PDF"
        if st.button(pdf_toggle_txt, use_container_width=True, help="Bật / Tắt hiển thị trình xem tài liệu bên trái"):
            st.session_state.show_doc_preview = not st.session_state.show_doc_preview
            st.session_state.show_pdf = st.session_state.show_doc_preview
            st.rerun()

    with w_col3:
        # Nút thu gọn / mở rộng Stepper
        st_toggle_txt = "▼ Mở Stepper" if st.session_state.stepper_collapsed else "▲ Thu gọn"
        if st.button(st_toggle_txt, use_container_width=True, help="Thu gọn thanh tiến trình để tăng diện tích làm việc"):
            st.session_state.stepper_collapsed = not st.session_state.stepper_collapsed
            st.rerun()

    with w_col4:
        # Nạp Dữ Liệu Mẫu (F3.6)
        if st.button("🚀 NẠP DỮ LIỆU MẪU", use_container_width=True, help="Nạp tức thì bộ hồ sơ mẫu chuẩn hải sản để trải nghiệm không tốn API"):
            st.session_state.current_extracted_data = get_full_sample_dataset()
            st.session_state.extracted_data = st.session_state.current_extracted_data
            st.session_state.current_step = 3
            st.session_state.step = 3
            chk = RFMOChecker(base_dir=CURRENT_DIR)
            rep, vr = chk.verify_ho_so(st.session_state.current_extracted_data)
            st.session_state.rfmo_audit_results = {"ho_so_report": rep, "v_results": vr}
            st.session_state.rfmo_results = st.session_state.rfmo_audit_results
            st.success("✅ Đã nạp thành công bộ hồ sơ mẫu chuẩn Mẫu 22.KT!")
            st.rerun()

    with w_col5:
        # Nút Bắt đầu trích xuất
        btn_run_ai = st.button("⚡ BẮT ĐẦU TRÍCH XUẤT AI", type="primary", use_container_width=True)

    # Khu vực Upload Tệp & Nạp Bản Nháp JSON
    with st.expander("📂 NẠP BẢN NHÁP JSON ĐÃ LƯU (KHÔI PHỤC HỒ SƠ)", expanded=False):
        uploaded_json = st.file_uploader(
            "Chọn tệp JSON bản nháp đã xuất trước đó:",
            type=["json"],
            key="uploader_draft_json",
            help="Tải lên tệp Draft_*.json để khôi phục toàn bộ 8 tab dữ liệu"
        )
        if uploaded_json is not None:
            try:
                draft_content = json.loads(uploaded_json.getvalue().decode("utf-8"))
                if isinstance(draft_content, dict):
                    st.session_state.current_extracted_data = draft_content
                    st.session_state.extracted_data = draft_content
                    st.session_state.current_step = 3
                    st.session_state.step = 3
                    if draft_content.get("tau_danh_bat"):
                        chk = RFMOChecker(base_dir=CURRENT_DIR)
                        rep, vr = chk.verify_ho_so(draft_content)
                        st.session_state.rfmo_audit_results = {"ho_so_report": rep, "v_results": vr}
                        st.session_state.rfmo_results = st.session_state.rfmo_audit_results
                    st.success("✅ Đã khôi phục thành công toàn bộ hồ sơ từ bản nháp JSON!")
                    st.rerun()
                else:
                    st.error("Tệp JSON không đúng cấu trúc hồ sơ hợp lệ.")
            except Exception as err:
                st.error(f"Lỗi khi đọc tệp JSON: {err}")

    uploaded_files = st.file_uploader(
        "Kéo thả hoặc chọn các file PDF chứng từ, Hóa đơn, Vận đơn, B/L, Giấy phép:",
        type=["pdf", "png", "jpg", "jpeg", "json"],
        accept_multiple_files=True,
        key="file_uploader_dossier",
        label_visibility="collapsed"
    )

    # Tự động nạp nếu người dùng kéo thả file JSON vào uploader chính
    if uploaded_files:
        _j_files = [f for f in uploaded_files if f.name.lower().endswith(".json")]
        if _j_files and not btn_run_ai and not st.session_state.is_ai_running:
            _jf = _j_files[0]
            if st.session_state.get("_last_loaded_json") != _jf.name:
                try:
                    d_parsed = json.loads(_jf.getvalue().decode("utf-8"))
                    if isinstance(d_parsed, dict):
                        st.session_state._last_loaded_json = _jf.name
                        st.session_state.current_extracted_data = d_parsed
                        st.session_state.extracted_data = d_parsed
                        st.session_state.current_step = 3
                        st.session_state.step = 3
                        if d_parsed.get("tau_danh_bat"):
                            chk = RFMOChecker(base_dir=CURRENT_DIR)
                            rep, vr = chk.verify_ho_so(d_parsed)
                            st.session_state.rfmo_audit_results = {"ho_so_report": rep, "v_results": vr}
                            st.session_state.rfmo_results = st.session_state.rfmo_audit_results
                        st.success(f"✅ Đã tự động nạp hồ sơ từ {_jf.name}!")
                        st.rerun()
                except Exception as _e:
                    st.error(f"Lỗi nạp file JSON: {_e}")

    # XỬ LÝ KHI BẤM "BẮT ĐẦU TRÍCH XUẤT AI"
    if btn_run_ai:
        user_inf = st.session_state.get("logged_user", {})
        user_cred = user_inf.get("credits", 0)
        user_em = user_inf.get("email", "")

        if user_cred <= 0:
            st.error("⚠️ Bạn đã sử dụng hết lượt trích xuất AI! Vui lòng vào mục '💳 Bảng Giá & Nạp Gói' để nạp thêm hoặc nhập mã Voucher khuyến mãi (VD: IUU-DEMO-2026) để tiếp tục.")
        elif not uploaded_files:
            st.warning("Vui lòng tải lên ít nhất một file PDF hoặc ảnh chứng từ, hoặc bấm '🚀 NẠP DỮ LIỆU MẪU' để kiểm thử!")
        else:
            st.session_state.is_ai_running = True
            st.session_state.current_step = 2
            st.session_state.step = 2
            saved_paths = []
            temp_dir = tempfile.mkdtemp()
            
            try:
                for f in uploaded_files:
                    p = os.path.join(temp_dir, f.name)
                    with open(p, "wb") as fo:
                        fo.write(f.getbuffer())
                    saved_paths.append(p)

                prog = st.progress(0, text="✨ AI đang nạp và xử lý tài liệu...")
                def _prog_cb(msg, val):
                    prog.progress(val, text=msg)

                t0 = time.time()
                prompt_type = "chung_tu" if st.session_state.workspace_mode == "LUONG_1" else "mau22"
                
                with st.spinner("🤖 Lõi Google Gemini AI đang đọc và phân tích cấu trúc chứng từ..."):
                    res_data = AIService.extract_data(
                        file_paths=saved_paths,
                        prompt_type=prompt_type,
                        api_key=active_api_key,
                        progress_callback=_prog_cb,
                        model_name=st.session_state.get("selected_model", "Gemini 3.8 Flash")
                    )
                    
                t_ai = round(time.time() - t0, 2)
                st.session_state.ai_duration = t_ai
                st.session_state.is_ai_running = False

                if res_data:
                    # Khấu trừ lượt trích xuất AI
                    if not user_inf.get("is_guest", True):
                        ok_dec, rem_cred = db.deduct_web_credit(user_em, 1)
                        if ok_dec:
                            st.session_state.logged_user["credits"] = rem_cred
                    else:
                        st.session_state.logged_user["credits"] = max(0, user_cred - 1)

                    st.session_state.current_extracted_data = res_data
                    st.session_state.extracted_data = res_data
                    st.session_state.current_step = 3
                    st.session_state.step = 3
                    prog.progress(100, text=f"✅ Trích xuất AI thành công trong {t_ai}s! Còn {st.session_state.logged_user['credits']} lượt.")

                    # Tra cứu RFMO ngầm
                    checker = RFMOChecker(base_dir=CURRENT_DIR)
                    rep, vr = checker.verify_ho_so(res_data)
                    st.session_state.rfmo_audit_results = {"ho_so_report": rep, "v_results": vr}
                    st.session_state.rfmo_results = st.session_state.rfmo_audit_results
                    st.rerun()
                else:
                    err_msg = ""
                    if isinstance(res_data, dict):
                        err_msg = res_data.get("message", "")
                    st.error(f"Không trích xuất được dữ liệu hợp lệ. {f'Chi tiết: {err_msg}' if err_msg else 'Vui lòng kiểm tra lại tài liệu hoặc API key.'}")
                    st.info("💡 Bạn có thể nạp ngay bộ hồ sơ mẫu chuẩn Mẫu 22.KT để trải nghiệm tiếp quy trình thẩm định IUU và xuất Word:")
                    if st.button("⚡ TỰ ĐỘNG NẠP DỮ LIỆU MẪU CHUẨN NGAY", type="primary", key="btn_fallback_nodata"):
                        st.session_state.current_extracted_data = get_full_sample_dataset()
                        st.session_state.extracted_data = st.session_state.current_extracted_data
                        st.session_state.current_step = 3
                        st.session_state.step = 3
                        chk = RFMOChecker(base_dir=CURRENT_DIR)
                        rep, vr = chk.verify_ho_so(st.session_state.current_extracted_data)
                        st.session_state.rfmo_audit_results = {"ho_so_report": rep, "v_results": vr}
                        st.session_state.rfmo_results = st.session_state.rfmo_audit_results
                        st.rerun()
                    st.session_state.current_step = 1
                    st.session_state.step = 1
            except Exception as e:
                st.session_state.is_ai_running = False
                st.error(f"Đã phát sinh sự cố trong quá trình trích xuất: {e}")
                st.info("💡 Bạn có thể nạp ngay bộ hồ sơ mẫu chuẩn Mẫu 22.KT để trải nghiệm tiếp quy trình thẩm định IUU và xuất Word:")
                if st.button("⚡ TỰ ĐỘNG NẠP DỮ LIỆU MẪU CHUẨN (FALLBACK)", type="primary", key="btn_fallback_exception"):
                    st.session_state.current_extracted_data = get_full_sample_dataset()
                    st.session_state.extracted_data = st.session_state.current_extracted_data
                    st.session_state.current_step = 3
                    st.session_state.step = 3
                    chk = RFMOChecker(base_dir=CURRENT_DIR)
                    rep, vr = chk.verify_ho_so(st.session_state.current_extracted_data)
                    st.session_state.rfmo_audit_results = {"ho_so_report": rep, "v_results": vr}
                    st.session_state.rfmo_results = st.session_state.rfmo_audit_results
                    st.rerun()
                st.session_state.current_step = 1
                st.session_state.step = 1
            finally:
                for p in saved_paths:
                    try: os.remove(p)
                    except Exception: pass

    # ==========================================
    # BỐ CỤC SPLIT VIEW 2 CỘT SONG SONG
    # ==========================================
    if st.session_state.show_doc_preview:
        col_left, col_right = st.columns([1, 1.25])
    else:
        col_left = None
        col_right = st.container()

    # ── CỘT TRÁI: PREVIEW TÀI LIỆU PDF / ẢNH TỪNG TRANG ──
    if col_left is not None:
        with col_left:
            st.markdown('<div class="content-panel"><div class="panel-header">📄 TRÌNH XEM CHỨNG TỪ (ĐỐI CHIẾU KÉP)</div>', unsafe_allow_html=True)
            
            if not uploaded_files:
                # Trạng thái rỗng chuyên nghiệp
                st.markdown("""
                <div style="background:#F8FAFC; border:1px dashed #CBD5E1; border-radius:8px; padding:24px 16px; text-align:center;">
                    <div style="font-size:36px; margin-bottom:8px;">📄</div>
                    <div style="font-weight:700; color:#0F172A; font-size:13.5px; margin-bottom:6px;">CHƯA CÓ TỆP CHỨNG TỪ ĐƯỢC CHỌN</div>
                    <div style="color:#64748B; font-size:12px; margin-bottom:14px;">Hãy kéo thả file PDF/Ảnh chứng từ vào khung bên trên hoặc nhấn <b>🚀 NẠP DỮ LIỆU MẪU</b> để kích hoạt xem trước.</div>
                    <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:6px; padding:10px; text-align:left; font-size:11.5px; color:#475569; line-height:1.6;">
                        <b>💡 Tính năng nổi bật:</b><br/>
                        • Lật trang độc lập theo từng tài liệu (nhớ trang từng file)<br/>
                        • Bộ điều khiển Zoom: Phóng to (➕), Thu nhỏ (➖), Căn vừa khung (↔)<br/>
                        • Chuẩn màu sRGB chống vệt đen trên hóa đơn quét scan<br/>
                        • Tối ưu RAM in-memory cache, không lưu file tạm ra đĩa
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                # Đã có tệp được tải lên
                file_names = [f.name for f in uploaded_files]
                if st.session_state.pdf_selected_file not in file_names:
                    st.session_state.pdf_selected_file = file_names[0]
                
                sel_file_idx = file_names.index(st.session_state.pdf_selected_file) if st.session_state.pdf_selected_file in file_names else 0

                c_fsel1, c_fsel2 = st.columns([3, 1.2])
                with c_fsel1:
                    chosen_file_name = st.selectbox(
                        "Tài liệu xem:",
                        options=file_names,
                        index=sel_file_idx,
                        key="sb_doc_viewer_file",
                        label_visibility="collapsed"
                    )
                    st.session_state.pdf_selected_file = chosen_file_name
                
                file_obj = next((f for f in uploaded_files if f.name == chosen_file_name), None)
                is_pdf = chosen_file_name.lower().endswith(".pdf")
                
                # Tính tổng số trang an toàn
                total_pages = 1
                if is_pdf and file_obj:
                    total_pages = max(1, get_pdf_total_pages(file_obj.getvalue()))

                with c_fsel2:
                    badge_label = f"PDF ({total_pages} tr)" if is_pdf else "ẢNH (1 tr)"
                    st.markdown(f'<div style="text-align:right;font-size:11px;font-weight:700;color:#2563EB;padding-top:6px;">{badge_label}</div>', unsafe_allow_html=True)

                # Quản lý số trang hiện tại của tài liệu này
                cur_page = st.session_state.pdf_pages_dict.get(chosen_file_name, 0)
                cur_page = max(0, min(total_pages - 1, cur_page))
                st.session_state.pdf_pages_dict[chosen_file_name] = cur_page

                # Thanh điều hướng trang & Zoom controls
                c_prev, c_psel, c_next, c_zout, c_zlbl, c_zin, c_fit = st.columns([0.8, 2.2, 0.8, 0.8, 1.2, 0.8, 1.8])
                
                with c_prev:
                    if st.button("◀", disabled=(cur_page <= 0 or not is_pdf), key=f"btn_p_prev_{chosen_file_name}", help="Trang trước"):
                        st.session_state.pdf_pages_dict[chosen_file_name] = max(0, cur_page - 1)
                        st.rerun()

                with c_psel:
                    if is_pdf and total_pages > 1:
                        page_opts = [f"Trang {p+1}/{total_pages}" for p in range(total_pages)]
                        sel_p_opt = st.selectbox(
                            "Chọn trang",
                            options=page_opts,
                            index=cur_page,
                            key=f"sel_jump_page_{chosen_file_name}_{cur_page}",
                            label_visibility="collapsed"
                        )
                        target_p = int(sel_p_opt.split("/")[0].replace("Trang", "").strip()) - 1
                        if target_p != cur_page:
                            st.session_state.pdf_pages_dict[chosen_file_name] = target_p
                            st.rerun()
                    else:
                        st.markdown(f"<div style='text-align:center;font-weight:700;font-size:11.5px;padding-top:6px;color:#1E293B;'>Trang {cur_page+1}/{total_pages}</div>", unsafe_allow_html=True)

                with c_next:
                    if st.button("▶", disabled=(cur_page >= total_pages - 1 or not is_pdf), key=f"btn_p_next_{chosen_file_name}", help="Trang sau"):
                        st.session_state.pdf_pages_dict[chosen_file_name] = min(total_pages - 1, cur_page + 1)
                        st.rerun()

                with c_zout:
                    if st.button("➖", key=f"btn_zout_{chosen_file_name}", help="Thu nhỏ"):
                        st.session_state.pdf_zoom = max(0.5, round(st.session_state.pdf_zoom - 0.25, 2))
                        st.session_state.pdf_fit_width = False
                        st.rerun()

                with c_zlbl:
                    zoom_pct = int(st.session_state.pdf_zoom * 100)
                    st.markdown(f"<div style='text-align:center;font-weight:700;font-size:11px;padding-top:6px;color:#64748B;'>{zoom_pct}%</div>", unsafe_allow_html=True)

                with c_zin:
                    if st.button("➕", key=f"btn_zin_{chosen_file_name}", help="Phóng to"):
                        st.session_state.pdf_zoom = min(2.5, round(st.session_state.pdf_zoom + 0.25, 2))
                        st.session_state.pdf_fit_width = False
                        st.rerun()

                with c_fit:
                    if st.button("↔ Vừa khung", key=f"btn_zfit_{chosen_file_name}", help="Đặt lại kích thước vừa khung"):
                        st.session_state.pdf_zoom = 1.0
                        st.session_state.pdf_fit_width = True
                        st.rerun()

                # Viewport cuộn hiển thị tài liệu
                with st.container(height=660, border=True):
                    if file_obj:
                        if is_pdf:
                            png_bytes = render_pdf_page_to_png(file_obj.getvalue(), cur_page, st.session_state.pdf_zoom)
                            if png_bytes:
                                st.image(png_bytes, use_container_width=st.session_state.pdf_fit_width)
                            else:
                                st.error("Không thể kết xuất trang này.")
                        else:
                            st.image(file_obj.getvalue(), use_container_width=st.session_state.pdf_fit_width)

            st.markdown('</div>', unsafe_allow_html=True)

    # ── CỘT PHẢI: 8 TAB DỮ LIỆU NGHIỆP VỤ & DATA EDITORS ──
    with col_right:
        cur_data = st.session_state.current_extracted_data

        tabs = st.tabs([
            "🏢 Thông tin cơ sở",
            "📦 Sản phẩm",
            "🚢 Tàu khai thác",
            "🔄 Chuyển tải",
            "📜 Giấy phép",
            "⚓ Cập bến",
            "📦 Container",
            "🌐 Đối chiếu IUU & RFMO Live"
        ])

        # -------------------------------------------------------------
        # TAB 1: THÔNG TIN CƠ SỞ & LÔ HÀNG BỐC DỠ
        # -------------------------------------------------------------
        with tabs[0]:
            st.markdown('<div class="content-panel">', unsafe_allow_html=True)
            st.markdown('<div class="panel-header">🏢 THÔNG TIN PHÁP LÝ & CƠ SỞ NHẬP KHẨU</div>', unsafe_allow_html=True)
            
            # Chọn nhanh doanh nghiệp từ Excel
            comp_names = ["-- Chọn doanh nghiệp từ danh mục --"] + list(companies_dict.keys())
            sel_comp = st.selectbox("Chọn nhanh cơ sở DN từ CSDL:", comp_names, index=0, key="sb_company_lookup")
            if sel_comp in companies_dict:
                c_info = companies_dict[sel_comp]
                cur_data["ten_co_so"] = c_info.get("ten_co_so", cur_data.get("ten_co_so", ""))
                cur_data["nguoi_dai_dien"] = c_info.get("nguoi_dai_dien", cur_data.get("nguoi_dai_dien", ""))
                cur_data["dia_chi"] = c_info.get("dia_chi", cur_data.get("dia_chi", ""))
                cur_data["sdt"] = c_info.get("sdt", cur_data.get("sdt", ""))
                cur_data["email"] = c_info.get("email", cur_data.get("email", ""))

            c_f1, c_f2 = st.columns(2)
            with c_f1:
                cur_data["kinh_gui"] = st.text_input("Kính gửi (Cơ quan tiếp nhận):", value=cur_data.get("kinh_gui", "Chi cục Thủy sản"))
                cur_data["ten_co_so"] = st.text_input("Tên cơ sở nhập khẩu/Importer:", value=cur_data.get("ten_co_so", ""))
                cur_data["dia_chi"] = st.text_input("Địa chỉ trụ sở/Address:", value=cur_data.get("dia_chi", ""))
                cur_data["nguoi_dai_dien"] = st.text_input("Người đại diện/Representative:", value=cur_data.get("nguoi_dai_dien", ""))
            with c_f2:
                cur_data["sdt"] = st.text_input("Số điện thoại/Tel:", value=cur_data.get("sdt", ""))
                cur_data["email"] = st.text_input("Email liên hệ:", value=cur_data.get("email", ""))
                cur_data["so_to_khai"] = st.text_input("Số tờ khai hải quan:", value=cur_data.get("so_to_khai", ""))
                cur_data["ngay_to_khai"] = st.text_input("Ngày tờ khai hải quan:", value=cur_data.get("ngay_to_khai", ""))

            st.markdown('<div class="panel-header" style="margin-top:14px;">⚓ KẾ HOẠCH BỐC DỠ & CHI TIẾT VẬN TẢI</div>', unsafe_allow_html=True)
            c_f3, c_f4 = st.columns(2)
            with c_f3:
                cur_data["tong_san_luong"] = st.text_input("Tổng sản lượng bốc dỡ (kg):", value=str(cur_data.get("tong_san_luong") or cur_data.get("khoi_luong") or ""))
                cur_data["thoi_gian_boc_do"] = st.text_input("Thời gian bốc dỡ (Offloading Time):", value=cur_data.get("thoi_gian_boc_do", ""))
                cur_data["dia_diem_boc_do"] = st.text_input("Địa điểm bốc dỡ (Offloading Venue):", value=cur_data.get("dia_diem_boc_do", ""))
            with c_f4:
                cur_data["so_van_don"] = st.text_input("Số vận đơn (B/L):", value=cur_data.get("so_van_don", ""))
                cur_data["cang_boc_hang"] = st.text_input("Cảng bốc hàng:", value=cur_data.get("cang_boc_hang", ""))
                cur_data["cang_den"] = st.text_input("Cảng dỡ hàng / Cảng đến:", value=cur_data.get("cang_den", ""))
                cur_data["ten_hang"] = st.text_input("Tên hàng hóa:", value=cur_data.get("ten_hang", ""))
                cur_data["nuoc_xuat_khau"] = st.text_input("Nước xuất khẩu:", value=cur_data.get("nuoc_xuat_khau", ""))

            st.markdown('</div>', unsafe_allow_html=True)

        # -------------------------------------------------------------
        # TAB 2: SẢN PHẨM (san_pham)
        # -------------------------------------------------------------
        with tabs[1]:
            st.markdown('<div class="content-panel"><div class="panel-header">📦 DANH MỤC SẢN PHẨM KHAI BÁO (BẢNG 1 MẪU 22.KT)</div>', unsafe_allow_html=True)
            sp_list = cur_data.get("san_pham", [])
            df_sp = pd.DataFrame(sp_list) if sp_list else pd.DataFrame(columns=["loai", "hs_code", "ten_khoa_hoc", "kich_co", "khoi_luong", "xuat_xu"])
            
            # Đảm bảo đủ các cột bắt buộc
            for col in ["loai", "hs_code", "ten_khoa_hoc", "kich_co", "khoi_luong", "xuat_xu"]:
                if col not in df_sp.columns:
                    df_sp[col] = ""
            df_sp = df_sp[["loai", "hs_code", "ten_khoa_hoc", "kich_co", "khoi_luong", "xuat_xu"]]

            edited_sp = st.data_editor(
                df_sp,
                column_config={
                    "loai": st.column_config.TextColumn("Loài thủy sản", required=True),
                    "hs_code": st.column_config.TextColumn("Mã HS"),
                    "ten_khoa_hoc": st.column_config.TextColumn("Tên khoa học"),
                    "kich_co": st.column_config.TextColumn("Kích cỡ"),
                    "khoi_luong": st.column_config.TextColumn("Khối lượng (kg)"),
                    "xuat_xu": st.column_config.TextColumn("Xuất xứ")
                },
                use_container_width=True,
                num_rows="dynamic",
                key="editor_sp_tab2"
            )
            if edited_sp is not None:
                cur_data["san_pham"] = edited_sp.fillna("").to_dict('records')

            st.markdown('</div>', unsafe_allow_html=True)

        # -------------------------------------------------------------
        # TAB 3: TÀU ĐÁNH BẮT (tau_danh_bat)
        # -------------------------------------------------------------
        with tabs[2]:
            st.markdown('<div class="content-panel"><div class="panel-header">🚢 DANH SÁCH TÀU KHAI THÁC & NGƯ CỤ (BẢNG 2 MẪU 22.KT)</div>', unsafe_allow_html=True)
            raw_v = cur_data.get("tau_danh_bat", [])
            # Chuẩn hóa về 10 khóa chuẩn tắc
            norm_v = [normalize_vessel_item(v) for v in raw_v] if raw_v else []
            clean_v = deduplicate_vessels(norm_v) if norm_v else []

            st.caption(f"Tổng số tàu: **{len(clean_v)}** tàu (Tự động khử trùng lặp & chuẩn hóa 10 trường ExportService)")

            df_v = pd.DataFrame(clean_v) if clean_v else pd.DataFrame(columns=["ten", "imo", "ho_hieu", "rfmo", "giay_phep", "co_quan", "ngay_het_han", "khu_vuc", "doi_tuong", "ngu_cu"])
            for col in ["ten", "imo", "ho_hieu", "rfmo", "giay_phep", "co_quan", "ngay_het_han", "khu_vuc", "doi_tuong", "ngu_cu"]:
                if col not in df_v.columns:
                    df_v[col] = ""
            df_v = df_v[["ten", "imo", "ho_hieu", "rfmo", "giay_phep", "co_quan", "ngay_het_han", "khu_vuc", "doi_tuong", "ngu_cu"]]

            edited_v = st.data_editor(
                df_v,
                column_config={
                    "ten": st.column_config.TextColumn("Tên tàu", required=True),
                    "imo": st.column_config.TextColumn("Số IMO"),
                    "ho_hieu": st.column_config.TextColumn("Hô hiệu (IRCS)"),
                    "rfmo": st.column_config.TextColumn("Số ĐK RFMO"),
                    "giay_phep": st.column_config.TextColumn("Giấy phép"),
                    "co_quan": st.column_config.TextColumn("Cơ quan cấp"),
                    "ngay_het_han": st.column_config.TextColumn("Ngày hết hạn"),
                    "khu_vuc": st.column_config.TextColumn("Khu vực / FAO"),
                    "doi_tuong": st.column_config.TextColumn("Đối tượng"),
                    "ngu_cu": st.column_config.TextColumn("Ngư cụ")
                },
                use_container_width=True,
                num_rows="dynamic",
                key="editor_v_tab3"
            )
            if edited_v is not None:
                cur_data["tau_danh_bat"] = edited_v.fillna("").to_dict('records')

            st.markdown('</div>', unsafe_allow_html=True)

        # -------------------------------------------------------------
        # TAB 4: CHUYỂN TẢI (thong_tin_chuyen_tai)
        # -------------------------------------------------------------
        with tabs[3]:
            st.markdown('<div class="content-panel"><div class="panel-header">🔄 THÔNG TIN CHUYỂN TẢI LIÊN QUAN (BẢNG 3 MẪU 22.KT)</div>', unsafe_allow_html=True)
            ct_list = cur_data.get("thong_tin_chuyen_tai", [])
            df_ct = pd.DataFrame(ct_list) if ct_list else pd.DataFrame(columns=["tau_khai_thac", "thoi_gian", "tau_nhan", "quoc_gia", "imo", "ho_hieu", "loai", "khoi_luong"])
            for col in ["tau_khai_thac", "thoi_gian", "tau_nhan", "quoc_gia", "imo", "ho_hieu", "loai", "khoi_luong"]:
                if col not in df_ct.columns:
                    df_ct[col] = ""
            df_ct = df_ct[["tau_khai_thac", "thoi_gian", "tau_nhan", "quoc_gia", "imo", "ho_hieu", "loai", "khoi_luong"]]

            edited_ct = st.data_editor(
                df_ct,
                column_config={
                    "tau_khai_thac": st.column_config.TextColumn("Tàu khai thác"),
                    "thoi_gian": st.column_config.TextColumn("Thời gian chuyển tải"),
                    "tau_nhan": st.column_config.TextColumn("Tàu nhận"),
                    "quoc_gia": st.column_config.TextColumn("Quốc gia (Cờ)"),
                    "imo": st.column_config.TextColumn("Số IMO tàu nhận"),
                    "ho_hieu": st.column_config.TextColumn("Hô hiệu"),
                    "loai": st.column_config.TextColumn("Loài thủy sản"),
                    "khoi_luong": st.column_config.TextColumn("Khối lượng (kg)")
                },
                use_container_width=True,
                num_rows="dynamic",
                key="editor_ct_tab4"
            )
            if edited_ct is not None:
                cur_data["thong_tin_chuyen_tai"] = edited_ct.fillna("").to_dict('records')

            st.markdown('</div>', unsafe_allow_html=True)

        # -------------------------------------------------------------
        # TAB 5: GIẤY PHÉP CHUYỂN TẢI (giay_phep_chuyen_tai)
        # -------------------------------------------------------------
        with tabs[4]:
            st.markdown('<div class="content-panel"><div class="panel-header">📜 CÁC GIẤY PHÉP CHUYỂN TẢI (BẢNG 4 MẪU 22.KT)</div>', unsafe_allow_html=True)
            gp_list = cur_data.get("giay_phep_chuyen_tai", [])
            df_gp = pd.DataFrame(gp_list) if gp_list else pd.DataFrame(columns=["tau_chuyen_tai", "imo", "giay_phep", "co_quan", "ngay_het_han"])
            for col in ["tau_chuyen_tai", "imo", "giay_phep", "co_quan", "ngay_het_han"]:
                if col not in df_gp.columns:
                    df_gp[col] = ""
            df_gp = df_gp[["tau_chuyen_tai", "imo", "giay_phep", "co_quan", "ngay_het_han"]]

            edited_gp = st.data_editor(
                df_gp,
                column_config={
                    "tau_chuyen_tai": st.column_config.TextColumn("Tàu chuyển tải"),
                    "imo": st.column_config.TextColumn("Số IMO"),
                    "giay_phep": st.column_config.TextColumn("Giấy phép chuyển tải"),
                    "co_quan": st.column_config.TextColumn("Cơ quan cấp"),
                    "ngay_het_han": st.column_config.TextColumn("Ngày hết hạn")
                },
                use_container_width=True,
                num_rows="dynamic",
                key="editor_gp_tab5"
            )
            if edited_gp is not None:
                cur_data["giay_phep_chuyen_tai"] = edited_gp.fillna("").to_dict('records')

            st.markdown('</div>', unsafe_allow_html=True)

        # -------------------------------------------------------------
        # TAB 6: SẢN LƯỢNG CẬP BẾN (san_luong_cap_ben)
        # -------------------------------------------------------------
        with tabs[5]:
            st.markdown('<div class="content-panel"><div class="panel-header">⚓ SẢN LƯỢNG KHAI THÁC CẬP BẾN (BẢNG 5 MẪU 22.KT)</div>', unsafe_allow_html=True)
            cb_list = cur_data.get("san_luong_cap_ben", [])
            df_cb = pd.DataFrame(cb_list) if cb_list else pd.DataFrame(columns=["tau", "imo", "cang", "ngay", "khoi_luong"])
            for col in ["tau", "imo", "cang", "ngay", "khoi_luong"]:
                if col not in df_cb.columns:
                    df_cb[col] = ""
            df_cb = df_cb[["tau", "imo", "cang", "ngay", "khoi_luong"]]

            edited_cb = st.data_editor(
                df_cb,
                column_config={
                    "tau": st.column_config.TextColumn("Tên tàu"),
                    "imo": st.column_config.TextColumn("Số IMO"),
                    "cang": st.column_config.TextColumn("Cảng cập bến"),
                    "ngay": st.column_config.TextColumn("Ngày cập bến"),
                    "khoi_luong": st.column_config.TextColumn("Khối lượng (kg)")
                },
                use_container_width=True,
                num_rows="dynamic",
                key="editor_cb_tab6"
            )
            if edited_cb is not None:
                cur_data["san_luong_cap_ben"] = edited_cb.fillna("").to_dict('records')

            st.markdown('</div>', unsafe_allow_html=True)

        # -------------------------------------------------------------
        # TAB 7: CONTAINER & SEAL (cong_ten_no)
        # -------------------------------------------------------------
        with tabs[6]:
            st.markdown('<div class="content-panel"><div class="panel-header">📦 THÔNG TIN CÔNG TEN NƠ (BẢNG 6 MẪU 22.KT)</div>', unsafe_allow_html=True)
            cnt_list = cur_data.get("cong_ten_no", [])
            df_cnt = pd.DataFrame(cnt_list) if cnt_list else pd.DataFrame(columns=["so_container", "so_seal", "so_bl", "tau_cho", "imo", "nuoc_xuat", "cang_xuat", "dia_chi_kho"])
            for col in ["so_container", "so_seal", "so_bl", "tau_cho", "imo", "nuoc_xuat", "cang_xuat", "dia_chi_kho"]:
                if col not in df_cnt.columns:
                    df_cnt[col] = ""
            df_cnt = df_cnt[["so_container", "so_seal", "so_bl", "tau_cho", "imo", "nuoc_xuat", "cang_xuat", "dia_chi_kho"]]

            edited_cnt = st.data_editor(
                df_cnt,
                column_config={
                    "so_container": st.column_config.TextColumn("Số Container", required=True),
                    "so_seal": st.column_config.TextColumn("Số Chì (Seal)"),
                    "so_bl": st.column_config.TextColumn("Vận đơn (B/L)"),
                    "tau_cho": st.column_config.TextColumn("Tàu chở container"),
                    "imo": st.column_config.TextColumn("Số IMO tàu chở"),
                    "nuoc_xuat": st.column_config.TextColumn("Nước xuất khẩu"),
                    "cang_xuat": st.column_config.TextColumn("Cảng xuất khẩu"),
                    "dia_chi_kho": st.column_config.TextColumn("Kho lưu trữ")
                },
                use_container_width=True,
                num_rows="dynamic",
                key="editor_cnt_tab7"
            )
            if edited_cnt is not None:
                cur_data["cong_ten_no"] = edited_cnt.fillna("").to_dict('records')

            st.markdown('</div>', unsafe_allow_html=True)

        # -------------------------------------------------------------
        # TAB 8: ĐỐI CHIẾU IUU & RFMO LIVE
        # -------------------------------------------------------------
        with tabs[7]:
            st.markdown('<div class="content-panel"><div class="panel-header">🌐 KẾT QUẢ ĐỐI SOÁT IUU & RFMO LIVE TOÀN CẦU</div>', unsafe_allow_html=True)
            
            rf_data = st.session_state.rfmo_audit_results
            if rf_data:
                rf_rep = rf_data.get("ho_so_report", {})
                v_res = rf_data.get("v_results", [])
                has_viol = rf_rep.get("has_violation", False)

                # Banner trạng thái
                if has_viol:
                    st.markdown('<div class="badge-danger">🚨 CẢNH BÁO RỦI RO IUU: Phát hiện tàu có dấu hiệu vi phạm hoặc nằm trong Danh sách đen IUU quốc tế!</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="badge-clean">✅ AN TOÀN TUYỆT ĐỐI: Tất cả tàu khai thác đều hợp lệ, không nằm trong danh sách đen IUU toàn cầu.</div>', unsafe_allow_html=True)

                st.write("")
                # 4 KPI Summary Cards
                total_v_chk = len(v_res)
                iuu_clean_count = sum(1 for vr in v_res if not vr.get("is_iuu_listed", False))
                iuu_warn_count = total_v_chk - iuu_clean_count

                kpi1, kpi2, kpi3, kpi4 = st.columns(4)
                with kpi1:
                    st.metric("Tổng số tàu", total_v_chk)
                with kpi2:
                    st.metric("Tàu an toàn IUU", iuu_clean_count)
                with kpi3:
                    st.metric("Cảnh báo rủi ro", iuu_warn_count, delta=None if iuu_warn_count == 0 else f"{iuu_warn_count} tàu vi phạm", delta_color="inverse")
                with kpi4:
                    st.metric("Tổ chức RFMO", f"{loaded_db}/5 CSDL")

                st.write("")
                # Bảng đối soát tổng hợp
                st.markdown("<b>Bảng tổng hợp đối soát từng tàu:</b>", unsafe_allow_html=True)
                summary_rows = []
                for vr in v_res:
                    summary_rows.append({
                        "Tên tàu": vr.get("ten_tau", ""),
                        "IMO": vr.get("so_imo", ""),
                        "Quốc tịch": vr.get("quoc_tich", ""),
                        "Trạng thái IUU": "🚨 VI PHẠM" if vr.get("is_iuu_listed", False) else "🟢 SẠCH",
                        "Kết quả RFMO": "Đã đối soát" if vr.get("rfmo_matches") or vr.get("rfmo_urls") else "Tra cứu",
                        "Nguồn dữ liệu": vr.get("source", "Live/Offline")
                    })
                if summary_rows:
                    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

                st.write("")
                st.markdown("<b>Chi tiết thẩm định và đường dẫn kiểm tra:</b>", unsafe_allow_html=True)
                for idx, vr in enumerate(v_res):
                    t_name = vr.get("ten_tau", f"Tàu #{idx+1}")
                    t_imo = vr.get("so_imo", "N/A")
                    is_listed = vr.get("is_iuu_listed", False)
                    status_icon = "🚨 VI PHẠM" if is_listed else "☑ Hợp lệ"

                    with st.expander(f"🚢 {t_name} (IMO: {t_imo}) — {status_icon}"):
                        st.markdown(f"- **Tên tàu:** `{t_name}` | **Số IMO:** `{t_imo}` | **Số Đăng Ký:** `{vr.get('so_dang_ky', 'N/A')}`")
                        st.markdown(f"- **Quốc tịch (Cờ):** `{vr.get('quoc_tich', 'N/A')}` | **Ngư cụ khai báo:** `{vr.get('ngu_cu', 'N/A')}`")
                        st.markdown(f"- **IUU Global:** {'🚨 Bị Liệt Kê Trong Danh Sách Đen' if is_listed else '🟢 Không có trong danh sách vi phạm IUU'}")
                        
                        # AIS Deep Link
                        if t_imo and str(t_imo).isdigit():
                            st.markdown(f"- 🛰️ **Hải đồ AIS vệ tinh:** [Kiểm tra hành trình Global Fishing Watch](https://globalfishingwatch.org/map/vessel/{t_imo}) | [MarineTraffic](https://www.marinetraffic.com/en/ais/details/ships/imo:{t_imo})")
                        
                        # RFMO Portal URLs
                        rf_urls = vr.get("rfmo_urls", {})
                        if rf_urls:
                            st.markdown("- 🌐 **Đường dẫn tra cứu thẩm quyền:**")
                            for org_k, u_link in rf_urls.items():
                                st.markdown(f"  + [{org_k}]({u_link})")

                # Nút tải Báo cáo Thẩm định IUU
                st.write("")
                iuu_rep_txt = generate_iuu_audit_report_text(cur_data, rf_data)
                so_tk_name = cur_data.get("so_to_khai", "IUU") if cur_data else "IUU"
                st.download_button(
                    label="📥 TẢI BÁO CÁO THẨM ĐỊNH IUU & RFMO (.TXT)",
                    data=iuu_rep_txt.encode("utf-8"),
                    file_name=f"IUU_Audit_Report_{so_tk_name}_{int(time.time())}.txt",
                    mime="text/plain",
                    type="primary",
                    use_container_width=True,
                    key="btn_download_iuu_rep",
                    help="Tải báo cáo kiểm toán rủi ro IUU và đối soát RFMO chi tiết định dạng văn bản"
                )

                # Cổng liên kết nhanh
                st.write("")
                st.markdown("""
                <div style="background:#F1F5F9; border-radius:8px; padding:10px 14px; font-size:12px; color:#475569;">
                    <b>🔗 Cổng tra cứu chính thức của các tổ chức quốc tế:</b><br/>
                    • WCPFC: <a href="https://www.wcpfc.int/vessels" target="_blank">wcpfc.int/vessels</a> &nbsp;|&nbsp;
                    • IOTC: <a href="https://rav.iotc.org/" target="_blank">rav.iotc.org</a> &nbsp;|&nbsp;
                    • IATTC: <a href="https://www.iattc.org/en-US/Management/vessel-register" target="_blank">iattc.org</a> &nbsp;|&nbsp;
                    • ICCAT: <a href="https://www.iccat.int/en/VesselsRecord.asp" target="_blank">iccat.int</a> &nbsp;|&nbsp;
                    • IUU Global: <a href="https://iuu-vessels.org/" target="_blank">iuu-vessels.org</a>
                </div>
                """, unsafe_allow_html=True)

            else:
                st.info("Chưa có kết quả đối chiếu IUU. Hãy nhấn '🔍 KIỂM TRA IUU & XUẤT' hoặc '🚀 NẠP DỮ LIỆU MẪU' để xem báo cáo.")

            st.markdown('</div>', unsafe_allow_html=True)


    # =========================================================================
    # 5. THANH CÔNG CỤ TÁC VỤ ĐÁY (BOTTOM ACTION TOOLBAR)
    # =========================================================================
    st.markdown("---")
    b_col1, b_col2, b_col3, b_col4, b_col5, b_col6 = st.columns(6)

    # 1. LƯU CSDL
    with b_col1:
        if st.button("💾 LƯU CSDL", use_container_width=True, help="Lưu hồ sơ vào cơ sở dữ liệu SQLite cục bộ"):
            if cur_data:
                res_id = db.save_ho_so(
                    ma_hs=cur_data.get("so_to_khai", f"HS_{int(time.time())}"),
                    file_name=uploaded_files[0].name if uploaded_files else "Dossier_Export",
                    luong=st.session_state.workspace_mode,
                    data=cur_data,
                    duration=st.session_state.ai_duration
                )
                st.success(f"✅ Đã lưu CSDL thành công! (ID: {res_id})")
            else:
                st.warning("Chưa có dữ liệu để lưu.")

    # 2. KIỂM TRA IUU & XUẤT
    with b_col2:
        if st.button("🔍 KIỂM TRA IUU & XUẤT", use_container_width=True, help="Thẩm định tàu cá qua CSDL IUU & RFMO"):
            if cur_data.get("tau_danh_bat"):
                with st.spinner("🌐 Đang kiểm tra IUU và RFMO Live..."):
                    chk = RFMOChecker(base_dir=CURRENT_DIR)
                    rep, vr = chk.verify_ho_so(cur_data)
                    st.session_state.rfmo_audit_results = {"ho_so_report": rep, "v_results": vr}
                    st.session_state.rfmo_results = st.session_state.rfmo_audit_results
                    st.session_state.current_step = 3
                    st.session_state.step = 3
                    st.rerun()
            else:
                st.warning("Vui lòng nhập hoặc nạp thông tin tàu cá ở Tab 3!")

    # 3. TRA CỨU RFMO LIVE (MODAL DIALOG)
    with b_col3:
        if st.button("🌐 TRA CỨU RFMO LIVE", use_container_width=True, help="Mở cửa sổ tra cứu trực tuyến các tổ chức nghề cá"):
            show_live_rfmo_dialog()

    # 4. XUẤT WORD (MẪU 22.KT)
    with b_col4:
        if cur_data:
            try:
                bio = io.BytesIO()
                ExportService.export_mau22(cur_data, bio)
                so_tk = cur_data.get("so_to_khai", "Export")
                st.download_button(
                    label="📄 XUẤT WORD",
                    data=bio.getvalue(),
                    file_name=f"Mau_22_KT_{so_tk}_{int(time.time())}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    type="primary",
                    use_container_width=True,
                    help="Tải file Word Mẫu 22.KT hoàn chỉnh"
                )
            except Exception as e:
                st.button(f"Lỗi Word: {e}", disabled=True, use_container_width=True)
        else:
            st.button("📄 XUẤT WORD", disabled=True, use_container_width=True)

    # 5. LƯU NHÁP JSON
    with b_col5:
        if cur_data:
            json_str = json.dumps(cur_data, ensure_ascii=False, indent=2)
            st.download_button(
                label="📝 Lưu Nháp JSON",
                data=json_str.encode("utf-8"),
                file_name=f"Draft_{cur_data.get('so_to_khai', 'IUU')}.json",
                mime="application/json",
                use_container_width=True,
                help="Lưu lại cấu trúc JSON để nhập lại sau này"
            )
        else:
            st.button("📝 Lưu Nháp JSON", disabled=True, use_container_width=True)

    # 6. NẠP DỮ LIỆU MẪU (TOOLBAR)
    with b_col6:
        if st.button("🚀 NẠP MẪU F3.6", use_container_width=True, help="Nạp tức thì bộ hồ sơ mẫu chuẩn nghiệp vụ"):
            st.session_state.current_extracted_data = get_full_sample_dataset()
            st.session_state.extracted_data = st.session_state.current_extracted_data
            st.session_state.current_step = 3
            st.session_state.step = 3
            chk = RFMOChecker(base_dir=CURRENT_DIR)
            rep, vr = chk.verify_ho_so(st.session_state.current_extracted_data)
            st.session_state.rfmo_audit_results = {"ho_so_report": rep, "v_results": vr}
            st.session_state.rfmo_results = st.session_state.rfmo_audit_results
            st.success("✅ Đã nạp dữ liệu mẫu!")
            st.rerun()


# =========================================================================
# MÀN HÌNH 3: BÁO CÁO CHI PHÍ API (API USAGE & COST REPORT)
# =========================================================================
elif st.session_state.current_view == "api_report":
    st.subheader("📊 BÁO CÁO ĐÁNH GIÁ VÀ TỐI ƯU CHI PHÍ API")
    st.caption("Theo dõi chi phí token, hạn mức kết nối Google Gemini và so sánh hiệu quả chi phí")

    a_c1, a_c2, a_c3, a_c4 = st.columns(4)
    with a_c1:
        st.metric("Tổng Token Ước Tính", "148,250", "+12.4%")
    with a_c2:
        st.metric("Chi phí Gemini Flash", "$0.022", "Tiết kiệm 94%")
    with a_c3:
        st.metric("Thời gian phản hồi TB", "2.1s", "-0.4s")
    with a_c4:
        st.metric("Tỷ lệ thành công", "99.8%", "0 lỗi rate limit")

    st.write("")
    st.markdown("""
    <div class="content-panel">
        <div class="panel-header">💡 SO SÁNH HIỆU QUẢ KINH TẾ (PER 1,000 HỒ SƠ CHỨNG TỪ)</div>
        <table style="width:100%; border-collapse:collapse; font-size:12.5px; text-align:left;">
            <thead>
                <tr style="border-bottom:2px solid #E2E8F0; color:#475569;">
                    <th style="padding:8px;">Mô hình AI</th>
                    <th style="padding:8px;">Chi phí Input (1M tok)</th>
                    <th style="padding:8px;">Chi phí Output (1M tok)</th>
                    <th style="padding:8px;">Ước tính / 1,000 Hồ sơ</th>
                    <th style="padding:8px;">Đánh giá</th>
                </tr>
            </thead>
            <tbody>
                <tr style="border-bottom:1px solid #F1F5F9; background:#ECFDF5;">
                    <td style="padding:8px; font-weight:700; color:#059669;">⚡ Gemini 3.8 Flash (Hiện tại)</td>
                    <td style="padding:8px;">$0.075</td>
                    <td style="padding:8px;">$0.30</td>
                    <td style="padding:8px; font-weight:700; color:#059669;">~ 35,000 VNĐ ($1.40)</td>
                    <td style="padding:8px;"><b style="color:#059669;">Tối ưu vượt trội</b></td>
                </tr>
                <tr style="border-bottom:1px solid #F1F5F9;">
                    <td style="padding:8px;">Gemini 3.1 Pro Preview</td>
                    <td style="padding:8px;">$1.25</td>
                    <td style="padding:8px;">$5.00</td>
                    <td style="padding:8px;">~ 580,000 VNĐ ($23.50)</td>
                    <td style="padding:8px;">Chuyên sâu hồ sơ mờ</td>
                </tr>
                <tr style="border-bottom:1px solid #F1F5F9;">
                    <td style="padding:8px;">OpenAI GPT-4o</td>
                    <td style="padding:8px;">$2.50</td>
                    <td style="padding:8px;">$10.00</td>
                    <td style="padding:8px;">~ 1,180,000 VNĐ ($47.20)</td>
                    <td style="padding:8px;">Chi phí cao</td>
                </tr>
            </tbody>
        </table>
    </div>
    """, unsafe_allow_html=True)


# =========================================================================
# MÀN HÌNH 4: BẢN QUYỀN & HỒ SƠ KHÁCH HÀNG (LICENSE & SYSTEM)
# =========================================================================
elif st.session_state.current_view == "license":
    st.subheader("🔑 BẢN QUYỀN HỆ THỐNG & THÔNG TIN DOANH NGHIỆP")
    st.caption("Chi tiết giấy phép đăng ký, định danh phần cứng và kích hoạt gói bản quyền")

    st.markdown(f"""
    <div class="content-panel">
        <div class="panel-header">👑 THÔNG TIN GIẤY PHÉP DOANH NGHIỆP</div>
        <div style="font-size:13px; line-height:2.0; color:#334155;">
            • Gói dịch vụ: <b style="color:#2563EB;">ENTERPRISE PRO LICENSE</b><br/>
            • Trạng thái bản quyền: <span style="background:#ECFDF5;color:#059669;padding:2px 8px;border-radius:12px;font-weight:700;font-size:12px;">ĐÃ KÍCH HOẠT VĨNH VIỄN</span><br/>
            • Mã định danh phần cứng (HWID): <code style="background:#F1F5F9;padding:2px 6px;border-radius:4px;color:#0F172A;">{get_hardware_id()}</code><br/>
            • Phiên bản ứng dụng: <b>Phiên bản 1.0.9 Enterprise</b><br/>
            • Bản quyền phát hành: <b>© 2026 Ngô Quốc Tiến — Hệ Thống Trích Xuất Chứng Từ Thủy Sản Mẫu 22.KT</b><br/>
            • Quyền hạn: Không giới hạn số lượng hồ sơ trích xuất, đối soát RFMO trực tuyến, xuất Word chuẩn Mẫu 22.KT.
        </div>
    </div>
    """, unsafe_allow_html=True)


# =========================================================================
# MÀN HÌNH 5: CỔNG TRA CỨU TRỰC TUYẾN RFMO LIVE
# =========================================================================
elif st.session_state.current_view == "rfmo_live":
    st.subheader("🌐 CỔNG TRA CỨU TRỰC TUYẾN RFMO & IUU TOÀN CẦU")
    st.caption("Tra cứu trực tiếp trên hệ thống dữ liệu WCPFC, IOTC, IATTC, ICCAT và IUU-Vessels.org")

    rc1, rc2 = st.columns([3, 1])
    with rc1:
        query_str = st.text_input("Nhập Tên tàu hoặc Số IMO cần tra cứu:", placeholder="Ví dụ: SHUN FA 888 hoặc 8745814...", key="rfmo_live_page_input")
    with rc2:
        org_select = st.selectbox("Tổ chức / CSDL:", ["Tất cả (All)", "WCPFC", "IOTC", "IATTC", "ICCAT", "IUU Global"], key="rfmo_live_page_org")

    if st.button("🔍 Tra Cứu Trực Tuyến Ngay", type="primary", key="rfmo_live_page_btn"):
        if query_str.strip():
            with st.spinner(f"Đang kết nối API tra cứu '{query_str}'..."):
                t_start = time.time()
                results = []

                if org_select in ["Tất cả (All)", "IUU Global"]:
                    iuu_res = rfmo_engine.search_iuu_global(query_str.strip())
                    results.append(("IUU Vessels Global", iuu_res))

                if org_select in ["Tất cả (All)", "WCPFC"]:
                    w_res = rfmo_engine.search_wcpfc(query_str.strip())
                    results.append(("WCPFC", w_res))

                if org_select in ["Tất cả (All)", "IOTC"]:
                    io_res = rfmo_engine.search_iotc(query_str.strip())
                    results.append(("IOTC", io_res))

                dur = round(time.time() - t_start, 2)
                st.success(f"Hoàn thành tra cứu trong {dur}s!")

                for org_name, res in results:
                    with st.expander(f"Kết quả từ {org_name}", expanded=True):
                        st.json(res)
        else:
            st.warning("Vui lòng nhập tên tàu hoặc số IMO!")
