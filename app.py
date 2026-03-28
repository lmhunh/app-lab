import streamlit as st
import pandas as pd
import gspread
from datetime import datetime
import json

# --- 1. CẤU HÌNH TRANG ---
st.set_page_config(page_title="Hệ thống Quản lý Lab", layout="wide")

# --- 2. HÀM TẢI DỮ LIỆU ---
def load_data(sheet):
    data = sheet.get_all_records()
    return pd.DataFrame(data)

# --- 3. KẾT NỐI GOOGLE SHEETS ---
@st.cache_resource
def connect_to_gsheets():
    try:
        # Ưu tiên đọc từ Secrets (Dạng JSON string)
        if "google_sheets_creds" in st.secrets:
            creds_info = json.loads(st.secrets["google_sheets_creds"])
            # Vá lỗi ký tự xuống dòng cho mã khóa bí mật
            if "private_key" in creds_info:
                creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
            gc = gspread.service_account_from_dict(creds_info)
        # Dự phòng đọc từ file nội bộ (chạy máy cá nhân)
        else:
            gc = gspread.service_account(filename='credentials.json')
            
        return gc
    except Exception as e:
        st.error(f"❌ Lỗi cấu hình chìa khóa: {e}")
        st.stop()

# Khởi tạo các sheet
try:
    gc = connect_to_gsheets()
    sh = gc.open("Quan_ly_lab") # Đảm bảo tên file khớp 100% trên Drive
    sheet_thietbi = sh.worksheet("ThietBi")
    sheet_lichsu = sh.worksheet("LichSu")
    sheet_taikhoan = sh.worksheet("TaiKhoan")
except Exception as e:
    st.error(f"❌ Lỗi kết nối Google Sheets: {e}")
    st.stop()

# --- 4. KIỂM TRA TRẠNG THÁI ĐĂNG NHẬP ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['ho_ten'] = ""

# ==========================================
# GIAO DIỆN ĐĂNG NHẬP
# ==========================================
if not st.session_state['logged_in']:
    st.title("🔐 Đăng nhập Hệ thống Lab")
    with st.form("login_form"):
        username = st.text_input("Tài khoản")
        password = st.text_input("Mật khẩu", type="password")
        submit_login = st.form_submit_button("Đăng nhập")

        if submit_login:
            df_tk = load_data(sheet_taikhoan)
            # So khớp tài khoản và mật khẩu
            match = df_tk[(df_tk['TaiKhoan'].astype(str) == str(username)) & 
                          (df_tk['MatKhau'].astype(str) == str(password))]

            if not match.empty:
                st.session_state['logged_in'] = True
                st.session_state['ho_ten'] = match.iloc[0]['HoTen']
                st.rerun()
            else:
                st.error("❌ Sai tài khoản hoặc mật khẩu!")

# ==========================================
# GIAO DIỆN CHÍNH (SAU KHI ĐĂNG NHẬP)
# ==========================================
else:
    col_title, col_logout = st.columns([8, 2])
    with col_title:
        st.title("🧪 Phần mềm Quản lý Thiết bị Lab")
    with col_logout:
        st.write(f"👤 Chào, **{st.session_state['ho_ten']}**")
        if st.button("🚪 Đăng xuất"):
            st.session_state['logged_in'] = False
            st.rerun()

    st.markdown("---")
    df = load_data(sheet_thietbi)
    tab1, tab2, tab3 = st.tabs(["📊 Trạng thái thiết bị", "🔄 Mượn / Trả", "🕒 Lịch sử"])

    # TAB 1: TRẠNG THÁI
    with tab1:
        st.subheader("Danh sách thiết bị hiện tại")
        def color_status(val):
            color = 'red' if val == 'Hỏng' else ('orange' if val == 'Đang mượn' else 'green')
            return f'color: {color}'
        
        if not df.empty:
            st.dataframe(df.style.map(color_status, subset=['Trạng thái']), use_container_width=True, hide_index=True)
        else:
            st.info("Chưa có dữ liệu thiết bị.")

    # TAB 2: MƯỢN TRẢ
    with tab2:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Đăng ký Mượn")
            ready_devices = df[df['Trạng thái'] == 'Sẵn sàng']['Tên'].tolist() if not df.empty else []
            with st.form("borrow_form"):
                selected_device = st.selectbox("Chọn thiết bị", ready_devices)
                note = st.text_input("Ghi chú mượn")
                if st.form_submit_button("Xác nhận Mượn"):
                    if selected_device:
                        cell = sheet_thietbi.find(selected_device)
                        sheet_thietbi.update_cell(cell.row, 3, "Đang mượn")
                        sheet_thietbi.update_cell(cell.row, 4, st.session_state['ho_ten'])
                        sheet_thietbi.update_cell(cell.row, 5, note)
                        
                        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                        sheet_lichsu.append_row([now, st.session_state['ho_ten'], "Mượn", selected_device])
                        st.success(f"✅ Đã mượn {selected_device}")
                        st.rerun()

        with col2:
            st.subheader("Đăng ký Trả")
            borrowed_devices = df[df['Trạng thái'] == 'Đang mượn']['Tên'].tolist() if not df.empty else []
            with st.form("return_form"):
                return_device = st.selectbox("Chọn thiết bị trả", borrowed_devices)
                if st.form_submit_button("Xác nhận Trả"):
                    if return_device:
                        cell = sheet_thietbi.find(return_device)
                        sheet_thietbi.update_cell(cell.row, 3, "Sẵn sàng")
                        sheet_thietbi.update_cell(cell.row, 4, "")
                        sheet_thietbi.update_cell(cell.row, 5, "Đã trả")
                        
                        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                        sheet_lichsu.append_row([now, st.session_state['ho_ten'], "Trả", return_device])
                        st.success(f"✅ Đã trả {return_device}")
                        st.rerun()

    # TAB 3: LỊCH SỬ
    with tab3:
        st.subheader("Lịch sử giao dịch gần đây")
        history_data = load_data(sheet_lichsu)
        if not history_data.empty:
            # Hiển thị lịch sử mới nhất lên đầu
            st.dataframe(history_data.iloc[::-1], use_container_width=True, hide_index=True)
        else:
            st.info("Chưa có lịch sử giao dịch.")