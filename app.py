import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta, timezone, time as dt_time
import time
import urllib.parse 
import json 

# ==========================================
# 1. CẤU HÌNH & KẾT NỐI (GMT+7)
# ==========================================
st.set_page_config(page_title="Lab 109 - Quản lý Lab", page_icon="🔬", layout="wide", initial_sidebar_state="expanded")

VN_TZ = timezone(timedelta(hours=7))

st.markdown("""
    <style>
    .stButton>button { border-radius: 12px; transition: all 0.3s ease; font-weight: bold; }
    .stButton>button:hover { transform: translateY(-2px); box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
    .css-1d391kg { padding-top: 1rem; }
    div[data-testid="stExpander"] { border-radius: 12px; border: 1px solid #e0e0e0; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
    h1 { text-align: center; color: #ff69b4; }
    div[data-testid="stChatMessage"] { background-color: #f1f8ff; border-radius: 15px; padding: 10px; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

def get_now():
    return datetime.now(VN_TZ)

def parse_time(t_str):
    t_str = str(t_str).strip()
    if t_str in ["24:00", "2400"]: return dt_time(23, 59, 59)
    try: return datetime.strptime(t_str, "%H:%M").time()
    except: return None

def get_or_create_sheet(sh, name, cols):
    try:
        return sh.worksheet(name)
    except Exception:
        ws = sh.add_worksheet(title=name, rows=1000, cols=len(cols))
        ws.append_row(cols)
        return ws

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
            "LichTuan": sh.worksheet("LichTuan"),
            "Chat": get_or_create_sheet(sh, "Chat", ["Thời gian", "Người gửi", "Nội dung"]),
            "TaiLieu": get_or_create_sheet(sh, "TaiLieu", ["Thời gian", "Người đăng", "Tên tài liệu", "Link"]),
            "ThongBao": get_or_create_sheet(sh, "ThongBao", ["ID", "Thời gian", "Người đăng", "Loại", "Nội dung", "Lựa chọn", "Bình chọn"])
        }
    except Exception as e:
        st.error(f"❌ Lỗi kết nối Google Sheets: {e}")
        st.stop()

sheets = init_google_sheets()
sheet_thietbi = sheets["ThietBi"]
sheet_taikhoan = sheets["TaiKhoan"]
sheet_lichsu = sheets["LichSu"]
sheet_lichtuan = sheets["LichTuan"]
sheet_chat = sheets["Chat"]
sheet_tailieu = sheets["TaiLieu"]
sheet_thongbao = sheets["ThongBao"]

@st.cache_data(ttl=10, show_spinner=False)
def load_data(sheet_name):
    try: return pd.DataFrame(sheets[sheet_name].get_all_records())
    except gspread.exceptions.APIError:
        time.sleep(2)
        return pd.DataFrame(sheets[sheet_name].get_all_records())

# ==========================================
# 2. ROBOT ĐỒNG BỘ TRẠNG THÁI
# ==========================================
def auto_update_devices():
    try:
        df_tb = load_data("ThietBi")
        df_lich = load_data("LichTuan")
        if df_tb.empty or df_lich.empty: return
        
        now = get_now()
        today_str = now.strftime("%d/%m/%Y")
        curr_time = now.time()
        
        df_today = df_lich[df_lich['Ngày'] == today_str]
        has_changes = False

        for idx, row in df_tb.iterrows():
            device = str(row.get('Tên'))
            current_status = str(row.get('Trạng thái'))
            current_user = str(row.get('Người sử dụng', ''))
            
            active_booking = None
            if not df_today.empty:
                dev_bookings = df_today[df_today['Thiết bị'] == device]
                for _, b_row in dev_bookings.iterrows():
                    ca = str(b_row['Ca làm việc'])
                    if " - " in ca:
                        try:
                            s_str, e_str = ca.split(" - ")
                            s_time, e_time = parse_time(s_str), parse_time(e_str)
                            if s_time and e_time and s_time <= curr_time <= e_time:
                                active_booking = b_row
                                break
                        except: pass
            
            row_num = int(idx) + 2
            
            if active_booking is not None:
                expected_user = str(active_booking['Người sử dụng'])
                if current_status != 'Đang mượn' or current_user != expected_user:
                    sheet_thietbi.update_cell(row_num, 3, "Đang mượn")
                    sheet_thietbi.update_cell(row_num, 4, expected_user)
                    has_changes = True
            else:
                if current_status != 'Sẵn sàng':
                    sheet_thietbi.update_cell(row_num, 3, "Sẵn sàng")
                    sheet_thietbi.update_cell(row_num, 4, "")
                    has_changes = True
                    
        if has_changes: load_data.clear() 
    except: pass

# ==========================================
# 3. LOGIC ĐĂNG NHẬP KÈM KIỂM TRA CẤP ĐỘ
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state.update({'logged_in': False, 'ho_ten': "", 'tai_khoan': "", 'cap_do': 2})

if not st.session_state['logged_in']:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align: center;'>🔬 Lab 109</h1>", unsafe_allow_html=True)
        st.markdown("""
            <p style='text-align: center; color: #666; font-size: 1.1em;'>
                Mỗi ngày lên lab là một ngày vui 🇻🇳
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
                    role_val = match.iloc[0].get('CapDo', 2)
                    if pd.isna(role_val) or str(role_val).strip() == "": role_val = 2
                    
                    st.session_state.update({
                        'logged_in': True, 
                        'ho_ten': match.iloc[0]['HoTen'], 
                        'tai_khoan': match.iloc[0]['TaiKhoan'],
                        'cap_do': int(role_val)
                    })
                    st.rerun()
                else: st.error("Sai tài khoản hoặc mật khẩu!")

# ==========================================
# 4. GIAO DIỆN CHÍNH (SUPER APP UX)
# ==========================================
else:
    df_tk = load_data("TaiKhoan")
    df_tb = load_data("ThietBi")
    df_lich_view = load_data("LichTuan")
    df_h = load_data("LichSu")
    df_chat = load_data("Chat")
    df_tailieu = load_data("TaiLieu")
    df_thongbao = load_data("ThongBao")
    all_devices = df_tb['Tên'].tolist() if not df_tb.empty else []
    
    my_role = st.session_state.get('cap_do', 2)
    role_badge = "👑 Quản lý" if my_role == 1 else ("🎒 Khách" if my_role == 3 else "👨‍🔬 Nội bộ")
    
    today = get_now().date()
    days_7 = [(today + timedelta(days=i)).strftime("%d/%m/%Y") for i in range(7)]
    time_options = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 15, 30, 45)]
    
    if not df_tk.empty:
        missing_cols = []
        if "TrangThai" not in df_tk.columns: missing_cols.append("TrangThai")
        if "Avatar" not in df_tk.columns: missing_cols.append("Avatar")
        if "CapDo" not in df_tk.columns: missing_cols.append("CapDo")
        
        if missing_cols:
            num_cols = len(df_tk.columns)
            for i, col in enumerate(missing_cols):
                sheet_taikhoan.update_cell(1, num_cols + i + 1, col)
            load_data.clear()
            df_tk = load_data("TaiKhoan")

    # --- TÍNH TOÁN BẢNG XẾP HẠNG NGẦM ---
    df_rank = pd.DataFrame(columns=['Thành viên', 'Tổng giờ'])
    my_current_hours = 0.0
    if not df_h.empty and len(df_h.columns) >= 3:
        col_time, col_user, col_action = df_h.columns[0], df_h.columns[1], df_h.columns[2]
        df_h_temp = df_h.copy()
        
        df_h_temp['Datetime'] = pd.to_datetime(df_h_temp[col_time], dayfirst=True, errors='coerce')
        if df_h_temp['Datetime'].isna().all():
            df_h_temp['Datetime'] = pd.to_datetime(df_h_temp[col_time], format="%d/%m/%Y %H:%M:%S", errors='coerce')
            
        now_naive = get_now().replace(tzinfo=None)
        start_of_week = now_naive - timedelta(days=now_naive.weekday())
        start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
        
        df_week = df_h_temp[(df_h_temp['Datetime'] >= start_of_week) & (df_h_temp[col_user] != '🤖 Hệ thống')]
        user_stats = []
        if not df_week.empty:
            users = df_week[col_user].unique()
            for u in users:
                u_logs = df_week[(df_week[col_user] == u) & (df_week[col_action].str.contains("Check-in|Check-out", na=False))].sort_values('Datetime')
                if u_logs.empty: continue 
                
                total_secs, last_in = 0, None
                for _, r in u_logs.iterrows():
                    action = str(r[col_action])
                    if "Check-in" in action: last_in = r['Datetime']
                    elif "Check-out" in action and last_in is not None:
                        total_secs += (r['Datetime'] - last_in).total_seconds(); last_in = None 
                
                if last_in is not None: total_secs += max(0, (now_naive - last_in).total_seconds())
                total_hours = round(total_secs / 3600, 2) 
                user_stats.append({'Thành viên': u, 'Tổng giờ': total_hours})
        
        if user_stats:
            df_rank = pd.DataFrame(user_stats).sort_values(by='Tổng giờ', ascending=False).reset_index(drop=True)
            if st.session_state['ho_ten'] in df_rank['Thành viên'].values:
                my_current_hours = df_rank[df_rank['Thành viên'] == st.session_state['ho_ten']]['Tổng giờ'].iloc[0]

    # --- 1. KHUNG POPUP BẢNG TIN & KHẢO SÁT (ĐÃ NÂNG CẤP) ---
    @st.dialog("❗ Bảng Tin & Khảo Sát Lab", width="large")
    def show_notice_board():
        st.write("Cập nhật thông tin và vote các vấn đề quan trọng của Lab.")
        
        # Chỉ Admin (Level 1) hoặc Nội bộ (Level 2) mới được phép tạo bài
        if my_role <= 2:
            with st.expander("✍️ Đăng Thông báo / Khảo sát mới", expanded=False):
                with st.form("create_notice"):
                    n_type = st.radio("Loại:", ["Thông báo 📢", "Bầu chọn 📊"], horizontal=True)
                    n_content = st.text_area("Nội dung (Bắt buộc):")
                    n_opts = st.text_input("Các lựa chọn nếu là Bầu chọn (Cách nhau bởi dấu phẩy, VD: Có, Không):")
                        
                    if st.form_submit_button("Đăng tải", type="primary"):
                        if n_content.strip():
                            nid = str(int(time.time()))
                            t_str = get_now().strftime("%d/%m/%Y %H:%M")
                            sheet_thongbao.append_row([nid, t_str, st.session_state['ho_ten'], n_type, n_content.strip(), n_opts.strip(), "{}"])
                            load_data.clear(); st.rerun()
                        else:
                            st.error("Vui lòng nhập nội dung.")
            st.markdown("---")
            
        if df_thongbao.empty:
            st.info("Hiện chưa có thông báo nào.")
        else:
            for idx, r in df_thongbao.iloc[::-1].iterrows():
                row_num = int(idx) + 2
                
                # Nút Xóa bài viết cho Admin hoặc Chính chủ
                col_h1, col_h2 = st.columns([4, 1])
                with col_h1:
                    st.markdown(f"**{r['Người đăng']}** • <span style='font-size:12px; color:#888;'>{r['Thời gian']}</span>", unsafe_allow_html=True)
                with col_h2:
                    if my_role == 1 or r['Người đăng'] == st.session_state['ho_ten']:
                        if st.button("🗑️ Xóa", key=f"del_{r['ID']}", help="Xóa bài viết này"):
                            sheet_thongbao.delete_rows(row_num)
                            load_data.clear(); st.rerun()
                
                # Hiển thị nội dung bài viết
                if "Thông báo" in str(r['Loại']):
                    st.info(f"📢 {r['Nội dung']}")
                else:
                    st.warning(f"📊 **Khảo sát:** {r['Nội dung']}")
                    
                    opts = [o.strip() for o in str(r['Lựa chọn']).split(",")] if r['Lựa chọn'] else []
                    votes = {}
                    try: votes = json.loads(str(r['Bình chọn']))
                    except: pass
                    
                    my_vote = votes.get(st.session_state['ho_ten'], None)
                    
                    if my_vote:
                        st.success(f"Bạn đã chọn: **{my_vote}**")
                        
                        # Hiện thanh biểu đồ kết quả
                        total_votes = len(votes) if len(votes) > 0 else 1
                        for o in opts:
                            count = sum(1 for v in votes.values() if v == o)
                            pct = int((count / total_votes) * 100)
                            st.markdown(f"<div style='font-size:13px;'>{o} ({count} phiếu)</div>", unsafe_allow_html=True)
                            st.progress(pct)
                            
                        # Nút Đổi / Xóa Vote của người dùng
                        if st.button("🔄 Đổi ý / Xóa bình chọn", key=f"revote_{r['ID']}"):
                            del votes[st.session_state['ho_ten']]
                            sheet_thongbao.update_cell(row_num, 7, json.dumps(votes, ensure_ascii=False))
                            load_data.clear(); st.rerun()
                    else:
                        # Giao diện cho phép chọn vote
                        with st.form(f"vote_form_{r['ID']}"):
                            choice = st.radio("Chọn ý kiến của bạn:", opts)
                            if st.form_submit_button("Chốt Bình chọn"):
                                votes[st.session_state['ho_ten']] = choice
                                sheet_thongbao.update_cell(row_num, 7, json.dumps(votes, ensure_ascii=False))
                                load_data.clear(); st.rerun()
                                
                st.markdown("<hr style='margin: 15px 0;'>", unsafe_allow_html=True)


    # --- 2. KHUNG POPUP CHAT CHUNG LAB ---
    @st.dialog("💬 Khung Chat Lab 109")
    def show_chat_popup():
        st.write("Cùng trò chuyện, nhắc lịch, hoặc hỗ trợ nhau nhé!")
        chat_container = st.container(height=350)
        if not df_chat.empty:
            for _, r in df_chat.tail(30).iterrows():
                is_me = r['Người gửi'] == st.session_state['ho_ten']
                with chat_container.chat_message("user" if is_me else "assistant"):
                    st.markdown(f"<span style='font-size:12px; color:#888;'><b>{r['Người gửi']}</b> • {r['Thời gian']}</span>", unsafe_allow_html=True)
                    st.write(r['Nội dung'])
        else:
            chat_container.info("Chưa có tin nhắn nào. Hãy là người mở lời!")
            
        with st.form("chat_form", clear_on_submit=True):
            cols = st.columns([4, 1])
            with cols[0]: msg = st.text_input("Nhập tin nhắn...", label_visibility="collapsed", placeholder="Nhắn gì đó...")
            with cols[1]: submit_msg = st.form_submit_button("Gửi 🚀", use_container_width=True)
            
            if submit_msg and msg.strip():
                sheet_chat.append_row([get_now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], msg.strip()])
                load_data.clear()
                st.rerun()

    # ---------------- SIDEBAR: HỒ SƠ & TRẠNG THÁI NHANH ----------------
    with st.sidebar:
        my_avatar_url = ""
        if "Avatar" in df_tk.columns:
            my_avatar_col = df_tk[df_tk['TaiKhoan'].astype(str) == str(st.session_state['tai_khoan'])]['Avatar'].values
            my_avatar_url = my_avatar_col[0] if len(my_avatar_col) > 0 and str(my_avatar_col[0]).strip() != "" else ""
        
        if not my_avatar_url:
            encoded_name = urllib.parse.quote(st.session_state['ho_ten'])
            my_avatar_url = f"https://ui-avatars.com/api/?name={encoded_name}&background=random&color=fff&size=128&bold=true"

        hours_display = f"<p style='color: #888; font-size: 14px; margin-top: 0px;'>⏱️ Giờ Lab tuần này: <b>{my_current_hours}h</b></p>" if my_role <= 2 else ""

        st.markdown(f"""
        <div style='text-align: center; margin-bottom: 10px;'>
            <img src='{my_avatar_url}' style='width: 90px; height: 90px; border-radius: 50%; border: 3px solid #ff69b4; box-shadow: 0 4px 10px rgba(0,0,0,0.15); object-fit: cover;'>
            <h3 style='margin-top: 10px; margin-bottom: 0;'>{st.session_state['ho_ten']}</h3>
            <p style='color: #666; font-size: 13px; font-weight: bold; margin-top: 2px; margin-bottom: 5px;'>{role_badge}</p>
            {hours_display}
        </div>
        """, unsafe_allow_html=True)
        st.markdown("---")
        
        # Tiện ích Mượn/Trả đã được chuyển ra ngoài
        def update_status(new_status):
            cell = sheet_taikhoan.find(str(st.session_state['tai_khoan']))
            col_idx = df_tk.columns.get_loc("TrangThai") + 1
            sheet_taikhoan.update_cell(cell.row, col_idx, new_status)
            if new_status == "🟢 Ở Lab": 
                sheet_lichsu.append_row([get_now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], "📍 Check-in Lab", "", ""])
            elif new_status == "🟡 Đang bận": 
                sheet_lichsu.append_row([get_now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], "📍 Check-in (Bận)", "", ""])
            elif new_status == "⚪ Đã về": 
                sheet_lichsu.append_row([get_now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], "🏃 Check-out", "", ""])
                
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
        
        # Tabs mini cho Sidebar để Mượn / Trả thiết bị nhanh
        st.markdown("### 🛠️ THAO TÁC NHANH")
        tab_dk, tab_ls, tab_tra = st.tabs(["📅 Mượn", "🕒 Lịch", "🔄 Trả"])
        
        def format_device_option(dev_name):
            if df_tb.empty or dev_name not in df_tb['Tên'].values: return dev_name
            row = df_tb[df_tb['Tên'] == dev_name].iloc[0]
            status, user = row.get('Trạng thái', 'Sẵn sàng'), row.get('Người sử dụng', '')
            if status == 'Sẵn sàng': return f"🟢 {dev_name}"
            else: return f"🔴 {dev_name} ({user.split()[-1] if user else ''})"
            
        with tab_dk:
            view_mode = st.selectbox("Chọn thiết bị:", all_devices if all_devices else ["Chưa có dữ liệu"], format_func=format_device_option if all_devices else lambda x: x)
            with st.form("smart_booking"):
                d_pick = st.date_input("🗓️ Ngày")
                now_minute = get_now().minute
                default_idx = get_now().hour * 4 + ((now_minute // 15) * 15 // 15)
                t_start_str = st.selectbox("⏳ Từ lúc:", time_options, index=default_idx)
                t_end_str = st.selectbox("⏳ Đến lúc:", time_options, index=min(default_idx + 4, 95)) 
                note = st.text_input("Ghi chú")
                if st.form_submit_button("Xác nhận", use_container_width=True):
                    t_start, t_end = parse_time(t_start_str), parse_time(t_end_str)
                    d_str, today_str, current_t = d_pick.strftime("%d/%m/%Y"), get_now().strftime("%d/%m/%Y"), get_now().time()
                    if t_end <= t_start: st.error("Lỗi: Giờ kết thúc < giờ bắt đầu!"); st.stop()
                    if d_str == today_str and t_end <= current_t: st.error("Lỗi: Đã qua giờ này!"); st.stop()
                    
                    df_lich_rt = pd.DataFrame(sheet_lichtuan.get_all_records())
                    conflict_found = []
                    if not df_lich_rt.empty:
                        df_day_device = df_lich_rt[(df_lich_rt['Ngày'] == d_str) & (df_lich_rt['Thiết bị'] == view_mode)]
                        for _, row in df_day_device.iterrows():
                            try:
                                exist_start, exist_end = parse_time(row['Ca làm việc'].split(" - ")[0]), parse_time(row['Ca làm việc'].split(" - ")[1])
                                if t_start < exist_end and exist_start < t_end and row['Người sử dụng'] != st.session_state['ho_ten']:
                                    conflict_found.append(f"{row['Ca làm việc']} ({row['Người sử dụng'].split()[-1]})")
                            except: pass

                    if conflict_found: st.error("Kẹt lịch:\n" + "\n".join([f"- {c}" for c in conflict_found]))
                    else:
                        ca_lam_viec_str = f"{t_start_str} - {t_end_str}"
                        sheet_lichtuan.append_row([d_str, ca_lam_viec_str, st.session_state['ho_ten'], view_mode, note])
                        if (d_str == today_str) and (t_start <= current_t <= t_end):
                            cell = sheet_thietbi.find(view_mode)
                            sheet_thietbi.update_cell(cell.row, 3, "Đang mượn")
                            sheet_thietbi.update_cell(cell.row, 4, st.session_state['ho_ten'])
                            sheet_lichsu.append_row([get_now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], f"Sử dụng ({ca_lam_viec_str})", view_mode, note])
                        else:
                            sheet_lichsu.append_row([get_now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], f"Đặt lịch ({ca_lam_viec_str})", view_mode, note])
                        load_data.clear(); st.rerun()

        with tab_ls:
            if not df_h.empty and len(df_h.columns) >= 4: 
                col_time, col_action, col_dev = df_h.columns[0], df_h.columns[2], df_h.columns[3]
                mini_df = df_h.iloc[::-1][[col_time, col_action, col_dev]].head(15)
                st.dataframe(mini_df, use_container_width=True, hide_index=True)

        with tab_tra:
            if "Người sử dụng" in df_tb.columns:
                my_list = df_tb[df_tb["Người sử dụng"] == st.session_state['ho_ten']]['Tên'].tolist()
                if not my_list: st.success("Không mượn máy nào.")
                else:
                    with st.form("return_form"):
                        dev_ret = st.selectbox("Chọn thiết bị:", my_list)
                        return_note = st.text_input("Ghi chú trả máy")
                        if st.form_submit_button("Xác nhận Trả", use_container_width=True):
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
                            load_data.clear(); st.rerun()

        st.markdown("---")
        if st.button("🚪 Đăng xuất", use_container_width=True):
            st.session_state['logged_in'] = False; st.rerun()


    # ---------------- NỘI DUNG CHÍNH (MAIN UI) ----------------
    auto_update_devices()
    
    st.markdown("<h1 style='text-align: center; margin-bottom: 0px;'>🔬 Lab 109</h1>", unsafe_allow_html=True)
    st.markdown("""
        <p style='text-align: center; color: #666; font-size: 1.1em; margin-top: 5px;'>
            Mỗi ngày lên lab là một ngày vui 🇻🇳
            <br>
            Sẽ vui hơn nếu chúng ta làm việc chăm chỉ
        </p>
    """, unsafe_allow_html=True)

    if "CẦN TRỢ GIÚP" in df_tk['TrangThai'].values:
        nguoi_can_giup = df_tk[df_tk['TrangThai'] == 'CẦN TRỢ GIÚP']['HoTen'].tolist()
        st.markdown(f"""
        <div style='background-color: #ff4b4b; color: white; padding: 15px; border-radius: 12px; text-align: center; margin-bottom: 20px; box-shadow: 0 4px 15px rgba(255,0,0,0.3); animation: blinker 1s linear infinite;'>
            <h3 style='margin:0; text-transform: uppercase;'>🚨 CẤP CỨU LAB: {', '.join(nguoi_can_giup)} 🚨</h3>
        </div>
        <style>@keyframes blinker {{ 50% {{ opacity: 0.7; }} }}</style>
        """, unsafe_allow_html=True)

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
                        is_my_booking = (mem_name == st.session_state['ho_ten'])
                        is_admin = (my_role == 1)
                        if " - " in ca and (is_my_booking or is_admin):
                            s_str = ca.split(" - ")[0]
                            start_dt = datetime.combine(b_date, parse_time(s_str), tzinfo=VN_TZ)
                            if start_dt > get_now(): 
                                cancel_options.append(f"[{r['Ngày']}] {r['Thiết bị']} | {ca} ({mem_name})")
                except: pass
        
        if not valid_bookings: 
            st.info(f"{mem_name} hiện chưa có lịch.")
        else:
            st.dataframe(pd.DataFrame(valid_bookings)[['Ngày', 'Ca làm việc', 'Thiết bị', 'Mục đích']], use_container_width=True, hide_index=True)
            
            if cancel_options:
                st.markdown("---")
                with st.form("cancel_booking_modal"):
                    st.write("**🗑️ Thao tác Hủy lịch**")
                    selected_cancel = st.selectbox("Chọn lịch:", cancel_options, label_visibility="collapsed")
                    if st.form_submit_button("Xác nhận Hủy", type="primary", use_container_width=True):
                        day = selected_cancel.split("] ")[0].replace("[", "")
                        dev_ca_user = selected_cancel.split("] ")[1]
                        dev = dev_ca_user.split(" | ")[0]
                        ca_user = dev_ca_user.split(" | ")[1]
                        ca = ca_user.split(" (")[0]
                        user_to_cancel = ca_user.split(" (")[1].replace(")", "")
                        
                        records = sheet_lichtuan.get_all_records()
                        row_to_delete = next((i + 2 for i, r in enumerate(records) if str(r['Ngày']) == day and str(r['Thiết bị']) == dev and str(r['Ca làm việc']) == ca and str(r['Người sử dụng']) == user_to_cancel), None)
                        if row_to_delete:
                            sheet_lichtuan.delete_rows(row_to_delete)
                            action_log = f"Hủy lịch của {user_to_cancel} ({ca})" if my_role == 1 and not is_my_booking else f"Hủy lịch ({ca})"
                            sheet_lichsu.append_row([get_now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], action_log, dev, "Hủy qua hệ thống"])
                            load_data.clear(); st.rerun()

    # ================= ĐIỀU HƯỚNG TABS ĐỘNG THEO PHÂN QUYỀN =================
    if my_role <= 2:
        main_tabs = st.tabs(["🏠 Tổng quan Lab", "🔬 Máy móc & Lịch", "🏆 Bảng vinh danh", "📚 Tài liệu & Link"])
        tab_tong_quan = main_tabs[0]
        tab_may_moc = main_tabs[1]
        tab_vinh_danh = main_tabs[2]
        tab_tai_lieu = main_tabs[3]
    else:
        main_tabs = st.tabs(["🔬 Máy móc & Lịch"])
        tab_tong_quan = None
        tab_may_moc = main_tabs[0]
        tab_vinh_danh = None
        tab_tai_lieu = None

    # --- TAB 1: TỔNG QUAN LAB ---
    if tab_tong_quan is not None:
        with tab_tong_quan:
            # 🚀 BLOCK TIỆN ÍCH NỔI BẬT DÀNH CHO TRANG CHỦ
            st.markdown("### 📌 Tiện ích nhanh")
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                st.markdown("""
                    <div style='background: linear-gradient(135deg, #a18cd1 0%, #fbc2eb 100%); padding: 15px; border-radius: 15px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1); display: flex; flex-direction: column; justify-content: center; margin-bottom: 10px;'>
                        <h3 style='margin: 0; color: white; text-shadow: 1px 1px 2px rgba(0,0,0,0.2);'>📢 BẢNG TIN & VOTE</h3>
                    </div>
                """, unsafe_allow_html=True)
                if st.button("Mở Bảng tin", key="btn_notice_main", use_container_width=True): show_notice_board()
                
            with col_b2:
                st.markdown("""
                    <div style='background: linear-gradient(135deg, #84fab0 0%, #8fd3f4 100%); padding: 15px; border-radius: 15px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1); display: flex; flex-direction: column; justify-content: center; margin-bottom: 10px;'>
                        <h3 style='margin: 0; color: white; text-shadow: 1px 1px 2px rgba(0,0,0,0.2);'>💬 CHAT TẬP THỂ</h3>
                    </div>
                """, unsafe_allow_html=True)
                if st.button("Mở Khung Chat", key="btn_chat_main", use_container_width=True): show_chat_popup()
                
            st.markdown("---")

            # KHÔNG GIAN THÀNH VIÊN
            st.markdown("### 🌐 Không gian làm việc")
            st.write("Nhấn vào thẻ thành viên để xem lịch trình cá nhân hoặc Hủy lịch nếu bạn có quyền.")
            
            if "TrangThai" not in df_tk.columns: st.warning("Đang đồng bộ...")
            else:
                cols = st.columns(4) 
                for idx, row in df_tk.iterrows():
                    mem_name = row['HoTen']
                    mem_status = row.get('TrangThai', '⚪ Đã về')
                    if not mem_status: mem_status = "⚪ Đã về"
                    
                    mem_avatar_url = row.get('Avatar', '')
                    if not mem_avatar_url or str(mem_avatar_url).strip() == "":
                        mem_avatar_url = f"https://ui-avatars.com/api/?name={urllib.parse.quote(mem_name)}&background=random&color=fff&size=128&bold=true"
                    
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
                            <div style='position: relative; display: inline-block; margin-bottom: 10px;'>
                                <img src='{mem_avatar_url}' style='width: 70px; height: 70px; border-radius: 50%; border: 3px solid white; object-fit: cover; box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
                                <div style='position: absolute; bottom: 0; right: -5px; font-size: 16px; background: white; border-radius: 50%; padding: 2px; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 4px rgba(0,0,0,0.2);'>{icon}</div>
                            </div>
                            <h5 style='margin: 0px 0 5px 0;'>{mem_name}</h5>
                            <p style='margin: 0; font-size: 12px; font-weight:bold; color: #555;'>{rank_str}</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if st.button("📅 Xem lịch", key=f"btn_pop_{idx}", use_container_width=True):
                            show_member_schedule(mem_name)

    # --- TAB 2: MÁY MÓC & LỊCH TRÌNH ---
    with tab_may_moc:
        sub1, sub2, sub3 = st.tabs(["📝 Đăng ký mượn", "🔄 Trả thiết bị", "🕒 Lịch sử mượn"])
        
        with sub1:
            def format_device_option_main(dev_name):
                if df_tb.empty or dev_name not in df_tb['Tên'].values: return dev_name
                row = df_tb[df_tb['Tên'] == dev_name].iloc[0]
                status, user = row.get('Trạng thái', 'Sẵn sàng'), row.get('Người sử dụng', '')
                note_col = "Ghi chú" if "Ghi chú" in df_tb.columns else None
                note = f" | 📝 {row.get(note_col, '')}" if note_col and row.get(note_col, '') else ""
                if status == 'Sẵn sàng': return f"🟢 {dev_name} (Rảnh){note}"
                else: return f"🔴 {dev_name} (Bận: {user.split()[-1] if user else ''}){note}"

            c_filter, _ = st.columns([1, 1])
            with c_filter:
                view_mode = st.selectbox("Chọn thiết bị:", all_devices if all_devices else ["Chưa có dữ liệu"], format_func=format_device_option_main if all_devices else lambda x: x)
            
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
                
            with st.form("smart_booking_tab_main"):
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
                    with st.form("return_form_tab_main"):
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

    # --- TAB 3: BẢNG VINH DANH ---
    if tab_vinh_danh is not None:
        with tab_vinh_danh:
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

    # --- TAB 4: TÀI LIÊU & LINK ---
    if tab_tai_lieu is not None:
        with tab_tai_lieu:
            st.markdown("### 📚 Kho Tài Liệu & Ứng Dụng chung")
            st.write("Nơi lưu trữ các quy trình vận hành máy (SOP), link phần mềm LabSpec, bài báo nghiên cứu Cu2O, ZnO...")
            
            with st.expander("➕ Thêm Tài liệu / Link mới", expanded=False):
                with st.form("add_doc_form"):
                    doc_name = st.text_input("Tên tài liệu / Ứng dụng (VD: Hướng dẫn LabSpec)")
                    doc_link = st.text_input("Đường dẫn (Link Google Drive, Website...)")
                    if st.form_submit_button("Thêm lên kho", type="primary"):
                        if doc_name.strip() and doc_link.strip():
                            sheet_tailieu.append_row([get_now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], doc_name.strip(), doc_link.strip()])
                            st.success("✅ Đã thêm tài liệu thành công!")
                            load_data.clear(); st.rerun()
                        else:
                            st.error("Vui lòng nhập đủ thông tin.")
                            
            st.markdown("---")
            
            if df_tailieu.empty:
                st.info("Kho tài liệu hiện đang trống.")
            else:
                for _, r in df_tailieu.iloc[::-1].iterrows():
                    st.markdown(f"""
                    <div style='padding: 15px; border-radius: 10px; border: 1px solid #e0e0e0; background: white; margin-bottom: 10px;'>
                        <h5 style='margin: 0;'>🔗 <a href='{r['Link']}' target='_blank' style='text-decoration:none; color: #1a73e8;'>{r['Tên tài liệu']}</a></h5>
                        <p style='color:#777; font-size: 13px; margin: 5px 0 0 0;'>Tải lên bởi: <b>{r['Người đăng']}</b> ({r['Thời gian']})</p>
                    </div>
                    """, unsafe_allow_html=True)
