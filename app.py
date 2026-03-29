import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta, timezone, time as dt_time
import time

# ==========================================
# 1. CẤU HÌNH & KẾT NỐI (GMT+7)
# ==========================================
# Sửa tiêu đề trang hiển thị trên tab trình duyệt
st.set_page_config(page_title="Lab 109", page_icon="🔬", layout="wide", initial_sidebar_state="expanded")

VN_TZ = timezone(timedelta(hours=7))

# Custom CSS cho phong cách Gen Z: Bo tròn, đổ bóng mềm, font chữ hiện đại, tiêu đề màu hồng
st.markdown("""
    <style>
    .stButton>button { border-radius: 12px; transition: all 0.3s ease; font-weight: bold; }
    .stButton>button:hover { transform: translateY(-2px); box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
    .css-1d391kg { padding-top: 1rem; }
    div[data-testid="stExpander"] { border-radius: 12px; border: 1px solid #e0e0e0; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
    /* Đổi màu tiêu đề chính */
    h1 {
        text-align: center;
        color: #FF8DA1; /* Màu hồng */
    }
    </style>
""", unsafe_allow_html=True)

def get_now():
    return datetime.now(VN_TZ)

def parse_time(t_str):
    t_str = str(t_str).strip()
    if t_str in ["24:00", "2400"]: return dt_time(23, 59, 59)
    try: return datetime.strptime(t_str, "%H:%M").time()
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
    try: return pd.DataFrame(sheets[sheet_name].get_all_records())
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
                            if latest_end is None or e_time > latest_end: latest_end = e_time
                        except: pass
                    
                    if latest_end and now.time() >= latest_end:
                        cell = sheet_thietbi.find(device)
                        sheet_thietbi.update_cell(cell.row, 3, "Sẵn sàng")
                        sheet_thietbi.update_cell(cell.row, 4, "")
                        sheet_lichsu.append_row([now.strftime("%d/%m/%Y %H:%M:%S"), "🤖 Hệ thống", "Thu hồi tự động", device, "Hết giờ mượn"])
                        has_changes = True
        if has_changes: load_data.clear() 
    except: pass

# ==========================================
# 3. LOGIC ĐĂNG NHẬP
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state.update({'logged_in': False, 'ho_ten': "", 'tai_khoan': ""})

if not st.session_state['logged_in']:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # Đã đổi tên thành Lab 109 và màu sang hồng nhờ CSS ở trên
        st.markdown("<h1 style='text-align: center;'>🔬 Lab 109</h1>", unsafe_allow_html=True)
        
        # Cập nhật Slogan mới, viết thành 2 dòng và thêm icon cờ đan nhau
        st.markdown("""
            <p style='text-align: center; color: #666; font-size: 1.1em;'>
                Mỗi ngày đến Lab là một ngày vui 🐽
                <br>
                Sẽ vui hơn nếu chúng ta làm việc chăm chỉ
            </p>
        """, unsafe_allow_html=True)
        
        with st.form("login"):
            u = st.text_input("Tài khoản sinh viên")
            p = st.text_input("Mật khẩu", type="password")
            if st.form_submit_button("🚀 Đăng nhập", use_container_width=True):
                df_tk = load_data("TaiKhoan")
                match = df_tk[(df_tk['TaiKhoan'].astype(str) == u) & (df_tk['MatKhau'].astype(str) == p)]
                if not match.empty:
                    st.session_state.update({'logged_in': True, 'ho_ten': match.iloc[0]['HoTen'], 'tai_khoan': match.iloc[0]['TaiKhoan']})
                    st.rerun()
                else: st.error("Sai tài khoản hoặc mật khẩu!")

