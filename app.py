import streamlit as st
import pandas as pd
import gspread
from datetime import datetime
import json
import base64  # Thêm thư viện này

# --- 1. CẤU HÌNH TRANG ---
st.set_page_config(page_title="Hệ thống Quản lý Lab", layout="wide")

# --- 2. HÀM KẾT NỐI SIÊU CẤP (DÙNG BASE64) ---
def get_gspread_client():
    try:
        # Nếu dùng cách mã hóa Base64 (Cách an toàn nhất)
        if "google_sheets_creds_base64" in st.secrets:
            base64_str = st.secrets["google_sheets_creds_base64"]
            # Giải mã chuỗi Base64 về dạng JSON ban đầu
            decoded_bytes = base64.b64decode(base64_str)
            creds_dict = json.loads(decoded_bytes)
            return gspread.service_account_from_dict(creds_dict)
            
        # Cách dự phòng (Dán trực tiếp JSON)
        elif "google_sheets_creds" in st.secrets:
            raw_creds = st.secrets["google_sheets_creds"]
            creds_dict = json.loads(raw_creds) if isinstance(raw_creds, str) else dict(raw_creds)
            if "private_key" in creds_dict:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            return gspread.service_account_from_dict(creds_dict)
            
        else:
            return gspread.service_account(filename='credentials.json')
    except Exception as e:
        st.error(f"❌ Lỗi cấu hình chìa khóa: {e}")
        st.stop()

# --- 3. KHỞI TẠO KẾT NỐI ---
try:
    gc = get_gspread_client()
    sh = gc.open("Quan_ly_lab")
    sheet_thietbi = sh.worksheet("ThietBi")
    sheet_lichsu = sh.worksheet("LichSu")
    sheet_taikhoan = sh.worksheet("TaiKhoan") 
except Exception as e:
    st.error(f"❌ Lỗi kết nối dữ liệu: {e}")
    st.stop()

# --- 4. HÀM TẢI DỮ LIỆU ---
def load_data(sheet):
    data = sheet.get_all_records()
    return pd.DataFrame(data)

# --- 5. KIỂM TRA TRẠNG THÁI ĐĂNG NHẬP ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['ho_ten'] = ""

# ==========================================
# GIAO DIỆN ĐĂNG NHẬP
# ==========================================
if not st.session_state['logged_in']:
    st.title("🔐 Đăng nhập Hệ thống Lab")
    st.info("Vui lòng đăng nhập bằng tài khoản Lab để sử dụng.")
    
    with st.form("login_form"):
        username = st.text_input("Tài khoản")
        password = st.text_input("Mật khẩu", type="password")
        submit_login = st.form_submit_button("Đăng nhập")
        
        if submit_login:
            df_tk = load_data(sheet_taikhoan)
            # Tìm tài khoản khớp
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
    # Header
    col_t, col_l = st.columns([8, 2])
    with col_t:
        st.title("🧪 Quản lý Thiết bị Lab")
    with col_l:
        st.write(f"👤 **{st.session_state['ho_ten']}**")
        if st.button("Đăng xuất"):
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
        else:
            st.warning("Chưa có dữ liệu trong sheet ThietBi.")

    # TAB 2: MƯỢN VÀ TRẢ
    with tab2:
        c1, c2 = st.columns(2)
        
        with c1:
            st.subheader("Đăng ký Mượn")
            ready_list = df[df['Trạng thái'] == 'Sẵn sàng']['Tên'].tolist() if not df.empty else []
            with st.form("borrow_f"):
                dev_m = st.selectbox("Chọn thiết bị", ready_list)
                note_m = st.text_input("Ghi chú/Mục đích")
                if st.form_submit_button("Xác nhận Mượn"):
                    if dev_m:
                        cell = sheet_thietbi.find(dev_m)
                        sheet_thietbi.update_cell(cell.row, 3, "Đang mượn")
                        sheet_thietbi.update_cell(cell.row, 4, st.session_state['ho_ten'])
                        sheet_thietbi.update_cell(cell.row, 5, note_m)
                        # Ghi lịch sử
                        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                        sheet_lichsu.append_row([now, st.session_state['ho_ten'], "Mượn", dev_m])
                        st.success(f"Đã mượn: {dev_m}")
                        st.rerun()
                    else: st.error("Không có thiết bị sẵn sàng.")

        with c2:
            st.subheader("Đăng ký Trả")
            borrowed_list = df[df['Trạng thái'] == 'Đang mượn']['Tên'].tolist() if not df.empty else []
            with st.form("return_f"):
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
                        st.success(f"Đã trả: {dev_t}")
                        st.rerun()
                    else: st.error("Không có thiết bị đang được mượn.")

    # TAB 3: LỊCH SỬ
    with tab3:
        st.subheader("Lịch sử giao dịch")
        history = load_data(sheet_lichsu)
        if not history.empty:
            st.dataframe(history.iloc[::-1], use_container_width=True, hide_index=True)
        else:
            st.info("Chưa có lịch sử.")