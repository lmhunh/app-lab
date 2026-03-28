import streamlit as st
import pandas as pd
import gspread
from datetime import datetime

# ==========================================
# 1. CẤU HÌNH TRANG
# ==========================================
st.set_page_config(page_title="Hệ thống Quản lý Lab", page_icon="🧪", layout="wide")

# ==========================================
# 2. HÀM KẾT NỐI (TRỊ DỨT ĐIỂM LỖI PEM & JWT)
# ==========================================
@st.cache_resource
def connect_to_gsheets():
    try:
        # Lấy dữ liệu từ "Két sắt" Secrets
        creds_dict = dict(st.secrets["my_creds"])
        
        # BỘ LỌC LÀM SẠCH PRIVATE_KEY
        if "private_key" in creds_dict:
            pk = creds_dict["private_key"]
            # 1. Loại bỏ khoảng trắng/dòng trống ở đầu và cuối
            pk = pk.strip()
            # 2. Ép tất cả các chuỗi "\n" bị lỗi thành lệnh xuống dòng thực sự
            pk = pk.replace("\\n", "\n")
            # Cập nhật lại key đã làm sạch
            creds_dict["private_key"] = pk
            
        return gspread.service_account_from_dict(creds_dict)
    except Exception as e:
        st.error(f"❌ Lỗi giải mã bí mật từ Secrets: {e}")
        st.stop()

# Khởi tạo kết nối Google Sheets
try:
    gc = connect_to_gsheets()
    # Tên file phải khớp 100% trên Google Drive
    sh = gc.open("Quan_ly_lab") 
    sheet_thietbi = sh.worksheet("ThietBi")
    sheet_taikhoan = sh.worksheet("TaiKhoan")
    sheet_lichsu = sh.worksheet("LichSu")
    sheet_lichtuan = sh.worksheet("LichTuan")
except Exception as e:
    st.error(f"❌ Lỗi kết nối Google Sheets: {e}")
    st.info("💡 Bạn đã Share file Sheets cho email bot (culi-109@...) với quyền Editor chưa?")
    st.stop()

# ==========================================
# 3. HÀM TẢI DỮ LIỆU
# ==========================================
def load_data(sheet):
    return pd.DataFrame(sheet.get_all_records())

# ==========================================
# 4. QUẢN LÝ ĐĂNG NHẬP
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['ho_ten'] = ""

if not st.session_state['logged_in']:
    st.title("🔐 Đăng nhập Hệ thống Lab")
    with st.form("login_form"):
        username = st.text_input("Tài khoản")
        password = st.text_input("Mật khẩu", type="password")
        submit_login = st.form_submit_button("Đăng nhập")

        if submit_login:
            df_tk = load_data(sheet_taikhoan)
            # Kiểm tra tài khoản
            match = df_tk[(df_tk['TaiKhoan'].astype(str) == str(username)) & 
                          (df_tk['MatKhau'].astype(str) == str(password))]

            if not match.empty:
                st.session_state['logged_in'] = True
                st.session_state['ho_ten'] = match.iloc[0]['HoTen']
                st.rerun()
            else:
                st.error("❌ Sai tài khoản hoặc mật khẩu!")

# ==========================================
# 5. GIAO DIỆN CHÍNH (SAU KHI ĐĂNG NHẬP)
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
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Trạng thái thiết bị", "🔄 Mượn / Trả", "🕒 Lịch sử", "📅 Lịch theo tuần"])

    # --- TAB 1: HIỂN THỊ DANH SÁCH ---
    with tab1:
        st.subheader("Danh sách thiết bị hiện tại")
        def color_status(val):
            color = 'red' if val == 'Hỏng' else ('orange' if val == 'Đang mượn' else 'green')
            return f'color: {color}'
        
        if not df.empty:
            st.dataframe(df.style.map(color_status, subset=['Trạng thái']), use_container_width=True, hide_index=True)
        else:
            st.info("Chưa có dữ liệu thiết bị.")

    # --- TAB 2: MƯỢN / TRẢ ---
    with tab2:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Đăng ký Mượn")
            ready_devices = df[df['Trạng thái'] == 'Sẵn sàng']['Tên'].tolist() if not df.empty else []
            with st.form("borrow_form"):
                selected_device = st.selectbox("Chọn thiết bị", ready_devices)
                note = st.text_input("Ghi chú mượn (VD: Đo phổ mẫu mới)")
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

    # --- TAB 3: LỊCH SỬ ---
    with tab3:
        st.subheader("Lịch sử giao dịch gần đây")
        history_data = load_data(sheet_lichsu)
        if not history_data.empty:
            st.dataframe(history_data.iloc[::-1], use_container_width=True, hide_index=True)
        else:
            st.info("Chưa có lịch sử giao dịch.")
# --- TAB 4: ĐĂNG KÝ LỊCH THEO TUẦN ---
    with tab4:
        st.subheader("Lịch sử dụng Lab trong tuần")
        c_form, c_view = st.columns([1, 2])
        
        with c_form:
            st.markdown("**📝 Form Đăng ký**")
            with st.form("form_dat_lich"):
                ngay_dk = st.date_input("Chọn ngày")
                ca_lam_viec = st.selectbox("Ca làm việc", ["Sáng (8h-12h)", "Chiều (13h-17h)", "Tối (18h-22h)"])
                
                # Lấy danh sách thiết bị để chọn (bỏ các thiết bị đã hỏng)
                danh_sach_tb = df[df['Trạng thái'] != 'Hỏng']['Tên'].tolist() if not df.empty else ["Bàn lab chung"]
                thiet_bi_dk = st.selectbox("Thiết bị / Vị trí", danh_sach_tb)
                
                muc_dich = st.text_input("Mục đích", placeholder="VD: Rửa cốc,...")
                
                if st.form_submit_button("Lưu lịch"):
                    if muc_dich == "":
                        st.warning("Vui lòng nhập mục đích sử dụng!")
                    else:
                        ngay_str = ngay_dk.strftime("%d/%m/%Y")
                        # Ghi dữ liệu vào Google Sheets
                        sheet_lichtuan.append_row([ngay_str, ca_lam_viec, st.session_state['ho_ten'], thiet_bi_dk, muc_dich])
                        st.success(f"✅ Đã lưu lịch ngày {ngay_str} ca {ca_lam_viec}!")
                        st.rerun()

        with c_view:
            st.markdown("**📅 Lịch đã đăng ký**")
            df_lich = load_data(sheet_lichtuan)
            
            if not df_lich.empty:
                # Sắp xếp lịch theo ngày gần nhất
                df_lich['Ngày_datetime'] = pd.to_datetime(df_lich['Ngày'], format='%d/%m/%Y')
                df_lich_sorted = df_lich.sort_values(by=['Ngày_datetime', 'Ca làm việc']).drop(columns=['Ngày_datetime'])
                
                st.dataframe(df_lich_sorted, use_container_width=True, hide_index=True)
            else:
                st.info("Tuần này Lab đang trống lịch. Nhanh tay đăng ký nhé!")
