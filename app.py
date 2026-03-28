import streamlit as st
import pandas as pd
import gspread
from datetime import datetime
import json
import base64

# --- 1. CẤU HÌNH TRANG ---
st.set_page_config(page_title="Hệ thống Quản lý Lab", layout="wide")

# --- 2. HÀM GIẢI MÃ VÀ KẾT NỐI ---
def get_gspread_client():
    try:
        # Ưu tiên cách Base64 vì nó cực kỳ ổn định
        if "BASE64_CREDS" in st.secrets:
            b64_str = st.secrets["BASE64_CREDS"]
            decoded_data = base64.b64decode(b64_str).decode('utf-8')
            creds_dict = json.loads(decoded_data)
            
            # Tự động sửa lỗi dấu xuống dòng trong private_key
            if "private_key" in creds_dict:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            
            return gspread.service_account_from_dict(creds_dict)
        else:
            # Dự phòng chạy ở máy tính cá nhân
            return gspread.service_account(filename='credentials.json')
    except Exception as e:
        st.error(f"❌ Lỗi giải mã chìa khóa: {e}")
        st.stop()

# --- 3. KHỞI TẠO KẾT NỐI ---
try:
    gc = get_gspread_client()
    sh = gc.open("Quan_ly_lab")
    sheet_thietbi = sh.worksheet("ThietBi")
    sheet_lichsu = sh.worksheet("LichSu")
    sheet_taikhoan = sh.worksheet("TaiKhoan") 
except Exception as e:
    st.error(f"❌ Lỗi kết nối Google Sheets: {e}")
    st.stop()

# --- 4. HÀM TẢI DỮ LIỆU ---
def load_data(sheet):
    data = sheet.get_all_records()
    return pd.DataFrame(data)

# --- 5. HỆ THỐNG ĐĂNG NHẬP ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['ho_ten'] = ""

if not st.session_state['logged_in']:
    st.title("🔐 Đăng nhập Hệ thống Lab")
    with st.form("login_form"):
        u = st.text_input("Tài khoản")
        p = st.text_input("Mật khẩu", type="password")
        if st.form_submit_button("Đăng nhập"):
            df_tk = load_data(sheet_taikhoan)
            match = df_tk[(df_tk['TaiKhoan'].astype(str) == str(u)) & 
                          (df_tk['MatKhau'].astype(str) == str(p))]
            if not match.empty:
                st.session_state['logged_in'] = True
                st.session_state['ho_ten'] = match.iloc[0]['HoTen']
                st.rerun()
            else:
                st.error("Sai tài khoản hoặc mật khẩu!")
else:
    # --- GIAO DIỆN CHÍNH ---
    col1, col2 = st.columns([8, 2])
    with col1: st.title("🧪 Quản lý Thiết bị Lab")
    with col2: 
        st.write(f"👤 {st.session_state['ho_ten']}")
        if st.button("Đăng xuất"):
            st.session_state['logged_in'] = False
            st.rerun()

    df = load_data(sheet_thietbi)
    tab1, tab2, tab3 = st.tabs(["📊 Trạng thái", "🔄 Mượn/Trả", "🕒 Lịch sử"])

    with tab1:
        st.subheader("Danh sách thiết bị")
        if not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)

    with tab2:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Đăng ký Mượn")
            ready = df[df['Trạng thái'] == 'Sẵn sàng']['Tên'].tolist() if not df.empty else []
            with st.form("bm"):
                d = st.selectbox("Chọn thiết bị", ready)
                n = st.text_input("Ghi chú")
                if st.form_submit_button("Xác nhận Mượn"):
                    if d:
                        row = sheet_thietbi.find(d).row
                        sheet_thietbi.update_cell(row, 3, "Đang mượn")
                        sheet_thietbi.update_cell(row, 4, st.session_state['ho_ten'])
                        sheet_thietbi.update_cell(row, 5, n)
                        sheet_lichsu.append_row([datetime.now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], "Mượn", d])
                        st.success(f"Đã mượn {d}"); st.rerun()

        with c2:
            st.subheader("Đăng ký Trả")
            borrowed = df[df['Trạng thái'] == 'Đang mượn']['Tên'].tolist() if not df.empty else []
            with st.form("rt"):
                d_t = st.selectbox("Thiết bị trả", borrowed)
                if st.form_submit_button("Xác nhận Trả"):
                    if d_t:
                        row = sheet_thietbi.find(d_t).row
                        sheet_thietbi.update_cell(row, 3, "Sẵn sàng")
                        sheet_thietbi.update_cell(row, 4, "")
                        sheet_thietbi.update_cell(row, 5, "Đã trả")
                        sheet_lichsu.append_row([datetime.now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], "Trả", d_t])
                        st.success(f"Đã trả {d_t}"); st.rerun()

    with tab3:
        st.subheader("Lịch sử")
        his = load_data(sheet_lichsu)
        if not his.empty: st.dataframe(his.iloc[::-1], use_container_width=True, hide_index=True)