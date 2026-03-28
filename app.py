import streamlit as st
import pandas as pd
import gspread
from datetime import datetime

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="Hệ thống Quản lý Lab", layout="wide")

# --- KẾT NỐI GOOGLE SHEETS BẢO MẬT ---
try:
    if "gcp_service_account" in st.secrets:
        gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
    else:
        gc = gspread.service_account(filename='credentials.json')
        
    sh = gc.open("Quan_ly_lab")
    sheet_thietbi = sh.worksheet("ThietBi")
    sheet_lichsu = sh.worksheet("LichSu")
    sheet_taikhoan = sh.worksheet("TaiKhoan") # Thêm sheet Tài khoản
except Exception as e:
    st.error(f"❌ Lỗi kết nối dữ liệu: {e}")
    st.stop()

# --- KHỞI TẠO TRẠNG THÁI ĐĂNG NHẬP ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['ho_ten'] = ""

# --- HÀM TẢI DỮ LIỆU ---
def load_data(sheet):
    data = sheet.get_all_records()
    return pd.DataFrame(data)

# ==========================================
# GIAO DIỆN ĐĂNG NHẬP
# ==========================================
if not st.session_state['logged_in']:
    st.title("🔐 Đăng nhập Hệ thống Lab")
    st.info("Vui lòng đăng nhập để mượn/trả thiết bị.")
    
    with st.form("login_form"):
        username = st.text_input("Tài khoản")
        password = st.text_input("Mật khẩu", type="password") # Ẩn mật khẩu bằng dấu ***
        submit_login = st.form_submit_button("Đăng nhập")
        
        if submit_login:
            df_tk = load_data(sheet_taikhoan)
            # Kiểm tra xem có tài khoản nào khớp không
            match = df_tk[(df_tk['TaiKhoan'] == username) & (df_tk['MatKhau'] == str(password))]
            
            if not match.empty:
                st.session_state['logged_in'] = True
                st.session_state['ho_ten'] = match.iloc[0]['HoTen']
                st.rerun() # Tải lại trang để vào bên trong
            else:
                st.error("❌ Sai tài khoản hoặc mật khẩu!")

# ==========================================
# GIAO DIỆN CHÍNH (SAU KHI ĐĂNG NHẬP)
# ==========================================
else:
    # Header hiển thị người dùng và nút Đăng xuất
    col_title, col_logout = st.columns([8, 2])
    with col_title:
        st.title("🧪 Phần mềm Quản lý Thiết bị Lab")
    with col_logout:
        st.write(f"👤 Xin chào, **{st.session_state['ho_ten']}**")
        if st.button("🚪 Đăng xuất"):
            st.session_state['logged_in'] = False
            st.rerun()

    st.markdown("---")
    df = load_data(sheet_thietbi)
    tab1, tab2, tab3 = st.tabs(["📊 Trạng thái thiết bị", "🔄 Mượn / Trả", "🕒 Lịch sử"])

    # TAB 1: HIỂN THỊ TRẠNG THÁI
    with tab1:
        st.subheader("Danh sách thiết bị hiện tại")
        def color_status(val):
            color = 'red' if val == 'Hỏng' else ('orange' if val == 'Đang mượn' else 'green')
            return f'color: {color}'
        
        if not df.empty:
            # hide_index=True để ẩn cột số 0, 1, 2
            st.dataframe(df.style.map(color_status, subset=['Trạng thái']), use_container_width=True, hide_index=True)
        else:
            st.info("Chưa có dữ liệu thiết bị.")

    # TAB 2: CHỨC NĂNG MƯỢN TRẢ
    with tab2:
        col1, col2 = st.columns(2)
        
        # --- FORM MƯỢN ---
        with col1:
            st.subheader("Đăng ký Mượn")
            if not df.empty and 'Trạng thái' in df.columns:
                ready_devices = df[df['Trạng thái'] == 'Sẵn sàng']['Tên'].tolist()
            else:
                ready_devices = []
                
            with st.form("borrow_form"):
                selected_device = st.selectbox("Chọn thiết bị", ready_devices)
                note = st.text_input("Mục đích mượn / Ghi chú")
                submit_borrow = st.form_submit_button("Xác nhận Mượn")
                
                if submit_borrow:
                    if not selected_device:
                        st.warning("⚠️ Không có thiết bị nào đang sẵn sàng!")
                    else:
                        cell = sheet_thietbi.find(selected_device)
                        sheet_thietbi.update_cell(cell.row, 3, "Đang mượn") 
                        sheet_thietbi.update_cell(cell.row, 4, st.session_state['ho_ten']) # Tự lấy tên người đăng nhập
                        sheet_thietbi.update_cell(cell.row, 5, note) 
                        
                        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                        sheet_lichsu.append_row([now, st.session_state['ho_ten'], "Mượn", selected_device])
                        st.success(f"✅ Đã ghi nhận bạn mượn {selected_device}")
                        st.rerun() 
                        
        # --- FORM TRẢ ---
        with col2:
            st.subheader("Đăng ký Trả")
            if not df.empty and 'Trạng thái' in df.columns:
                # Chỉ hiện những thiết bị mà người này đang mượn (Hoặc hiện tất cả tùy bạn)
                borrowed_devices = df[df['Trạng thái'] == 'Đang mượn']['Tên'].tolist()
            else:
                borrowed_devices = []
                
            with st.form("return_form"):
                return_device = st.selectbox("Chọn thiết bị cần trả", borrowed_devices)
                submit_return = st.form_submit_button("Xác nhận Trả")
                
                if submit_return:
                    if not return_device:
                        st.warning("⚠️ Không có thiết bị nào đang được mượn!")
                    else:
                        cell = sheet_thietbi.find(return_device)
                        sheet_thietbi.update_cell(cell.row, 3, "Sẵn sàng")
                        sheet_thietbi.update_cell(cell.row, 4, "")
                        sheet_thietbi.update_cell(cell.row, 5, "Đã trả")
                        
                        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                        sheet_lichsu.append_row([now, st.session_state['ho_ten'], "Trả", return_device])
                        st.success(f"✅ Đã ghi nhận bạn trả {return_device}")
                        st.rerun()

    # TAB 3: XEM LỊCH SỬ
    with tab3:
        st.subheader("Lịch sử Mượn / Trả gần đây")
        history_data = sheet_lichsu.get_all_records()
        if history_data:
            df_history = pd.DataFrame(history_data)
            st.dataframe(df_history.iloc[::-1], use_container_width=True, hide_index=True)
        else:
            st.info("Chưa có lịch sử giao dịch nào.")