import streamlit as st
import pandas as pd
import gspread
from datetime import datetime

# ==========================================
# 1. CẤU HÌNH TRANG & KẾT NỐI
# ==========================================
st.set_page_config(page_title="Hệ thống Quản lý Lab", page_icon="🧪", layout="wide")

@st.cache_resource
def connect_to_gsheets():
    try:
        creds_dict = dict(st.secrets["my_creds"])
        if "private_key" in creds_dict:
            pk = creds_dict["private_key"].strip().replace("\\n", "\n")
            creds_dict["private_key"] = pk
        return gspread.service_account_from_dict(creds_dict)
    except Exception as e:
        st.error(f"❌ Lỗi Secrets: {e}")
        st.stop()

# Khởi tạo các Sheet
try:
    gc = connect_to_gsheets()
    sh = gc.open("Quan_ly_lab") 
    sheet_thietbi = sh.worksheet("ThietBi")
    sheet_taikhoan = sh.worksheet("TaiKhoan")
    sheet_lichsu = sh.worksheet("LichSu")
    sheet_lichtuan = sh.worksheet("LichTuan")
except Exception as e:
    st.error(f"❌ Lỗi kết nối Sheets: {e}")
    st.stop()

# ==========================================
# 2. HÀM HỖ TRỢ (HELPER FUNCTIONS)
# ==========================================
def load_data(sheet):
    return pd.DataFrame(sheet.get_all_records())

def check_conflict(df_lich, ngay, gio, thiet_bi):
    """Kiểm tra xem thiết bị đã có người đặt vào khung giờ đó chưa"""
    if df_lich.empty: return False
    conflict = df_lich[(df_lich['Ngày'] == ngay) & 
                       (df_lich['Ca làm việc'] == gio) & 
                       (df_lich['Thiết bị'] == thiet_bi)]
    return not conflict.empty

# ==========================================
# 3. QUẢN LÝ ĐĂNG NHẬP
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state.update({'logged_in': False, 'ho_ten': ""})

if not st.session_state['logged_in']:
    st.title("🔐 Đăng nhập Hệ thống Lab")
    with st.form("login_form"):
        u = st.text_input("Tài khoản")
        p = st.text_input("Mật khẩu", type="password")
        if st.form_submit_button("Đăng nhập"):
            df_tk = load_data(sheet_taikhoan)
            match = df_tk[(df_tk['TaiKhoan'].astype(str) == u) & (df_tk['MatKhau'].astype(str) == p)]
            if not match.empty:
                st.session_state.update({'logged_in': True, 'ho_ten': match.iloc[0]['HoTen']})
                st.rerun()
            else: st.error("Sai tài khoản hoặc mật khẩu!")

