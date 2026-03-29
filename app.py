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
                    latest_end_dt = None
                    for _, b_row in user_bookings.iterrows():
                        try:
                            b_date = datetime.strptime(str(b_row['Ngày']), "%d/%m/%Y").date()
                            ca = str(b_row['Ca làm việc'])
                            if " - " in ca:
                                _, e_str = ca.split(" - ")
                                e_time = parse_time(e_str)
                                end_dt = datetime.combine(b_date, e_time, tzinfo=VN_TZ)
                                if latest_end_dt is None or end_dt > latest_end_dt:
                                    latest_end_dt = end_dt
                        except: pass
                    
                    if latest_end_dt and now >= latest_end_dt:
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
# 3. LOGIC ĐĂNG NHẬP CÓ LƯU MÃ TÀI KHOẢN
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
    # Lấy dữ liệu tài khoản để kiểm tra Trạng thái Khẩn cấp
    df_tk = load_data("TaiKhoan")
    
    # ---------------- SIDEBAR (Menu bên trái) ----------------
    with st.sidebar:
        st.markdown(f"### 👤 {st.session_state['ho_ten']}")
        st.markdown("---")
        
        # NÚT KHẨN CẤP
        if "TrangThai" in df_tk.columns:
            my_status = df_tk[df_tk['TaiKhoan'].astype(str) == str(st.session_state['tai_khoan'])]['TrangThai'].values
            current_my_status = my_status[0] if len(my_status) > 0 else "Bình thường"
            
            if current_my_status != "CẦN TRỢ GIÚP":
                st.info("🟢 Trạng thái: An toàn")
                if st.button("🆘 NÚT KHẨN CẤP", use_container_width=True, type="primary"):
                    cell = sheet_taikhoan.find(str(st.session_state['tai_khoan']))
                    col_idx = df_tk.columns.get_loc("TrangThai") + 1
                    sheet_taikhoan.update_cell(cell.row, col_idx, "CẦN TRỢ GIÚP")
                    load_data.clear()
                    st.rerun()
            else:
                st.markdown("<div style='background-color: #ff4b4b; color: white; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold; margin-bottom: 10px; box-shadow: 0 0 10px #ff4b4b;'>🚨 BẠN ĐANG PHÁT TÍN HIỆU CẤP CỨU!</div>", unsafe_allow_html=True)
                if st.button("✅ Đã an toàn (Hủy báo động)", use_container_width=True):
                    cell = sheet_taikhoan.find(str(st.session_state['tai_khoan']))
                    col_idx = df_tk.columns.get_loc("TrangThai") + 1
                    sheet_taikhoan.update_cell(cell.row, col_idx, "Bình thường")
                    load_data.clear()
                    st.rerun()
        else:
            st.warning("⚠️ Admin hãy thêm cột 'TrangThai' vào sheet TaiKhoan để dùng tính năng Khẩn Cấp.")
            
        st.markdown("---")
        if st.button("🚪 Đăng xuất", use_container_width=True):
            st.session_state['logged_in'] = False
            st.rerun()

    # ---------------- NỘI DUNG CHÍNH ----------------
    st.title("📅 Hệ thống Quản lý Thiết bị Lab")
    
    # Hiệu ứng nhấp nháy báo động TOÀN HỆ THỐNG nếu có ai đó ấn nút 🆘
    if "TrangThai" in df_tk.columns and "CẦN TRỢ GIÚP" in df_tk['TrangThai'].values:
        nguoi_can_giup = df_tk[df_tk['TrangThai'] == 'CẦN TRỢ GIÚP']['HoTen'].tolist()
        st.markdown(f"""
        <div style='background-color: #ff0000; color: yellow; padding: 15px; border-radius: 8px; border: 3px solid yellow; text-align: center; margin-bottom: 20px; animation: blinker 1s linear infinite;'>
            <h2 style='margin:0; color: white;'>🚨 CẢNH BÁO KHẨN CẤP TỪ: {', '.join(nguoi_can_giup)} 🚨</h2>
            <p style='margin:0; font-size: 1.2rem; color: white;'>Vui lòng kiểm tra phòng Lab ngay lập tức!</p>
        </div>
        <style>
            @keyframes blinker {{ 50% {{ opacity: 0.5; }} }}
        </style>
        """, unsafe_allow_html=True)

    auto_return_devices()
    
    df_tb = load_data("ThietBi")
    df_lich_view = load_data("LichTuan")
    all_devices = df_tb['Tên'].tolist() if not df_tb.empty else []
    
    today = get_now().date()
    days_7 = [(today + timedelta(days=i)).strftime("%d/%m/%Y") for i in range(7)]
    time_options = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 15, 30, 45)]

    # CẤU TRÚC TAB MỚI (Đã gộp Tab 1 & 2)
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Trạng thái & Đăng ký", "👥 Thành viên Lab", "📋 Lịch của tôi", "🕒 Lịch sử", "🔄 Trả thiết bị"])

    # ================= TAB 1: GỘP BẢNG TRẠNG THÁI VÀ ĐĂNG KÝ =================
    with tab1:
        st.subheader("1. Tình trạng thiết bị hiện tại")
        if not df_tb.empty:
            def highlight_status(row):
                if row['Trạng thái'] == 'Đang mượn': return ['background-color: #fdecea; color: #000000; font-weight: bold;'] * len(row)
                return [''] * len(row)
            st.dataframe(df_tb.style.apply(highlight_status, axis=1), use_container_width=True, hide_index=True)
            
        st.markdown("---")
        
        st.subheader("2. Đăng ký & Biểu đồ Timeline")
        c_filter, _ = st.columns([1, 2])
        with c_filter:
            view_mode = st.selectbox("🔍 Chọn thiết bị để thao tác:", all_devices if all_devices else ["Chưa có dữ liệu"])
        
        if not df_tb.empty and view_mode in df_tb['Tên'].values:
            current_status = df_tb[df_tb['Tên'] == view_mode].iloc[0]['Trạng thái']
            current_user = df_tb[df_tb['Tên'] == view_mode].iloc[0].get('Người sử dụng', '')
            note_col_name = "Ghi chú" if "Ghi chú" in df_tb.columns else None
            current_note = df_tb[df_tb['Tên'] == view_mode].iloc[0].get(note_col_name, '') if note_col_name else ''
            note_display = f"<br><span style='color: #666; font-size: 0.95em;'>📝 Ghi chú: <i>{current_note}</i></span>" if current_note else ""

            if current_status == 'Sẵn sàng':
                st.markdown(f"<div style='padding: 10px; border-radius: 8px; background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb;'><h5 style='margin: 0;'>🟢 <b>{view_mode}</b> đang SẴN SÀNG!{note_display}</h5></div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='padding: 10px; border-radius: 8px; background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb;'><h5 style='margin: 0;'>🔴 <b>{view_mode}</b> đang BẬN (Bởi: <b>{current_user}</b>).{note_display}</h5></div>", unsafe_allow_html=True)

        st.write("") 

        with st.expander(f"👉 Mở Biểu đồ sử dụng của [{view_mode}]", expanded=True):
            zoom_level = st.slider("🔍 Zoom trục thời gian", min_value=30, max_value=150, value=60, label_visibility="collapsed")
            df_dev = df_lich_view[df_lich_view['Thiết bị'] == view_mode] if not df_lich_view.empty else pd.DataFrame()
            if not df_dev.empty:
                df_dev = df_dev.drop_duplicates(subset=['Ngày', 'Ca làm việc', 'Thiết bị'])
            
            total_h = 24 * zoom_level
            header_h = 40
            html_timeline = f"<div style='width: 100%; max-height: 450px; overflow-y: auto; overflow-x: auto; border: 1px solid #ddd; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); background: white;'><div style='display: flex; min-width: 800px; height: {total_h + header_h + 20}px; position: relative;'><div style='width: 60px; flex-shrink: 0; border-right: 1px solid #ccc; position: sticky; left: 0; background: white; z-index: 10;'><div style='height: {header_h}px; border-bottom: 1px solid #ccc; background: #f8f9fa; position: sticky; top: 0; z-index: 11;'></div>"
            for h in range(25):
                top_pos = header_h + h * zoom_level
                html_timeline += f"<div style='position: absolute; top: {top_pos}px; right: 8px; transform: translateY(-50%); font-size: 11px; color: #555; font-weight: bold;'>{h:02d}:00</div>"
            html_timeline += "</div>"
            
            for d in days_7:
                html_timeline += f"<div style='flex: 1; min-width: 100px; position: relative; border-right: 1px solid #eee;'>"
                is_today = (d == get_now().strftime("%d/%m/%Y"))
                bg_header = "#e8f0fe" if is_today else "#f8f9fa"
                color_header = "#1a73e8" if is_today else "#333"
                html_timeline += f"<div style='height: {header_h}px; display: flex; align-items: center; justify-content: center; background: {bg_header}; border-bottom: 1px solid #ccc; font-weight: bold; font-size: 13px; color: {color_header}; position: sticky; top: 0; z-index: 5;'>{d[:5]}</div>"
                
                for h in range(1, 24):
                    top_pos = header_h + h * zoom_level
                    html_timeline += f"<div style='position: absolute; top: {top_pos}px; left: 0; width: 100%; height: 1px; background: #e9ecef; z-index: 1;'></div>"
                
                if is_today:
                    now_h = get_now().hour + get_now().minute / 60.0
                    now_top = header_h + now_h * zoom_level
                    html_timeline += f"<div style='position: absolute; top: {now_top}px; left: 0; width: 100%; height: 2px; background: #ea4335; z-index: 3;'></div>"
                
                df_day = df_dev[df_dev['Ngày'] == d]
                if not df_day.empty:
                    for _, r in df_day.iterrows():
                        ca = str(r['Ca làm việc'])
                        if " - " in ca:
                            try:
                                s_str, e_str = ca.split(" - ")
                                s_time = parse_time(s_str)
                                e_time = parse_time(e_str)
                                start_float = s_time.hour + s_time.minute / 60.0
                                end_float = e_time.hour + e_time.minute / 60.0
                                if end_float <= start_float: end_float = 24.0
                                top_px = header_h + start_float * zoom_level
                                height_px = (end_float - start_float) * zoom_level
                                user = r['Người sử dụng']
                                is_me = user == st.session_state.get('ho_ten', '')
                                color = "#1a73e8" if is_me else "#9e9e9e" 
                                tooltip = f"⌚ {s_str} - {e_str} | 👤 {user} | 📝 {r.get('Mục đích', '')}"
                                display_text = f"<span style='font-weight:bold;'>{user}</span><br>{s_str}-{e_str}" if height_px > 30 else (f"{user}" if height_px > 15 else "")
                                block_html = f"<div title='{tooltip}' style='position: absolute; top: {top_px}px; left: 4px; right: 4px; height: {height_px}px; background-color: {color}; border-radius: 4px; color: white; font-size: 11px; padding: 2px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.2); z-index: 2; text-align: center; line-height: 1.2; display: flex; flex-direction: column; justify-content: center; opacity: 0.9;'>{display_text}</div>"
                                html_timeline += block_html
                            except: pass
                html_timeline += "</div>"
            html_timeline += "</div></div>"
            st.markdown(html_timeline, unsafe_allow_html=True)
            st.markdown("<div style='margin-top: 5px; font-size: 13px;'>🟦 <b>Bạn</b> &nbsp;&nbsp;&nbsp; ⬜ <b>Người khác</b> &nbsp;&nbsp;&nbsp; 🟥 <b>Giờ hiện tại</b></div>", unsafe_allow_html=True)
            
        with st.form("smart_booking"):
            c1, c2, c3, c4 = st.columns([1.5, 1, 1, 2])
            with c1: d_pick = st.date_input("🗓️ Chọn ngày", min_value=today)
            with c2: 
                now_minute = get_now().minute
                default_idx = get_now().hour * 4 + ((now_minute // 15) * 15 // 15)
                t_start_str = st.selectbox("⏳ Từ lúc:", time_options, index=default_idx)
            with c3: 
                t_end_str = st.selectbox("⏳ Đến lúc:", time_options, index=min(default_idx + 4, 95)) 
            with c4: 
                note = st.text_input("Mục đích (VD: Đo phổ ZnO)")
            
            btn_submit = st.form_submit_button("🔥 Xác nhận Đăng ký", use_container_width=True)
            
            if btn_submit:
                t_start = parse_time(t_start_str)
                t_end = parse_time(t_end_str)
                d_str = d_pick.strftime("%d/%m/%Y")
                today_str = get_now().strftime("%d/%m/%Y")
                current_t = get_now().time()
                
                if t_end <= t_start: st.error("❌ Lỗi: Giờ kết thúc phải lớn hơn giờ bắt đầu!"); st.stop()
                if d_str == today_str and t_end <= current_t: st.error(f"⏳ Lỗi: Khoảng thời gian này đã qua!"); st.stop()
                
                df_lich_rt = pd.DataFrame(sheet_lichtuan.get_all_records())
                conflict_found = []
                if not df_lich_rt.empty:
                    df_day_device = df_lich_rt[(df_lich_rt['Ngày'] == d_str) & (df_lich_rt['Thiết bị'] == view_mode)]
                    for _, row in df_day_device.iterrows():
                        try:
                            exist_start = parse_time(row['Ca làm việc'].split(" - ")[0])
                            exist_end = parse_time(row['Ca làm việc'].split(" - ")[1])
                            if t_start < exist_end and exist_start < t_end:
                                if row['Người sử dụng'] != st.session_state['ho_ten']:
                                    conflict_found.append(f"{row['Ca làm việc']} (bởi {row['Người sử dụng']})")
                        except: pass

                if conflict_found: 
                    st.error(f"❌ Rất tiếc, {view_mode} đã bị kẹt lịch:\n" + "\n".join([f"- {c}" for c in conflict_found]))
                else:
                    ca_lam_viec_str = f"{t_start_str} - {t_end_str}"
                    sheet_lichtuan.append_row([d_str, ca_lam_viec_str, st.session_state['ho_ten'], view_mode, note])
                    is_active_now = (d_str == today_str) and (t_start <= current_t <= t_end)
                    if is_active_now:
                        cell = sheet_thietbi.find(view_mode)
                        sheet_thietbi.update_cell(cell.row, 3, "Đang mượn")
                        sheet_thietbi.update_cell(cell.row, 4, st.session_state['ho_ten'])
                        sheet_lichsu.append_row([get_now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], f"Sử dụng trực tiếp ({ca_lam_viec_str})", view_mode, note])
                        st.success(f"✅ Đã kích hoạt mượn ngay {view_mode}.")
                    else:
                        sheet_lichsu.append_row([get_now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], f"Đặt lịch ({ca_lam_viec_str})", view_mode, note])
                        st.success(f"✅ Đã chốt lịch sử dụng {view_mode} thành công!")
                    load_data.clear(); st.rerun()

    # ================= TAB 2: THÀNH VIÊN LAB (MỚI) =================
    with tab2:
        st.subheader("👥 Trạng thái Thành viên Lab")
        st.info("💡 Bảng theo dõi tình trạng an toàn của mọi người trong Lab.")
        
        if "TrangThai" not in df_tk.columns:
            st.warning("Vui lòng truy cập file Google Sheets, thêm cột 'TrangThai' vào trang tính 'TaiKhoan' để tính năng này hoạt động.")
        else:
            cols = st.columns(4) # Chia lưới 4 cột
            for idx, row in df_tk.iterrows():
                mem_name = row['HoTen']
                mem_status = row.get('TrangThai', 'Bình thường')
                if not mem_status: mem_status = "Bình thường"
                
                with cols[idx % 4]:
                    if mem_status == "CẦN TRỢ GIÚP":
                        st.markdown(f"""
                        <div style='background-color: #ff4b4b; color: white; padding: 20px; border-radius: 10px; text-align: center; margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border: 2px solid darkred;'>
                            <h1 style='margin: 0; font-size: 30px;'>🚨</h1>
                            <h4 style='margin: 10px 0 5px 0; color: white;'>{mem_name}</h4>
                            <p style='margin: 0; font-weight: bold;'>ĐANG GẶP NGUY HIỂM!</p>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <div style='background-color: #f8f9fa; color: #333; padding: 20px; border-radius: 10px; text-align: center; margin-bottom: 15px; border: 1px solid #ddd;'>
                            <h1 style='margin: 0; font-size: 30px;'>🟢</h1>
                            <h4 style='margin: 10px 0 5px 0; color: #333;'>{mem_name}</h4>
                            <p style='margin: 0; color: #666;'>Bình thường</p>
                        </div>
                        """, unsafe_allow_html=True)

    # --- TAB 3: LỊCH CỦA TÔI ---
    with tab3:
        st.subheader("📋 Các lịch bạn đã đăng ký (Từ hôm nay)")
        my_raw_bookings = df_lich_view[df_lich_view['Người sử dụng'] == st.session_state['ho_ten']]
        valid_bookings, cancel_options = [], []
        if not my_raw_bookings.empty:
            for _, r in my_raw_bookings.iterrows():
                try:
                    b_date = datetime.strptime(str(r['Ngày']), "%d/%m/%Y").date()
                    if b_date >= today:
                        valid_bookings.append(r)
                        ca = str(r['Ca làm việc'])
                        if " - " in ca:
                            s_str = ca.split(" - ")[0]
                            start_dt = datetime.combine(b_date, parse_time(s_str), tzinfo=VN_TZ)
                            if start_dt > get_now(): cancel_options.append(f"[{r['Ngày']}] {r['Thiết bị']} | {ca}")
                except: pass
        
        if not valid_bookings: st.success("Bạn hiện chưa đăng ký thiết bị nào.")
        else:
            st.dataframe(pd.DataFrame(valid_bookings)[['Ngày', 'Ca làm việc', 'Thiết bị', 'Mục đích']], use_container_width=True, hide_index=True)
            st.markdown("---")
            if cancel_options:
                with st.form("cancel_booking"):
                    selected_cancel = st.selectbox("🗑️ Chọn lịch muốn hủy:", cancel_options)
                    if st.form_submit_button("Xác nhận Hủy lịch"):
                        day = selected_cancel.split("] ")[0].replace("[", "")
                        dev, ca = selected_cancel.split("] ")[1].split(" | ")
                        records = sheet_lichtuan.get_all_records()
                        row_to_delete = next((i + 2 for i, r in enumerate(records) if str(r['Ngày']) == day and str(r['Thiết bị']) == dev and str(r['Ca làm việc']) == ca and str(r['Người sử dụng']) == st.session_state['ho_ten']), None)
                        if row_to_delete:
                            sheet_lichtuan.delete_rows(row_to_delete)
                            sheet_lichsu.append_row([get_now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], f"Hủy lịch ({ca})", dev, "Tự hủy"])
                            st.success(f"✅ Đã hủy lịch {dev}."); load_data.clear(); st.rerun()

    # --- TAB 4: LỊCH SỬ ---
    with tab4:
        st.subheader("Lịch sử hoạt động")
        df_h = load_data("LichSu")
        if not df_h.empty: st.dataframe(df_h.iloc[::-1], use_container_width=True, hide_index=True)

    # --- TAB 5: TRẢ THIẾT BỊ ---
    with tab5:
        st.subheader("🔄 Hoàn trả & Ghi chú tình trạng thiết bị")
        if "Người sử dụng" in df_tb.columns:
            my_list = df_tb[df_tb["Người sử dụng"] == st.session_state['ho_ten']]['Tên'].tolist()
            if not my_list: st.success("Bạn hiện không giữ thiết bị nào.")
            else:
                with st.form("return_form"):
                    dev_ret = st.selectbox("Chọn thiết bị đang giữ để trả:", my_list)
                    return_note = st.text_input("📝 Ghi chú tình trạng (VD: Lò nung gia nhiệt ổn định...)")
                    if st.form_submit_button("Xác nhận Trả"):
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
                        
                        sheet_lichsu.append_row([get_now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], "Trả sớm & Giải phóng lịch", dev_ret, return_note])
                        st.success(f"✅ Đã trả {dev_ret}."); load_data.clear(); st.rerun()
