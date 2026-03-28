import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta, timezone, time as dt_time
import time

# ==========================================
# 1. CẤU HÌNH & KẾT NỐI (BỌC THÉP CHỐNG LỖI 429)
# ==========================================
st.set_page_config(page_title="Hệ thống Lab (Pro Version)", page_icon="📅", layout="wide")

VN_TZ = timezone(timedelta(hours=7))

def get_now():
    return datetime.now(VN_TZ)

def parse_time(t_str):
    t_str = str(t_str).strip()
    try:
        if ":" in t_str: return datetime.strptime(t_str, "%H:%M").time()
        elif len(t_str) == 4: return datetime.strptime(t_str, "%H%M").time()
        elif len(t_str) == 3: return datetime.strptime(f"0{t_str}", "%H%M").time()
        elif len(t_str) in [1, 2]: return dt_time(int(t_str), 0)
    except: return None
    return None

# ĐÂY LÀ CHÌA KHÓA CHỐNG 429: Cache toàn bộ kết nối và Object Sheets (Lưu 1 tiếng)
@st.cache_resource(ttl=3600)
def init_google_sheets():
    try:
        creds_dict = dict(st.secrets["my_creds"])
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].strip().replace("\\n", "\n")
        gc = gspread.service_account_from_dict(creds_dict)
        sh = gc.open("Quan_ly_lab") 
        # Lấy tất cả các sheet 1 lần duy nhất và cất vào Cache
        return {
            "ThietBi": sh.worksheet("ThietBi"),
            "TaiKhoan": sh.worksheet("TaiKhoan"),
            "LichSu": sh.worksheet("LichSu"),
            "LichTuan": sh.worksheet("LichTuan")
        }
    except Exception as e:
        st.error(f"❌ Lỗi kết nối Google Sheets: {e}")
        st.stop()

# Gọi dữ liệu từ Cache Két Sắt
sheets = init_google_sheets()
sheet_thietbi = sheets["ThietBi"]
sheet_taikhoan = sheets["TaiKhoan"]
sheet_lichsu = sheets["LichSu"]
sheet_lichtuan = sheets["LichTuan"]

