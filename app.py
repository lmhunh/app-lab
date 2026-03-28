import streamlit as st
import pandas as pd
import gspread
import json
from datetime import datetime

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="Hệ thống Quản lý Lab", layout="wide")

# --- KẾT NỐI GOOGLE SHEETS (SIÊU BẢO MẬT) ---
def connect_to_gsheets():
    try:
        # 1. Ưu tiên đọc từ Secrets (Két sắt)
        if "my_creds" in st.secrets:
            creds_data = st.secrets["my_creds"]
            
            # Nếu là chuỗi JSON, chuyển thành Dictionary
            if isinstance(creds_data, str):
                # Tự động sửa lỗi dấu xuống dòng trong mã khóa
                fixed_json = creds_data.replace("\\n", "\n")
                creds_dict = json.loads(fixed_json, strict=False)
            else:
                creds_dict = dict(creds_data)
            
            # Ép kiểu lại private_key lần cuối cho chắc chắn
            if "private_key" in creds_dict:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
                
            return gspread.service_account_from_dict(creds_dict)
        else:
            # 2. Dự phòng nếu chạy ở máy tính (local)
            return gspread.service_account(filename='credentials.json')
    except Exception as e:
        st.error(f"❌ Lỗi cấu hình chìa khóa: {e}")
        st.stop()

# Khởi tạo kết nối
try:
    gc = connect_to_gsheets()
    sh = gc.open("Quan_ly_lab")
    sheet_thietbi = sh.worksheet("ThietBi")
    sheet_lichsu = sh.worksheet("LichSu")
    sheet_taikhoan = sh.worksheet("TaiKhoan")
except Exception as e:
    st.error(f"❌ Lỗi kết nối Google Sheets: {e}")
    st.stop()

# --- PHẦN LOGIN VÀ GIAO DIỆN (GIỮ NGUYÊN) ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['ho_ten'] = ""

if not st.session_state['logged_in']:
    st.title("🔐 Đăng nhập Hệ thống Lab")
    with st.form("login"):
        u = st.text_input("Tài khoản")
        p = st.text_input("Mật khẩu", type="password")
        if st.form_submit_button("Đăng nhập"):
            df_tk = pd.DataFrame(sheet_taikhoan.get_all_records())
            match = df_tk[(df_tk['TaiKhoan'].astype(str) == str(u)) & (df_tk['MatKhau'].astype(str) == str(p))]
            if not match.empty:
                st.session_state['logged_in'] = True
                st.session_state['ho_ten'] = match.iloc[0]['HoTen']
                st.rerun()
            else: st.error("Sai tài khoản hoặc mật khẩu!")
else:
    # Giao diện quản lý chính
    st.title(f"🧪 Chào mừng {st.session_state['ho_ten']}!")
    if st.button("Đăng xuất"):
        st.session_state['logged_in'] = False
        st.rerun()
    
    # Hiển thị các Tab mượn trả như bình thường...
    tab1, tab2 = st.tabs(["📊 Danh sách", "🔄 Mượn/Trả"])
    with tab1:
        df = pd.DataFrame(sheet_thietbi.get_all_records())
        st.dataframe(df, use_container_width=True, hide_index=True)