# ==========================================
# 4. GIAO DIỆN CHÍNH (SUPER APP UX)
# ==========================================
else:
    # --- TẢI DATA TỔNG ---
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
        load_data.clear(); df_tk = load_data("TaiKhoan")

    # --- TÍNH TOÁN BẢNG XẾP HẠNG NGẦM ---
    df_rank = pd.DataFrame(columns=['Thành viên', 'Tổng giờ'])
    my_current_hours = 0.0
    if not df_h.empty and len(df_h.columns) >= 3:
        col_time, col_user, col_action = df_h.columns[0], df_h.columns[1], df_h.columns[2]
        df_h_temp = df_h.copy()
        df_h_temp['Datetime'] = pd.to_datetime(df_h_temp[col_time], format="%d/%m/%Y %H:%M:%S", errors='coerce')
        now_naive = get_now().replace(tzinfo=None)
        start_of_week = now_naive - timedelta(days=now_naive.weekday())
        start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        
        df_week = df_h_temp[(df_h_temp['Datetime'] >= start_of_week) & (df_h_temp[col_user] != '🤖 Hệ thống')]
        user_stats = []
        if not df_week.empty:
            users = df_week[col_user].unique()
            for u in users:
                u_logs = df_week[(df_week[col_user] == u) & (df_week[col_action].str.contains("Check-in|Check-out", na=False))].sort_values('Datetime')
                total_secs, last_in = 0, None
                for _, r in u_logs.iterrows():
                    action = str(r[col_action])
                    if "Check-in" in action: last_in = r['Datetime']
                    elif "Check-out" in action and last_in is not None:
                        total_secs += (r['Datetime'] - last_in).total_seconds(); last_in = None 
                if last_in is not None: total_secs += (now_naive - last_in).total_seconds()
                total_hours = round(total_secs / 3600, 1)
                if total_hours > 0: user_stats.append({'Thành viên': u, 'Tổng giờ': total_hours})
        
        if user_stats:
            df_rank = pd.DataFrame(user_stats).sort_values(by='Tổng giờ', ascending=False).reset_index(drop=True)
            if st.session_state['ho_ten'] in df_rank['Thành viên'].values:
                my_current_hours = df_rank[df_rank['Thành viên'] == st.session_state['ho_ten']]['Tổng giờ'].iloc[0]

    # ---------------- SIDEBAR: HỒ SƠ & TRẠNG THÁI NHANH ----------------
    with st.sidebar:
        st.markdown(f"<div style='text-align: center;'><h2 style='margin-bottom: 0;'>👨‍🔬</h2><h3 style='margin-top: 0;'>{st.session_state['ho_ten']}</h3><p style='color: #888;'>⏱️ Giờ Lab tuần này: <b>{my_current_hours}h</b></p></div>", unsafe_allow_html=True)
        st.markdown("---")
        
        def update_status(new_status):
            cell = sheet_taikhoan.find(str(st.session_state['tai_khoan']))
            col_idx = df_tk.columns.get_loc("TrangThai") + 1
            sheet_taikhoan.update_cell(cell.row, col_idx, new_status)
            if new_status == "🟢 Ở Lab": sheet_lichsu.append_row([get_now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], "📍 Check-in Lab", "", ""])
            elif new_status == "⚪ Đã về": sheet_lichsu.append_row([get_now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], "🏃 Check-out", "", ""])
            load_data.clear(); st.rerun()

        my_status_arr = df_tk[df_tk['TaiKhoan'].astype(str) == str(st.session_state['tai_khoan'])]['TrangThai'].values
        current_my_status = my_status_arr[0] if len(my_status_arr) > 0 and my_status_arr[0] != "" else "⚪ Đã về"
        
        st.write("**🕹️ Cập nhật trạng thái:**")
        if current_my_status == "CẦN TRỢ GIÚP":
            st.markdown("<div style='background-color: #ff4b4b; color: white; padding: 10px; border-radius: 8px; text-align: center; font-weight: bold; margin-bottom: 10px;'>🚨 ĐANG BÁO ĐỘNG!</div>", unsafe_allow_html=True)
            if st.button("✅ Đã an toàn", use_container_width=True): update_status("🟢 Ở Lab")
        else:
            c1, c2, c3 = st.columns(3)
            with c1: 
                if st.button("🟢 Lab", use_container_width=True): update_status("🟢 Ở Lab")
            with c2: 
                if st.button("🟡 Bận", use_container_width=True): update_status("🟡 Đang bận")
            with c3: 
                if st.button("⚪ Về", use_container_width=True): update_status("⚪ Đã về")
            
            st.markdown(f"Đang hiển thị: **{current_my_status}**")
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🆘 NÚT KHẨN CẤP", use_container_width=True, type="primary"): update_status("CẦN TRỢ GIÚP")
            
        st.markdown("---")
        if st.button("🚪 Đăng xuất", use_container_width=True):
            st.session_state['logged_in'] = False; st.rerun()


    # ---------------- NỘI DUNG CHÍNH (MAIN UI) ----------------
    auto_return_devices()
    
    # Tiêu đề chính và slogan (đã cập nhật)
    st.markdown("<h1 style='text-align: center;'>🔬 Lab 109</h1>", unsafe_allow_html=True)
    st.markdown("""
        <p style='text-align: center; color: #666; font-size: 1.1em;'>
            Mỗi ngày đến Lab là một ngày vui. ⚔️
            <br>
            Cùng nhau nỗ lực, gặt hái thành công.
        </p>
    """, unsafe_allow_html=True)

    # Báo động toàn cầu (Hiển thị đầu trang)
    if "CẦN TRỢ GIÚP" in df_tk['TrangThai'].values:
        nguoi_can_giup = df_tk[df_tk['TrangThai'] == 'CẦN TRỢ GIÚP']['HoTen'].tolist()
        st.markdown(f"""
        <div style='background-color: #ff4b4b; color: white; padding: 15px; border-radius: 12px; text-align: center; margin-bottom: 20px; box-shadow: 0 4px 15px rgba(255,0,0,0.3); animation: blinker 1s linear infinite;'>
            <h3 style='margin:0; text-transform: uppercase;'>🚨 CẤP CỨU LAB: {', '.join(nguoi_can_giup)} 🚨</h3>
        </div>
        <style>@keyframes blinker {{ 50% {{ opacity: 0.7; }} }}</style>
        """, unsafe_allow_html=True)

    # --- TẠO POPUP KHI BẤM VÀO THẺ THÀNH VIÊN ---
    @st.dialog("📅 Lịch trình cá nhân")
    def show_member_schedule(mem_name):
        st.write(f"Danh sách lịch mượn máy của **{mem_name}**:")
        raw_bookings = df_lich_view[df_lich_view['Người sử dụng'] == mem_name]
        valid_bookings, cancel_options = [], []
        
        if not raw_bookings.empty:
            for _, r in raw_bookings.iterrows():
                try:
                    b_date = datetime.strptime(str(r['Ngày']), "%d/%m/%Y").date()
                    if b_date >= today:
                        valid_bookings.append(r)
                        ca = str(r['Ca làm việc'])
                        if " - " in ca and mem_name == st.session_state['ho_ten']:
                            s_str = ca.split(" - ")[0]
                            start_dt = datetime.combine(b_date, parse_time(s_str), tzinfo=VN_TZ)
                            if start_dt > get_now(): cancel_options.append(f"[{r['Ngày']}] {r['Thiết bị']} | {ca}")
                except: pass
        
        if not valid_bookings: 
            st.info(f"{mem_name} hiện chưa có lịch.")
        else:
            st.dataframe(pd.DataFrame(valid_bookings)[['Ngày', 'Ca làm việc', 'Thiết bị', 'Mục đích']], use_container_width=True, hide_index=True)
            
            if mem_name == st.session_state['ho_ten'] and cancel_options:
                st.markdown("---")
                with st.form("cancel_booking_modal"):
                    selected_cancel = st.selectbox("🗑️ Chọn lịch để hủy:", cancel_options)
                    if st.form_submit_button("Xác nhận Hủy", type="primary", use_container_width=True):
                        day = selected_cancel.split("] ")[0].replace("[", "")
                        dev, ca = selected_cancel.split("] ")[1].split(" | ")
                        records = sheet_lichtuan.get_all_records()
                        row_to_delete = next((i + 2 for i, r in enumerate(records) if str(r['Ngày']) == day and str(r['Thiết bị']) == dev and str(r['Ca làm việc']) == ca and str(r['Người sử dụng']) == st.session_state['ho_ten']), None)
                        if row_to_delete:
                            sheet_lichtuan.delete_rows(row_to_delete)
                            sheet_lichsu.append_row([get_now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], f"Hủy lịch ({ca})", dev, "Tự hủy"])
                            load_data.clear(); st.rerun()

    def format_device_option(dev_name):
        if df_tb.empty or dev_name not in df_tb['Tên'].values: return dev_name
        row = df_tb[df_tb['Tên'] == dev_name].iloc[0]
        status, user = row.get('Trạng thái', 'Sẵn sàng'), row.get('Người sử dụng', '')
        note_col = "Ghi chú" if "Ghi chú" in df_tb.columns else None
        note = f" | 📝 {row.get(note_col, '')}" if note_col and row.get(note_col, '') else ""
        if status == 'Sẵn sàng': return f"🟢 {dev_name} (Rảnh){note}"
        else: return f"🔴 {dev_name} (Bận: {user.split()[-1] if user else ''}){note}"

    # ================= ĐIỀU HƯỚNG TABS CHÍNH (Super App Layout) =================
    mt1, mt2, mt3 = st.tabs(["🏠 Tổng quan Lab", "🔬 Máy móc & Lịch", "🏆 Bảng vinh danh"])

    # --- TAB 1: TỔNG QUAN LAB (Thành viên) ---
    with mt1:
        st.markdown("### 🌐 Không gian làm việc")
        st.write("Nhấn vào tên thành viên để xem lịch trình phối hợp nhóm.")
        
        if "TrangThai" not in df_tk.columns: st.warning("Đang đồng bộ...")
        else:
            cols = st.columns(4) 
            for idx, row in df_tk.iterrows():
                mem_name = row['HoTen']
                mem_status = row.get('TrangThai', '⚪ Đã về')
                if not mem_status: mem_status = "⚪ Đã về"
                
                rank_str = ""
                if not df_rank.empty and mem_name in df_rank['Thành viên'].values:
                    rank_idx = df_rank[df_rank['Thành viên'] == mem_name].index[0]
                    hours = df_rank.iloc[rank_idx]['Tổng giờ']
                    if rank_idx == 0: rank_str = f"🥇 Top 1 ({hours}h)"
                    elif rank_idx == 1: rank_str = f"🥈 Top 2 ({hours}h)"
                    elif rank_idx == 2: rank_str = f"🥉 Top 3 ({hours}h)"
                    else: rank_str = f"🏅 Top {rank_idx + 1} ({hours}h)"
                
                with cols[idx % 4]:
                    bg_color, border_color, text_color, icon = "#f8f9fa", "#dee2e6", "#6c757d", "⚪"
                    if mem_status == "CẦN TRỢ GIÚP": bg_color, border_color, text_color, icon = "#ff4b4b", "darkred", "white", "🚨"
                    elif "Ở Lab" in mem_status: bg_color, border_color, text_color, icon = "#e6f4ea", "#c3e6cb", "#155724", "🟢"
                    elif "Đang bận" in mem_status: bg_color, border_color, text_color, icon = "#fff8e1", "#ffeeba", "#856404", "🟡"

                    st.markdown(f"""
                    <div style='background-color: {bg_color}; color: {text_color}; padding: 15px; border-radius: 12px 12px 0 0; text-align: center; border: 1px solid {border_color}; border-bottom: none;'>
                        <h2 style='margin: 0;'>{icon}</h2>
                        <h5 style='margin: 5px 0;'>{mem_name}</h5>
                        <p style='margin: 0; font-size: 12px; font-weight:bold; color: #555;'>{rank_str}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if st.button("📅 Xem lịch", key=f"btn_pop_{idx}", use_container_width=True):
                        show_member_schedule(mem_name)

    # --- TAB 2: MÁY MÓC & LỊCH TRÌNH ---
    with mt2:
        # Sử dụng sub-tabs để chia nhỏ hành động, tối ưu không gian rộng
        sub1, sub2, sub3 = st.tabs(["📝 Đăng ký mượn", "🔄 Trả thiết bị", "🕒 Lịch sử mượn"])
        
        with sub1:
            c_filter, _ = st.columns([1, 1])
            with c_filter:
                view_mode = st.selectbox("Chọn thiết bị:", all_devices if all_devices else ["Chưa có dữ liệu"], format_func=format_device_option if all_devices else lambda x: x)
            
            with st.expander(f"Biểu đồ Timeline: {view_mode}", expanded=True):
                df_dev = df_lich_view[df_lich_view['Thiết bị'] == view_mode] if not df_lich_view.empty else pd.DataFrame()
                if not df_dev.empty: df_dev = df_dev.drop_duplicates(subset=['Ngày', 'Ca làm việc', 'Thiết bị'])
                
                html_timeline = "<div style='width: 100%; font-family: sans-serif; overflow-x: auto; padding-bottom: 10px;'><div style='display: flex; align-items: flex-end; width: 100%; min-width: 700px; margin-bottom: 5px; font-size: 11px; color: #666; font-weight: bold;'><div style='width: 70px;'></div><div style='flex-grow: 1; position: relative; height: 20px; border-bottom: 2px solid #aaa;'>"
                for h in range(0, 25, 2):
                    left_pct = (h / 24.0) * 100
                    html_timeline += f"<div style='position: absolute; left: {left_pct}%; transform: translateX(-50%); bottom: 2px;'>{h:02d}:00</div><div style='position: absolute; left: {left_pct}%; width: 2px; height: 6px; background-color: #aaa; bottom: -2px; transform: translateX(-50%);'></div>"
                html_timeline += "</div></div>"
                
                for d in days_7:
                    html_timeline += f"<div style='display: flex; align-items: center; margin-bottom: 10px; min-width: 700px;'><div style='width: 70px; font-size: 13px; font-weight: bold; color: #444;'>{d[:5]}</div><div style='flex-grow: 1; position: relative; height: 36px; background-color: #f8f9fa; border-radius: 6px; border: 1px solid #e0e0e0;'>"
                    for h in range(2, 24, 2):
                        html_timeline += f"<div style='position: absolute; left: {(h/24)*100}%; width: 1px; height: 100%; background-color: #e9ecef; z-index: 1;'></div>"
                    
                    df_day = df_dev[df_dev['Ngày'] == d]
                    if not df_day.empty:
                        for _, r in df_day.iterrows():
                            ca = str(r['Ca làm việc'])
                            if " - " in ca:
                                try:
                                    s_str, e_str = ca.split(" - ")
                                    s_time, e_time = parse_time(s_str), parse_time(e_str)
                                    start_min, end_min = s_time.hour * 60 + s_time.minute, e_time.hour * 60 + e_time.minute
                                    if end_min <= start_min: end_min = 24 * 60
                                    
                                    left_pct, width_pct = (start_min / (24 * 60)) * 100, ((end_min - start_min) / (24 * 60)) * 100
                                    user = r['Người sử dụng']
                                    color = "#4285f4" if user == st.session_state.get('ho_ten', '') else "#ea4335" 
                                    display_text = f"{s_str}-{e_str} ({user.split()[-1]})"
                                    
                                    block_html = f"<div style='position: absolute; left: {left_pct}%; width: {width_pct}%; height: 100%; background-color: {color}; border-radius: 4px; color: white; font-size: 11px; display: flex; align-items: center; justify-content: center; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; box-shadow: 0 2px 4px rgba(0,0,0,0.15); z-index: 2;'><span style='padding: 0 4px;'>{display_text}</span></div>"
                                    html_timeline += block_html
                                except: pass
                    html_timeline += "</div></div>"
                html_timeline += "</div>"
                st.markdown(html_timeline, unsafe_allow_html=True)
                
            with st.form("smart_booking_main"):
                c1, c2, c3, c4 = st.columns([1.5, 1, 1, 2])
                with c1: d_pick = st.date_input("🗓️ Chọn ngày", min_value=today)
                with c2: 
                    now_minute = get_now().minute
                    default_idx = get_now().hour * 4 + ((now_minute // 15) * 15 // 15)
                    t_start_str = st.selectbox("⏳ Từ lúc:", time_options, index=default_idx)
                with c3: 
                    t_end_str = st.selectbox("⏳ Đến lúc:", time_options, index=min(default_idx + 4, 95)) 
                with c4: note = st.text_input("Mục đích (VD: Đo phổ)")
                
                if st.form_submit_button("🔥 Xác nhận Đăng ký", type="primary"):
                    t_start, t_end = parse_time(t_start_str), parse_time(t_end_str)
                    d_str, today_str, current_t = d_pick.strftime("%d/%m/%Y"), get_now().strftime("%d/%m/%Y"), get_now().time()
                    
                    if t_end <= t_start: st.error("❌ Lỗi: Giờ kết thúc phải lớn hơn giờ bắt đầu!"); st.stop()
                    if d_str == today_str and t_end <= current_t: st.error(f"⏳ Lỗi: Khoảng thời gian này đã qua!"); st.stop()
                    
                    df_lich_rt = pd.DataFrame(sheet_lichtuan.get_all_records())
                    conflict_found = []
                    if not df_lich_rt.empty:
                        df_day_device = df_lich_rt[(df_lich_rt['Ngày'] == d_str) & (df_lich_rt['Thiết bị'] == view_mode)]
                        for _, row in df_day_device.iterrows():
                            try:
                                exist_start, exist_end = parse_time(row['Ca làm việc'].split(" - ")[0]), parse_time(row['Ca làm việc'].split(" - ")[1])
                                if t_start < exist_end and exist_start < t_end and row['Người sử dụng'] != st.session_state['ho_ten']:
                                    conflict_found.append(f"{row['Ca làm việc']} (bởi {row['Người sử dụng']})")
                            except: pass

                    if conflict_found: st.error(f"❌ Kẹt lịch:\n" + "\n".join([f"- {c}" for c in conflict_found]))
                    else:
                        ca_lam_viec_str = f"{t_start_str} - {t_end_str}"
                        sheet_lichtuan.append_row([d_str, ca_lam_viec_str, st.session_state['ho_ten'], view_mode, note])
                        is_active_now = (d_str == today_str) and (t_start <= current_t <= t_end)
                        if is_active_now:
                            cell = sheet_thietbi.find(view_mode)
                            sheet_thietbi.update_cell(cell.row, 3, "Đang mượn")
                            sheet_thietbi.update_cell(cell.row, 4, st.session_state['ho_ten'])
                            sheet_lichsu.append_row([get_now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], f"Sử dụng trực tiếp ({ca_lam_viec_str})", view_mode, note])
                            st.success(f"✅ Đã mượn thành công!")
                        else:
                            sheet_lichsu.append_row([get_now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], f"Đặt lịch ({ca_lam_viec_str})", view_mode, note])
                            st.success("✅ Đã chốt lịch thành công!")
                        load_data.clear(); st.rerun()

        with sub2:
            st.markdown("#### Thiết bị bạn đang giữ")
            if "Người sử dụng" in df_tb.columns:
                my_list = df_tb[df_tb["Người sử dụng"] == st.session_state['ho_ten']]['Tên'].tolist()
                if not my_list: st.info("Bạn hiện không mượn thiết bị nào.")
                else:
                    with st.form("return_form_main"):
                        dev_ret = st.selectbox("Chọn thiết bị để trả:", my_list)
                        return_note = st.text_input("📝 Ghi chú (nếu máy có vấn đề):")
                        if st.form_submit_button("Xác nhận Trả máy", type="primary"):
                            cell = sheet_thietbi.find(dev_ret)
                            sheet_thietbi.update_cell(cell.row, 3, "Sẵn sàng")
                            sheet_thietbi.update_cell(cell.row, 4, "")
                            note_col_index = df_tb.columns.get_loc("Ghi chú") + 1 if "Ghi chú" in df_tb.columns else 5 
                            sheet_thietbi.update_cell(cell.row, note_col_index, return_note)
                            
                            today_str, curr_t, curr_str = get_now().strftime("%d/%m/%Y"), get_now().time(), get_now().strftime("%H:%M")
                            records = sheet_lichtuan.get_all_records()
                            row_to_update, new_ca = None, ""
                            for i, r in enumerate(records):
                                if str(r['Thiết bị']) == dev_ret and str(r['Người sử dụng']) == st.session_state['ho_ten'] and str(r['Ngày']) == today_str:
                                    ca = str(r['Ca làm việc'])
                                    if " - " in ca:
                                        s_t, e_t = parse_time(ca.split(" - ")[0]), parse_time(ca.split(" - ")[1])
                                        if s_t and e_t and s_t <= curr_t <= e_t:
                                            row_to_update, new_ca = i + 2, f"{ca.split(' - ')[0]} - {curr_str}"
                                            break
                            if row_to_update: sheet_lichtuan.update_cell(row_to_update, 2, new_ca) 
                            
                            sheet_lichsu.append_row([get_now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], "Trả sớm", dev_ret, return_note])
                            st.success(f"✅ Đã trả {dev_ret}."); load_data.clear(); st.rerun()

        with sub3:
            st.markdown("#### Nhật ký hệ thống")
            if not df_h.empty: st.dataframe(df_h.iloc[::-1], use_container_width=True, hide_index=True)

    # --- TAB 3: BẢNG VINH DANH (Gamification Detail) ---
    with mt3:
        st.markdown("### 🏆 Bảng xếp hạng Tuần")
        st.write("Dựa trên thời gian check-in thực tế. Cố gắng lọt Top 3 nhé!")
        if not df_rank.empty:
            stats = df_rank.copy()
            c1, c2, c3 = st.columns(3)
            if len(stats) >= 1:
                with c2: st.markdown(f"<div style='text-align:center; padding:20px; background:#fff8e1; border-radius:15px; border: 2px solid #ffc107; box-shadow: 0 8px 15px rgba(255,193,7,0.2); transform: scale(1.05);'><h1 style='font-size: 60px; margin:0;'>🥇</h1><h3 style='margin: 10px 0; color: #b78100;'>{stats.iloc[0]['Thành viên']}</h3><p style='margin:0; font-size:20px; font-weight:bold;'>{stats.iloc[0]['Tổng giờ']}h</p></div>", unsafe_allow_html=True)
            if len(stats) >= 2:
                with c1: st.markdown(f"<div style='text-align:center; padding:20px; background:#f8f9fa; border-radius:15px; border: 2px solid #adb5bd; margin-top: 40px;'><h1 style='font-size: 50px; margin:0;'>🥈</h1><h4 style='margin: 10px 0; color: #495057;'>{stats.iloc[1]['Thành viên']}</h4><p style='margin:0; font-size:18px; font-weight:bold;'>{stats.iloc[1]['Tổng giờ']}h</p></div>", unsafe_allow_html=True)
            if len(stats) >= 3:
                with c3: st.markdown(f"<div style='text-align:center; padding:20px; background:#fdf3eb; border-radius:15px; border: 2px solid #d99a6c; margin-top: 50px;'><h1 style='font-size: 45px; margin:0;'>🥉</h1><h4 style='margin: 10px 0; color: #9c5c2d;'>{stats.iloc[2]['Thành viên']}</h4><p style='margin:0; font-size:18px; font-weight:bold;'>{stats.iloc[2]['Tổng giờ']}h</p></div>", unsafe_allow_html=True)
            
            st.write("")
            stats.index = stats.index + 1
            st.dataframe(stats, use_container_width=True)
        else:
            st.info("Chưa có ai check-in tuần này.")