# ==========================================
# 4. GIAO DIỆN CHÍNH
# ==========================================
else:
    # Sidebar / Header
    col_t, col_l = st.columns([8, 2])
    col_t.title("🧪 Phần mềm Quản lý Lab")
    with col_l:
        st.write(f"👤 **{st.session_state['ho_ten']}**")
        if st.button("🚪 Đăng xuất"):
            st.session_state['logged_in'] = False
            st.rerun()

    st.markdown("---")
    df_tb = load_data(sheet_thietbi)
    df_lich = load_data(sheet_lichtuan)
    khung_gio_24h = [f"{i:02d}:00" for i in range(24)]

    tab1, tab2, tab3, tab4 = st.tabs(["📊 Trạng thái", "📅 Mượn & Đặt lịch", "🕒 Lịch sử", "🔄 Trả thiết bị"])

    # --- TAB 1: TRẠNG THÁI ---
    with tab1:
        st.subheader("Danh sách thiết bị")
        if not df_tb.empty:
            st.dataframe(df_tb, use_container_width=True, hide_index=True)

    # --- TAB 2: MƯỢN & ĐẶT LỊCH (CHỐNG TRÙNG) ---
    with tab2:
        st.info("💡 Bạn có thể Mượn sử dụng ngay hoặc Đặt lịch trước cho tuần tới.")
        col_borrow, col_schedule = st.columns(2)

        with col_borrow:
            st.subheader("⚡ Mượn ngay bây giờ")
            ready_list = df_tb[df_tb['Trạng thái'] == 'Sẵn sàng']['Tên'].tolist()
            with st.form("form_muon_ngay"):
                device_now = st.selectbox("Chọn thiết bị", ready_list if ready_list else ["Không có máy trống"])
                note_now = st.text_input("Ghi chú (VD: Đo phổ Raman ZnO)")
                if st.form_submit_button("Xác nhận Mượn"):
                    now_h = datetime.now().strftime("%H:00")
                    today_s = datetime.now().strftime("%d/%m/%Y")
                    
                    # Kiểm tra xem giờ này có ai đặt trước không
                    if check_conflict(df_lich, today_s, now_h, device_now):
                        st.error("⚠️ Giờ này đã có người đặt lịch trước cho máy này!")
                    else:
                        cell = sheet_thietbi.find(device_now)
                        sheet_thietbi.update_cell(cell.row, 3, "Đang mượn")
                        sheet_thietbi.update_cell(cell.row, 4, st.session_state['ho_ten'])
                        sheet_lichsu.append_row([f"{today_s} {datetime.now().strftime('%H:%M')}", st.session_state['ho_ten'], "Mượn", device_now])
                        st.success(f"✅ Đã mượn {device_now}")
                        st.rerun()

        with col_schedule:
            st.subheader("📅 Đặt lịch trước (When2meet style)")
            with st.form("form_dat_lich"):
                ngay_dk = st.date_input("Chọn ngày", min_value=datetime.now().date())
                gio_dk = st.multiselect("Chọn các khung giờ", khung_gio_24h)
                tb_dk = st.selectbox("Thiết bị đặt lịch", df_tb['Tên'].tolist())
                ghi_chu_dk = st.text_input("Mục đích (VD: Ủ nhiệt Cu2O)")
                if st.form_submit_button("🔥 Lưu lịch đã chọn"):
                    n_str = ngay_dk.strftime("%d/%m/%Y")
                    conflicts = [g for g in gio_dk if check_conflict(df_lich, n_str, g, tb_dk)]
                    if conflicts:
                        st.error(f"❌ Trùng lịch tại: {', '.join(conflicts)}")
                    else:
                        for g in gio_dk:
                            sheet_lichtuan.append_row([n_str, g, st.session_state['ho_ten'], tb_dk, ghi_chu_dk])
                        st.success("✅ Đã đặt lịch thành công!")
                        st.rerun()

    # --- TAB 3: LỊCH SỬ ---
    with tab3:
        st.subheader("Lịch sử hoạt động")
        df_history = load_data(sheet_lichsu)
        if not df_history.empty:
            st.dataframe(df_history.iloc[::-1], use_container_width=True, hide_index=True)

    # --- TAB 4: TRẢ THIẾT BỊ ---
    with tab4:
        st.subheader("🔄 Hoàn trả thiết bị")
        my_borrowed = df_tb[df_tb['Người mượn'] == st.session_state['ho_ten']]['Tên'].tolist()
        if not my_borrowed:
            st.info("Bạn hiện không mượn thiết bị nào.")
        else:
            with st.form("form_tra"):
                device_return = st.selectbox("Chọn thiết bị muốn trả", my_borrowed)
                if st.form_submit_button("Xác nhận Trả"):
                    cell = sheet_thietbi.find(device_return)
                    sheet_thietbi.update_cell(cell.row, 3, "Sẵn sàng")
                    sheet_thietbi.update_cell(cell.row, 4, "")
                    sheet_thietbi.update_cell(cell.row, 5, "")
                    
                    now_s = datetime.now().strftime("%d/%m/%Y %H:%M")
                    sheet_lichsu.append_row([now_s, st.session_state['ho_ten'], "Trả", device_return])
                    st.success(f"✅ Đã trả {device_return}")
                    st.rerun()
