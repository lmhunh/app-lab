import streamlit as st
import pandas as pd
import gspread
from datetime import datetime

# --- 1. CẤU HÌNH TRANG ---
st.set_page_config(page_title="Hệ thống Quản lý Lab", layout="wide")

# --- 2. KẾT NỐI GOOGLE SHEETS ---
def connect_to_gsheets():
    try:
        # Lấy dữ liệu từ mục [my_creds] trong Secrets (dạng TOML)
        creds_dict = dict(st.secrets["my_creds"])
        
        # Sửa lỗi ký tự xuống dòng của mã khóa bí mật
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        
        return gspread.service_account_from_dict(creds_dict)
    except Exception as e:
        st.error(f"❌ Lỗi cấu hình Secrets: {e}")
        st.info("Kiểm tra lại định dạng TOML trong mục Secrets trên Streamlit Cloud.")
        st.stop()

# Khởi tạo kết nối và các Sheet
try:
    gc = connect_to_gsheets()
    # Mở file Sheets (Hãy đảm bảo tên này đúng 100% với tên trên Google Drive)
    sh = gc.open("Quan_ly_lab") 
    sheet_thietbi = sh.worksheet("ThietBi")
    sheet_lichsu = sh.worksheet("LichSu")
    sheet_taikhoan = sh.worksheet("TaiKhoan")
except Exception as e:
    st.error(f"❌ Lỗi kết nối Google Sheets: {e}")
    st.stop()

# --- 3. QUẢN LÝ ĐĂNG NHẬP ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['ho_ten'] = ""

def load_data(sheet):
    data = sheet.get_all_records()
    return pd.DataFrame(data)

# ==========================================
# GIAO DIỆN ĐĂNG NHẬP
# ==========================================
if not st.session_state['logged_in']:
    st.title("🔐 Đăng nhập Hệ thống Lab")
    with st.form("login_form"):
        u = st.text_input("Tài khoản")
        p = st.text_input("Mật khẩu", type="password")
        if st.form_submit_button("Đăng nhập"):
            df_tk = load_data(sheet_taikhoan)
            # Kiểm tra tài khoản
            match = df_tk[(df_tk['TaiKhoan'].astype(str) == str(u)) & 
                          (df_tk['MatKhau'].astype(str) == str(p))]
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
    col_t, col_l = st.columns([8, 2])
    with col_t:
        st.title(f"🧪 Chào mừng {st.session_state['ho_ten']}!")
    with col_l:
        if st.button("🚪 Đăng xuất"):
            st.session_state['logged_in'] = False
            st.rerun()

    st.markdown("---")
    
    # Tải dữ liệu thiết bị
    df = load_data(sheet_thietbi)
    tab1, tab2, tab3 = st.tabs(["📊 Trạng thái", "🔄 Mượn/Trả", "🕒 Lịch sử"])

    # TAB 1: DANH SÁCH THIẾT BỊ
    with tab1:
        st.subheader("Danh sách thiết bị hiện tại")
        def color_status(val):
            color = 'red' if val == 'Hỏng' else ('orange' if val == 'Đang mượn' else 'green')
            return f'color: {color}'
        
        if not df.empty:
            st.dataframe(df.style.map(color_status, subset=['Trạng thái']), use_container_width=True, hide_index=True)

    # TAB 2: MƯỢN VÀ TRẢ
    with tab2:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Đăng ký Mượn")
            ready_list = df[df['Trạng thái'] == 'Sẵn sàng']['Tên'].tolist() if not df.empty else []
            with st.form("borrow_form"):
                dev_m = st.selectbox("Chọn thiết bị", ready_list)
                note_m = st.text_input("Ghi chú")
                if st.form_submit_button("Xác nhận Mượn"):
                    if dev_m:
                        cell = sheet_thietbi.find(dev_m)
                        sheet_thietbi.update_cell(cell.row, 3, "Đang mượn")
                        sheet_thietbi.update_cell(cell.row, 4, st.session_state['ho_ten'])
                        sheet_thietbi.update_cell(cell.row, 5, note_m)
                        # Ghi lịch sử
                        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                        sheet_lichsu.append_row([now, st.session_state['ho_ten'], "Mượn", dev_m])
                        st.success(f"✅ Đã mượn: {dev_m}")
                        st.rerun()

        with c2:
            st.subheader("Đăng ký Trả")
            borrowed_list = df[df['Trạng thái'] == 'Đang mượn']['Tên'].tolist() if not df.empty else []
            with st.form("return_form"):
                dev_t = st.selectbox("Thiết bị cần trả", borrowed_list)
                if st.form_submit_button("Xác nhận Trả"):
                    if dev_t:
                        cell = sheet_thietbi.find(dev_t)
                        sheet_thietbi.update_cell(cell.row, 3, "Sẵn sàng")
                        sheet_thietbi.update_cell(cell.row, 4, "")
                        sheet_thietbi.update_cell(cell.row, 5, "Đã trả")
                        # Ghi lịch sử
                        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                        sheet_lichsu.append_row([now, st.session_state['ho_ten'], "Trả", dev_t])
                        st.success(f"✅ Đã trả: {dev_t}")
                        st.rerun()

    # TAB 3: LỊCH SỬ
    with tab3:
        st.subheader("Lịch sử giao dịch")
        history = load_data(sheet_lichsu)
        if not history.empty:
            st.dataframe(history.iloc[::-1], use_container_width=True, hide_index=True)