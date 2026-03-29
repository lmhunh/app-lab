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
    df_tb = load_data("ThietBi")
    df_lich_view = load_data("LichTuan")
    df_h = load_data("LichSu")
    all_devices = df_tb['Tên'].tolist() if not df_tb.empty else []
    
    today = get_now().date()
    days_7 = [(today + timedelta(days=i)).strftime("%d/%m/%Y") for i in range(7)]
    time_options = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 15, 30, 45)]
    
    if not df_tk.empty and "TrangThai" not in df_tk.columns:
        num_cols = len(df_tk.columns)
        sheet_taikhoan.update_cell(1, num_cols + 1, "TrangThai")
        load_data.clear()
        df_tk = load_data("TaiKhoan")
        
    def format_device_option(dev_name):
        if df_tb.empty or dev_name not in df_tb['Tên'].values: return dev_name
        row = df_tb[df_tb['Tên'] == dev_name].iloc[0]
        status = row.get('Trạng thái', 'Sẵn sàng')
        user = row.get('Người sử dụng', '')
        if status == 'Sẵn sàng': return f"🟢 {dev_name}"
        else: return f"🔴 {dev_name} (Bận: {user.split()[-1] if user else ''})"

    # ---------------- SIDEBAR: BẢNG ĐIỀU KHIỂN CÁ NHÂN & TABS ----------------
    with st.sidebar:
        st.markdown(f"### 👤 {st.session_state['ho_ten']}")
        
        def update_status(new_status):
            cell = sheet_taikhoan.find(str(st.session_state['tai_khoan']))
            col_idx = df_tk.columns.get_loc("TrangThai") + 1
            sheet_taikhoan.update_cell(cell.row, col_idx, new_status)
            if new_status == "🟢 Ở Lab":
                sheet_lichsu.append_row([get_now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], "📍 Check-in Lab", "", ""])
            elif new_status == "⚪ Đã về":
                sheet_lichsu.append_row([get_now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], "🏃 Check-out", "", ""])
            load_data.clear()
            st.rerun()

        my_status_arr = df_tk[df_tk['TaiKhoan'].astype(str) == str(st.session_state['tai_khoan'])]['TrangThai'].values
        current_my_status = my_status_arr[0] if len(my_status_arr) > 0 and my_status_arr[0] != "" else "⚪ Đã về"
        
        if current_my_status == "CẦN TRỢ GIÚP":
            st.markdown("<div style='background-color: #ff4b4b; color: white; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold; margin-bottom: 10px;'>🚨 ĐANG BÁO ĐỘNG!</div>", unsafe_allow_html=True)
            if st.button("✅ Đã an toàn", use_container_width=True): update_status("🟢 Ở Lab")
        else:
            c1, c2, c3 = st.columns(3)
            with c1: 
                if st.button("🟢 Lab", use_container_width=True): update_status("🟢 Ở Lab")
            with c2: 
                if st.button("🟡 Bận", use_container_width=True): update_status("🟡 Đang bận")
            with c3: 
                if st.button("⚪ Về", use_container_width=True): update_status("⚪ Đã về")
            
            if st.button("🆘 NÚT KHẨN CẤP", use_container_width=True, type="primary"): update_status("CẦN TRỢ GIÚP")
            
        st.markdown("---")
        
        # ĐƯA 3 TABS THAO TÁC VÀO SIDEBAR
        st.markdown("### 🛠️ THAO TÁC THIẾT BỊ")
        tab_dk, tab_ls, tab_tra = st.tabs(["📅 Đăng ký", "🕒 Lịch sử", "🔄 Trả máy"])
        
        # --- SIDEBAR TAB 1: ĐĂNG KÝ MÁY ---
        with tab_dk:
            view_mode = st.selectbox("🔍 Chọn thiết bị:", all_devices if all_devices else ["Chưa có dữ liệu"], format_func=format_device_option if all_devices else lambda x: x)
            
            with st.expander(f"Mini-Timeline [{view_mode}]", expanded=True):
                df_dev = df_lich_view[df_lich_view['Thiết bị'] == view_mode] if not df_lich_view.empty else pd.DataFrame()
                if not df_dev.empty: df_dev = df_dev.drop_duplicates(subset=['Ngày', 'Ca làm việc', 'Thiết bị'])
                
                html_timeline = "<div style='width: 100%; font-family: sans-serif; padding-bottom: 5px;'><div style='display: flex; align-items: flex-end; width: 100%; margin-bottom: 5px; font-size: 9px; color: #666; font-weight: bold;'><div style='width: 35px;'></div><div style='flex-grow: 1; position: relative; height: 15px; border-bottom: 1px solid #aaa;'>"
                for h in range(0, 25, 6): 
                    left_pct = (h / 24.0) * 100
                    html_timeline += f"<div style='position: absolute; left: {left_pct}%; transform: translateX(-50%); bottom: 2px;'>{h:02d}h</div><div style='position: absolute; left: {left_pct}%; width: 1px; height: 4px; background-color: #aaa; bottom: -1px; transform: translateX(-50%);'></div>"
                html_timeline += "</div></div>"
                
                for d in days_7:
                    html_timeline += f"<div style='display: flex; align-items: center; margin-bottom: 6px; width: 100%;'><div style='width: 35px; font-size: 10px; font-weight: bold; color: #444;'>{d[:5]}</div><div style='flex-grow: 1; position: relative; height: 18px; background-color: #e9ecef; border-radius: 3px; border: 1px solid #ddd;'>"
                    
                    df_day = df_dev[df_dev['Ngày'] == d]
                    if not df_day.empty:
                        for _, r in df_day.iterrows():
                            ca = str(r['Ca làm việc'])
                            if " - " in ca:
                                try:
                                    s_str, e_str = ca.split(" - ")
                                    s_time, e_time = parse_time(s_str), parse_time(e_str)
                                    start_min, end_min = s_time.hour * 60 + s_time
