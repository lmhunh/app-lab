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
    
    # --- TỰ ĐỘNG TẠO CỘT 'TrangThai' NẾU CHƯA CÓ TRONG SHEETS ---
    if not df_tk.empty and "TrangThai" not in df_tk.columns:
        num_cols = len(df_tk.columns)
        sheet_taikhoan.update_cell(1, num_cols + 1, "TrangThai")
        load_data.clear()
        df_tk = load_data("TaiKhoan")
        
    # ---------------- SIDEBAR (Menu bên trái) ----------------
    with st.sidebar:
        st.markdown(f"### 👤 {st.session_state['ho_ten']}")
        st.markdown("---")
        
        # Hàm cập nhật trạng thái nhanh
        def update_status(new_status):
            cell = sheet_taikhoan.find(str(st.session_state['tai_khoan']))
            col_idx = df_tk.columns.get_loc("TrangThai") + 1
            sheet_taikhoan.update_cell(cell.row, col_idx, new_status)
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
                if st.button("🟢 Lab", use_container_width=True, help="Tôi đang ở Lab"): update_status("🟢 Ở Lab")
            with c2:
                if st.button("🟡 Bận", use_container_width=True, help="Tôi đang bận tay"): update_status("🟡 Đang bận")
            with c3:
                if st.button("⚪ Về", use_container_width=True, help="Tôi đã về"): update_status("⚪ Đã về")
                
            st.markdown(f"Đang hiển thị: **{current_my_status}**")
            
            st.markdown("---")
            if st.button("🆘 NÚT KHẨN CẤP", use_container_width=True, type="primary"):
                update_status("CẦN TRỢ GIÚP")
            
        st.markdown("---")
        if st.button("🚪 Đăng xuất", use_container_width=True):
            st.session_state['logged_in'] = False
            st.rerun()

    # ---------------- NỘI DUNG CHÍNH ----------------
    st.title("📅 Hệ thống Quản lý Thiết bị Lab")
    
    if "CẦN TRỢ GIÚP" in df_tk['TrangThai'].values:
        nguoi_can_giup = df_tk[df_tk['TrangThai'] == 'CẦN TRỢ GIÚP']['HoTen'].tolist()
        st.markdown(f"""
        <div style='background-color: #ff0000; color: yellow; padding: 15px; border-radius: 8px; border: 3px solid yellow; text-align: center; margin-bottom: 20px; animation: blinker 1s linear infinite;'>
            <h2 style='margin:0; color: white;'>🚨 CẢNH BÁO KHẨN CẤP TỪ: {', '.join(nguoi_can_giup)} 🚨</h2>
            <p style='margin:0; font-size: 1.2rem; color: white;'>Vui lòng kiểm tra phòng Lab ngay lập tức!</p>
        </div>
        <style>@keyframes blinker {{ 50% {{ opacity: 0.5; }} }}</style>
        """, unsafe_allow_html=True)

    auto_return_devices()
    
    df_tb = load_data("ThietBi")
    df_lich_view = load_data("LichTuan")
    all_devices = df_tb['Tên'].tolist() if not df_tb.empty else []
    
    today = get_now().date()
    days_7 = [(today + timedelta(days=i)).strftime("%d/%m/%Y") for i in range(7)]
    time_options = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 15, 30, 45)]

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Trạng thái & Đăng ký", "👥 Thành viên Lab", "📋 Lịch của tôi", "🕒 Lịch sử", "🔄 Trả thiết bị"])

    # ================= TAB 1: BẢNG TRẠNG THÁI VÀ ĐĂNG KÝ =================
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
            df_dev = df_lich_view[df_lich_view['Thiết bị'] == view_mode] if not df_lich_view.empty else pd.DataFrame()
            if not df_dev.empty:
                df_dev = df_dev.drop_duplicates(subset=['Ngày', 'Ca làm việc', 'Thiết bị'])
            
            html_timeline = "<div style='width: 100%; font-family: sans-serif; overflow-x: auto; padding-bottom: 10px;'><div style='display: flex; align-items: flex-end; width: 100%; min-width: 700px; margin-bottom: 5px; font-size: 11px; color: #666; font-weight: bold;'><div style='width: 70px;'></div><div style='flex-grow: 1; position: relative; height: 20px; border-bottom: 2px solid #aaa;'>"
            for h in range(0, 25, 2):
                left_pct = (h / 24.0) * 100
                html_timeline += f"<div style='position: absolute; left: {left_pct}%; transform: translateX(-50%); bottom: 2px;'>{h:02d}:00</div><div style='position: absolute; left: {left_pct}%; width: 2px; height: 6px; background-color: #aaa; bottom: -2px; transform: translateX(-50%);'></div>"
            html_timeline += "</div></div>"
            
            for d in days_7:
                html_timeline += f"<div style='display: flex; align-items: center; margin-bottom: 10px; min-width: 700px;'><div style='width: 70px; font-size: 13px; font-weight: bold; color: #444;'>{d[:5]}</div><div style='flex-grow: 1; position: relative; height: 36px; background-color: #e9ecef; border-radius: 4px; border: 1px solid #ddd;'>"
                for h in range(2, 24, 2):
                    html_timeline += f"<div style='position: absolute; left: {(h/24)*100}%; width: 1px; height: 100%; background-color: #cfd4da; z-index: 1;'></div>"
                
                df_day = df_dev[df_dev['Ngày'] == d]
                if not df_day.empty:
                    for _, r in df_day.iterrows():
                        ca = str(r['Ca làm việc'])
                        if " - " in ca:
                            try:
                                s_str, e_str = ca.split(" - ")
                                s_time = parse_time(s_str)
                                e_time = parse_time(e_str)
                                start_min = s_time.hour * 60 + s_time.minute
                                end_min = e_time.hour * 60 + e_time.minute
                                if end_min <= start_min: end_min = 24 * 60
                                
                                left_pct = (start_min / (24 * 60)) * 100
                                width_pct = ((end_min - start_min) / (24 * 60)) * 100
                                user = r['Người sử dụng']
                                is_me = user == st.session_state.get('ho_ten', '')
                                color = "#1a73e8" if is_me else "#ea4335" 
                                display_text = f"{s_str}-{e_str} ({user})"
                                
                                block_html = f"<div style='position: absolute; left: {left_pct}%; width: {width_pct}%; height: 100%; background-color: {color}; border-radius: 4px; color: white; font-size: 11px; display: flex; align-items: center; justify-content: center; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; box-shadow: 0 1px 3px rgba(0,0,0,0.3); z-index: 2;'><span style='padding: 0 4px;'>{display_text}</span></div>"
                                html_timeline += block_html
                            except: pass
                html_timeline += "</div></div>"
            html_timeline += "</div>"
            st.markdown(html_timeline, unsafe_allow_html=True)
            
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
            
            btn_submit = st.form_submit_button("🔥 Xác nhận")
            
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

    # ================= TAB 2: THÀNH VIÊN LAB =================
    with tab2:
        st.subheader("👥 Trạng thái Thành viên Lab")
        st.info("💡 Bảng theo dõi tình trạng an toàn và tiến độ làm việc của mọi người trong Lab.")
        
        cols = st.columns(4) 
        for idx, row in df_tk.iterrows():
            mem_name = row['HoTen']
            mem_status = row.get('TrangThai', '⚪ Đã về')
            if not mem_status: mem_status = "⚪ Đã về"
            
            with cols[idx % 4]:
                if mem_status == "CẦN TRỢ GIÚP":
                    st.markdown(f"""
                    <div style='background-color: #ff4b4b; color: white; padding: 20px; border-radius: 10px; text-align: center; margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border: 2px solid darkred;'>
                        <h1 style='margin: 0; font-size: 30px;'>🚨</h1>
                        <h4 style='margin: 10px 0 5px 0; color: white;'>{mem_name}</h4>
                        <p style='margin: 0; font-weight: bold;'>ĐANG GẶP NGUY HIỂM!</p>
                    </div>
                    """, unsafe_allow_html=True)
                elif "Ở Lab" in mem_status:
                    st.markdown(f"""
                    <div style='background-color: #d4edda; color: #155724; padding: 20px; border-radius: 10px; text-align: center; margin-bottom: 15px; border: 1px solid #c3e6cb;'>
                        <h1 style='margin: 0; font-size: 30px;'>🟢</h1>
                        <h4 style='margin: 10px 0 5px 0;'>{mem_name}</h4>
                        <p style='margin: 0;'>{mem_status}</p>
                    </div>
                    """, unsafe_allow_html=True)
                elif "Đang bận" in mem_status:
                    st.markdown(f"""
                    <div style='background-color: #fff3cd; color: #856404; padding: 20px; border-radius: 10px; text-align: center; margin-bottom: 15px; border: 1px solid #ffeeba;'>
                        <h1 style='margin: 0; font-size: 30px;'>🟡</h1>
                        <h4 style='margin: 10px 0 5px 0;'>{mem_name}</h4>
                        <p style='margin: 0;'>{mem_status}</p>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style='background-color: #f8f9fa; color: #6c757d; padding: 20px; border-radius: 10px; text-align: center; margin-bottom: 15px; border: 1px solid #dee2e6;'>
                        <h1 style='margin: 0; font-size: 30px;'>⚪</h1>
                        <h4 style='margin: 10px 0 5px 0;'>{mem_name}</h4>
                        <p style='margin: 0;'>{mem_status}</p>
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