# Đọc bảng dữ liệu (Lưu Cache 15 giây)
@st.cache_data(ttl=15, show_spinner=False)
def load_data(sheet_name):
    try:
        return pd.DataFrame(sheets[sheet_name].get_all_records())
    except gspread.exceptions.APIError:
        time.sleep(2) # Giảm xóc 2 giây nếu Google quá tải
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
    col_t.title("📅 Quản lý Lab - Calendar View")
    with col_l:
        st.write(f"👤 **{st.session_state['ho_ten']}**")
        if st.button("🚪 Đăng xuất"):
            st.session_state['logged_in'] = False
            st.rerun()

    st.markdown("---")
    auto_return_devices()
    
    df_tb = load_data("ThietBi")
    df_lich_view = load_data("LichTuan")
    all_devices = df_tb['Tên'].tolist() if not df_tb.empty else []
    
    khung_gio_24h = [f"{i:02d}:00" for i in range(24)]
    today = get_now().date()
    days_7 = [(today + timedelta(days=i)).strftime("%d/%m/%Y") for i in range(7)]

    tab1, tab2, tab3, tab4 = st.tabs(["📊 Trạng thái", "📅 Lịch Calendar & Đặt lịch", "🕒 Lịch sử", "🔄 Trả thiết bị"])

    # --- TAB 1: TRẠNG THÁI ---
    with tab1:
        st.subheader("Tình trạng thiết bị hiện tại")
        if not df_tb.empty:
            st.dataframe(df_tb, use_container_width=True, hide_index=True)

    # --- TAB 2: LỊCH CALENDAR & ĐẶT LỊCH ---
    with tab2:
        st.subheader("📅 Kiểm tra lịch thiết bị")
        c_filter, _ = st.columns([1, 2])
        with c_filter:
            view_mode = st.selectbox("Chọn thiết bị để xem lịch:", all_devices if all_devices else ["Chưa có dữ liệu"])
        
        # Thẻ trạng thái nhanh
        if not df_tb.empty and view_mode in df_tb['Tên'].values:
            current_status = df_tb[df_tb['Tên'] == view_mode].iloc[0]['Trạng thái']
            current_user = df_tb[df_tb['Tên'] == view_mode].iloc[0].get('Người sử dụng', '')
            
            if current_status == 'Sẵn sàng':
                st.markdown(f"""
                <div style='padding: 15px; border-radius: 8px; background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb;'>
                    <h4 style='margin: 0;'>🟢 <b>{view_mode}</b> đang SẴN SÀNG! Bạn có thể đặt lịch ngay.</h4>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style='padding: 15px; border-radius: 8px; background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb;'>
                    <h4 style='margin: 0;'>🔴 <b>{view_mode}</b> đang BẬN (Người dùng: <b>{current_user}</b>).</h4>
                </div>
                """, unsafe_allow_html=True)

        st.write("") 

        # Ma trận Google Calendar Style
        with st.expander("👉 Mở Lịch tuần (Click vào ô để xem chi tiết)", expanded=True):
            df_matrix_data = df_lich_view[df_lich_view['Thiết bị'] == view_mode] if not df_lich_view.empty else pd.DataFrame()
            matrix = pd.DataFrame(" ", index=khung_gio_24h, columns=days_7)
            
            if not df_matrix_data.empty:
                for _, r in df_matrix_data.iterrows():
                    ca = str(r['Ca làm việc'])
                    if " - " in ca and str(r['Ngày']) in days_7:
                        try:
                            s_str, e_str = ca.split(" - ")
                            s_time = parse_time(s_str)
                            e_time = parse_time(e_str)
                            
                            for h in range(24):
                                block_start = dt_time(h, 0)
                                block_end = dt_time(h, 59)
                                
                                if s_time <= block_end and block_start <= e_time:
                                    block_text = f"🔷 {s_time.strftime('%H:%M')} - {e_time.strftime('%H:%M')}"
                                    current_val = matrix.at[f"{h:02d}:00", str(r['Ngày'])]
                                    if "🔷" in current_val:
                                        matrix.at[f"{h:02d}:00", str(r['Ngày'])] += f"\n🔷 {s_time.strftime('%H:%M')}-{e_time.strftime('%H:%M')}"
                                    else:
                                        matrix.at[f"{h:02d}:00", str(r['Ngày'])] = block_text
                        except: pass

            def style_calendar(val):
                if "🔷" in val: return 'background-color: #e8f0fe; color: #1967d2; font-weight: bold; border-left: 4px solid #1a73e8;'
                return 'background-color: white; color: black;'
            
            event = st.dataframe(
                matrix.style.map(style_calendar),
                use_container_width=True,
                height=400,
                on_select="rerun",
                selection_mode="single-cell"
            )

            if event and len(event.selection.rows) > 0 and len(event.selection.columns) > 0:
                r_idx = event.selection.rows[0]
                c_idx = event.selection.columns[0]
                s_hour_str = matrix.index[r_idx]
                s_date = matrix.columns[c_idx]
                
                s_hour = int(s_hour_str.split(":")[0])
                block_start = dt_time(s_hour, 0)
                block_end = dt_time(s_hour, 59)
                
                overlapping = []
                if not df_matrix_data.empty:
                    df_day = df_matrix_data[df_matrix_data['Ngày'] == s_date]
                    for _, r in df_day.iterrows():
                        try:
                            s_t = parse_time(r['Ca làm việc'].split(" - ")[0])
                            e_t = parse_time(r['Ca làm việc'].split(" - ")[1])
                            if s_t <= block_end and block_start <= e_t:
                                overlapping.append(r)
                        except: pass
                
                if overlapping:
                    st.error(f"📅 **Chi tiết lịch ngày {s_date} (Quanh mốc {s_hour_str}):**")
                    for r in overlapping:
                        st.write(f"- ⏱️ **{r['Ca làm việc']}** | 👤 **{r['Người sử dụng']}** | 📝 *{r['Mục đích']}*")
                else:
                    st.success(f"🟢 Khung {s_hour_str} ngày {s_date} hiện đang trống!")
            
        st.markdown("---")
        
        # Form Đặt Lịch
        st.markdown(f"### 📝 Đặt lịch thiết bị: **{view_mode}**")
        with st.form("smart_booking"):
            st.info("💡 **Mẹo:** Bạn có thể gõ trực tiếp thời gian (Ví dụ: `14:30`, `1430` hoặc `9`).")
            c1, c2, c3, c4 = st.columns([1.5, 1, 1, 2])
            
            with c1: 
                d_pick = st.date_input("🗓️ Chọn ngày", min_value=today)
            with c2: 
                is_now = st.checkbox("Sử dụng BÂY GIỜ", value=True)
                if not is_now:
                    t_start_input = st.text_input("⏳ Từ lúc:", placeholder="VD: 14:30")
                else:
                    t_start_input = get_
