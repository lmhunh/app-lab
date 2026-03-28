import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta, timezone, time as dt_time
import time

# ==========================================
# 1. CẤU HÌNH & KẾT NỐI (GMT+7)
# ==========================================
st.set_page_config(page_title="Hệ thống Lab (Fixed Timeline)", page_icon="📅", layout="wide")

VN_TZ = timezone(timedelta(hours=7))

def get_now():
    return datetime.now(VN_TZ)

def parse_time(t_str):
    t_str = str(t_str).strip()
    if t_str == "24:00" or t_str == "2400": return dt_time(23, 59, 59)
    try:
        if ":" in t_str: return datetime.strptime(t_str, "%H:%M").time()
        elif len(t_str) == 4: return datetime.strptime(t_str, "%H%M").time()
        elif len(t_str) == 3: return datetime.strptime(f"0{t_str}", "%H%M").time()
        elif len(t_str) in [1, 2]: return dt_time(int(t_str), 0)
    except: return None
    return None

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
                        sheet_lichsu.append_row([now.strftime("%d/%m/%Y %H:%M:%S"), "🤖 Hệ thống", "Thu hồi tự động", device])
                        has_changes = True
        if has_changes:
            load_data.clear() 
    except:
        pass

# ==========================================
# 3. LOGIC ĐĂNG NHẬP
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state.update({'logged_in': False, 'ho_ten': ""})

if not st.session_state['logged_in']:
    st.title("🔐 Đăng nhập Hệ thống Lab")
    with st.form("login"):
        u = st.text_input("Tài khoản")
        p = st.text_input("Mật khẩu", type="password")
        if st.form_submit_button("Đăng nhập"):
            df_tk = load_data("TaiKhoan")
            match = df_tk[(df_tk['TaiKhoan'].astype(str) == u) & (df_tk['MatKhau'].astype(str) == p)]
            if not match.empty:
                st.session_state.update({'logged_in': True, 'ho_ten': match.iloc[0]['HoTen']})
                st.rerun()
            else: st.error("Sai tài khoản hoặc mật khẩu!")

# ==========================================
# 4. GIAO DIỆN CHÍNH
# ==========================================
else:
    col_t, col_l = st.columns([8, 2])
    col_t.title("📅 Hệ thống Quản lý Thiết bị Lab")
    with col_l:
        st.write(f"👤 **{st.session_state['ho_ten']}**")
        if st.button("🚪 Đăng xuất"):
            st.session_state['logged_in'] = False
            st.rerun()

    st.markdown("""
    <div style='text-align: center; font-style: italic; color: #4b4b4b; background-color: #f1f8ff; padding: 10px; border-radius: 8px; border-left: 5px solid #0366d6; margin-bottom: 20px;'>
        "Nghiên cứu khoa học là biến những điều chưa biết thành kiến thức. Chúc bạn có một phiên làm việc hiệu quả!" 🔬✨
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    auto_return_devices()
    
    df_tb = load_data("ThietBi")
    df_lich_view = load_data("LichTuan")
    all_devices = df_tb['Tên'].tolist() if not df_tb.empty else []
    
    today = get_now().date()
    days_7 = [(today + timedelta(days=i)).strftime("%d/%m/%Y") for i in range(7)]

    tab1, tab2, tab3, tab4 = st.tabs(["📊 Trạng thái", "📅 Đăng ký & Timeline", "🕒 Lịch sử", "🔄 Trả thiết bị"])

    # --- TAB 1: TRẠNG THÁI ---
    with tab1:
        st.subheader("Tình trạng thiết bị hiện tại")
        if not df_tb.empty:
            st.dataframe(df_tb, use_container_width=True, hide_index=True)
