import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta, timezone, time as dt_time
import time

# ==========================================
# 1. CẤU HÌNH & KẾT NỐI (GMT+7)
# ==========================================
st.set_page_config(page_title="Hệ thống Lab", page_icon="📅", layout="wide")

VN_TZ = timezone(timedelta(hours=7))

def get_now():
    return datetime.now(VN_TZ)

def parse_time(t_str):
    t_str = str(t_str).strip()
    if t_str == "24:00" or t_str == "2400": return dt_time(23, 59, 59)
    try:
        return datetime.strptime(t_str, "%H:%M").time()
    except: return None

@st.cache_resource(ttl=3600)
def init_google_sheets():
    try:
        creds_dict = dict(st.secrets["my_creds"])
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].strip().replace("\\n", "\n")
        gc = gspread.service_account_from_dict(creds_dict)
        sh = gc.open("Quan_ly_lab") 
        return {
            "ThietBi": sh.worksheet("ThietBi"),
            "TaiKhoan": sh.worksheet("TaiKhoan"),
            "LichSu": sh.worksheet("LichSu"),
            "LichTuan": sh.worksheet("LichTuan")
        }
    except Exception as e:
        st.error(f"❌ Lỗi kết nối Google Sheets: {e}")
        st.stop()

sheets = init_google_sheets()
sheet_thietbi = sheets["ThietBi"]
sheet_taikhoan = sheets["TaiKhoan"]
sheet_lichsu = sheets["LichSu"]
sheet_lichtuan = sheets["LichTuan"]

@st.cache_data(ttl=15, show_spinner=False)
def load_data(sheet_name):
    try:
        return pd.DataFrame(sheets[sheet_name].get_all_records())
    except gspread.exceptions.APIError:
        time.sleep(2)
        return pd.DataFrame(sheets[sheet_name].get_all_records())

# ==========================================
# 2. ROBOT TỰ ĐỘNG THU HỒI
# ==========================================
def auto_return_devices():
    try:
        df_tb = load_data("ThietBi")
        df_lich = load_data("LichTuan")
        if df_tb.empty or df_lich.empty: return
        
        now = get_now()
        today_str = now.strftime("%d/%m/%Y")
        
        df_today = df_lich[df_lich['Ngày'] == today_str]
        if df_today.empty: return
        has_changes = False

        for _, row in df_tb.iterrows():
            if row.get('Trạng thái') == 'Đang mượn':
                device = row.get('Tên')
                user = row.get('Người sử dụng', '')
                user_bookings = df_today[(df_today['Thiết bị'] == device) & (df_today['Người sử dụng'] == user)]
                
                if not user_bookings.empty:
                    latest_end = None
                    for ca in user_bookings['Ca làm việc']:
                        try:
                            _, e_str = ca.split(" - ")
                            e_time = parse_time(e_str)
                            if latest_end is None or e_time > latest_end:
                                latest_end = e_time
                        except: pass
                    
                    if latest_end and now.time() >= latest_end:
                        cell = sheet_thietbi.find(device)
                        sheet_thietbi.update_cell(cell.row, 3, "Sẵn sàng")
                        sheet_thietbi.update_cell(cell.row, 4, "")
                        sheet_lichsu.append_row([now.strftime("%d/%m/%Y %H:%M:%S"), "🤖 Hệ thống", "Thu hồi tự động", device, "Hết giờ mượn"])
                        has_changes = True
        if has_changes:
            load_data.clear() 
    except:
        pass

# ==========================================
# 3. LOGIC ĐĂNG NHẬP
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state.update({'logged_in': False, 'ho_ten': "", 'tai_khoan': ""})

if not st.session_state['logged_in']:
    st.title("🔐 Đăng nhập Hệ thống Lab")
    with st.form("login"):
        u = st.text_input("Tài khoản")
        p = st.text_input("Mật khẩu", type="password")
        if st.form_submit_button("Đăng nhập"):
            df_tk = load_data("TaiKhoan")
            match = df_tk[(df_tk['TaiKhoan'].astype(str) == u) & (df_tk['MatKhau'].astype(str) == p)]
            if not match.empty:
                st.session_state.update({'logged_in': True, 'ho_ten': match.iloc[0]['HoTen'], 'tai_khoan': match.iloc[0]['TaiKhoan']})
                st.rerun()
            else: st.error("Sai tài khoản hoặc mật khẩu!")

# ==========================================
# 4. GIAO DIỆN CHÍNH
# ==========================================
else:
    df_tk = load_data("TaiKhoan")
    
    if not df_tk.empty and "TrangThai" not in df_tk.columns:
        num_cols = len(df_tk.columns)
        sheet_taikhoan.update_cell(1, num_cols + 1, "TrangThai")
        load_data.clear()
        df_tk = load_data("TaiKhoan")
        
    # ---------------- SIDEBAR: QUẢN LÝ TRẠNG THÁI CÁ NHÂN ----------------
    with st.sidebar:
        st.markdown(f"### 👤 {st.session_state['ho_ten']}")
        st.markdown("---")
        
        def update_status(new_status):
            cell = sheet_taikhoan.find(str(st.session_state['tai_khoan']))
            col_idx = df_tk.columns.get_loc("TrangThai") + 1
            sheet_taikhoan.update_cell(cell.row, col_idx, new_status)
            
            if new_status == "🟢 Ở Lab":
                sheet_lichsu.append_row([get_now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], "📍 Check-in Lab", "", ""])
                
            load_data.clear()
            st.rerun()

        my_status_arr = df_tk[df_tk['TaiKhoan'].astype(str) == str(st.session_state['tai_khoan'])]['TrangThai'].values
        current_my_status = my_status_arr[0] if len(my_status_arr) > 0 and my_status_arr[0] != "" else "⚪ Đã về"
        
        if current_my_status == "CẦN TRỢ GIÚP":
            st.markdown("<div style='background-color: #ff4b4b; color: white; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold; margin-bottom: 10px; box-shadow: 0 0 10px #ff4b4b;'>🚨 ĐANG BÁO ĐỘNG!</div>", unsafe_allow_html=True)
            if st.button("✅ Đã an toàn (Tắt báo động)", use_container_width=True):
                update_status("🟢 Ở Lab")
        else:
            st.write("**Trạng thái của bạn:**")
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("🟢 Lab", use_container_width=True): update_status("🟢 Ở Lab")
            with c2:
                if st.button("🟡 Bận", use_container_width=True): update_status("🟡 Đang bận")
            with c3:
                if st.button("⚪ Về", use_container_width=True): update_status("⚪ Đã về")
                
            st.markdown(f"Đang hiển thị:
