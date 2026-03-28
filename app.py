import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta, timezone, time as dt_time
import time

# ==========================================
# 1. CẤU HÌNH & KẾT NỐI (BỌC THÉP CHỐNG LỖI 429)
# ==========================================
st.set_page_config(page_title="Hệ thống Lab (Độc lập)", page_icon="📅", layout="wide")

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

    # --- CÂU NÓI KHÍCH LỆ NGHIÊN CỨU ---
    st.markdown("""
    <div style='text-align: center; font-style: italic; color: #4b4b4b; background-color: #f1f8ff; padding: 10px; border-radius: 8px; border-left: 5px solid #0366d6; margin-bottom: 20px;'>
        "Khoa học không chỉ là khám phá thế giới, mà là kiến tạo tương lai. Chúc bạn có một phiên nghiên cứu thành công và thu được những dữ liệu hoàn hảo nhất!" 🔬✨
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    auto_return_devices()
    
    df_tb = load_data("ThietBi")
    df_lich_view = load_data("LichTuan")
    all_devices = df_tb['Tên'].tolist() if not df_tb.empty else []
    
    khung_gio_24h = [f"{i:02d}:00" for i in range(24)]
    today = get_now().date()
    days_7 = [(today + timedelta(days=i)).strftime("%d/%m/%Y") for i in range(7)]

    tab1, tab2, tab3, tab4 = st.tabs(["📊 Trạng thái", "📅 Lịch & Đặt lịch", "🕒 Lịch sử", "🔄 Trả thiết bị"])

    # --- TAB 1: TRẠNG THÁI ---
    with tab1:
        st.subheader("Tình trạng thiết bị hiện tại")
        if not df_tb.empty:
            st.dataframe(df_tb, use_container_width=True, hide_index=True)

    # --- TAB 2: LỊCH CALENDAR & ĐẶT LỊCH ĐỘC LẬP ---
    with tab2:
        st.subheader("📅 Kiểm tra và Đặt lịch thiết bị")
        c_filter, _ = st.columns([1, 2])
        with c_filter:
            view_mode = st.selectbox("🔍 Chọn thiết bị để xem và thao tác:", all_devices if all_devices else ["Chưa có dữ liệu"])
        
        # Thẻ trạng thái
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

        # Ma trận Hiển thị tĩnh
        with st.expander(f"👉 Mở Lịch tuần của [{view_mode}]", expanded=True):
            df_matrix_data = df_lich_view[df_lich_view['Thiết bị'] == view_mode] if not df_lich_view.empty else pd.DataFrame()
            matrix = pd.DataFrame(" ", index=khung_gio_24h, columns=days_7)
            
            if not df_matrix_data.empty:
                for _, r in df_matrix_data.iterrows():
                    ca = str(r['Ca làm việc'])
                    nguoi_dung = str(r['Người sử dụng'])
                    if " - " in ca and str(r['Ngày']) in days_7:
                        try:
                            s_str, e_str = ca.split(" - ")
                            s_time = parse_time(s_str)
                            e_time = parse_time(e_str)
                            
                            for h in range(24):
                                block_start = dt_time(h, 0)
                                block_end = dt_time(h, 59)
                                
                                if s_time <= block_end and block_start <= e_time:
                                    block_text = f"🔷 {s_time.strftime('%H:%M')}-{e_time.strftime('%H:%M')} ({nguoi_dung})"
                                    current_val = matrix.at[f"{h:02d}:00", str(r['Ngày'])]
                                    if "🔷" in current_val:
                                        matrix.at[f"{h:02d}:00", str(r['Ngày'])] += f"\n{block_text}"
                                    else:
                                        matrix.at[f"{h:02d}:00", str(r['Ngày'])] = block_text
                        except: pass

            def style_calendar(val):
                if "🔷" in val: return 'background-color: #e8f0fe; color: #1967d2; font-weight: bold; border-left: 4px solid #1a73e8; white-space: pre-wrap;'
                return 'background-color: white; color: black;'
            
            st.dataframe(
                matrix.style.map(style_calendar),
                use_container_width=True,
                height=450
            )
            
        st.markdown("---")
        
        # FORM ĐẶT LỊCH ĐỘC LẬP THEO THIẾT BỊ
        st.markdown(f"### 📝 Đặt lịch thời gian cho: **{view_mode}**")
        with st.form("smart_booking"):
            st.info("💡 **Mẹo:** Gõ trực tiếp thời gian bằng số (VD: `14:30`, `1430` hoặc `9`).")
            
            c1, c2, c3, c4 = st.columns([1.5, 1, 1, 2])
            with c1: 
                d_pick = st.date_input("🗓️ Chọn ngày", min_value=today)
            with c2: 
                is_now = st.checkbox("Sử dụng BÂY GIỜ", value=True)
                if not is_now:
                    t_start_input = st.text_input("⏳ Từ lúc:", placeholder="VD: 14:30")
                else:
                    t_start_input = get_now().strftime('%H:%M')
                    st.text_input("⏳ Từ lúc (Tự động):", value=t_start_input, disabled=True)
            with c3: 
                t_end_input = st.text_input("⏳ Đến lúc:", placeholder="VD: 16:45", value=(get_now() + timedelta(hours=1)).strftime('%H:%M'))
            with c4: 
                note = st.text_input("Mục đích (VD: Chạy mẫu Cu2O)")
            
            st.markdown("---")
            btn_submit = st.form_submit_button("🔥 Xác nhận Lịch")
            
            if btn_submit:
                t_start = parse_time(t_start_input)
                t_end = parse_time(t_end_input)

                if not t_start:
                    st.error("❌ Lỗi: Thời gian 'Từ lúc' không hợp lệ!")
                    st.stop()
                if not t_end:
                    st.error("❌ Lỗi: Thời gian 'Đến lúc' không hợp lệ!")
                    st.stop()

                d_str = d_pick.strftime("%d/%m/%Y")
                today_str = get_now().strftime("%d/%m/%Y")
                
                if t_end <= t_start:
                    st.error("❌ Lỗi: Giờ kết thúc phải lớn hơn giờ bắt đầu!")
                    st.stop()
                
                if d_str == today_str and t_start < get_now().time() and not is_now:
                    st.error(f"⏳ Lỗi: Không thể đặt giờ trong quá khứ!")
                    st.stop()
                
                df_lich_rt = pd.DataFrame(sheet_lichtuan.get_all_records())
                
                # Rà soát trùng lịch CHỈ DÀNH CHO THIẾT BỊ ĐANG CHỌN (view_mode)
                conflict_found = []
                if not df_lich_rt.empty:
                    df_day_device = df_lich_rt[(df_lich_rt['Ngày'] == d_str) & (df_lich_rt['Thiết bị'] == view_mode)]
                    for _, row in df_day_device.iterrows():
                        try:
                            exist_start = parse_time(row['Ca làm việc'].split(" - ")[0])
                            exist_end = parse_time(row['Ca làm việc'].split(" - ")[1])
                            
                            # Kiểm tra giao cắt thời gian
                            if t_start < exist_end and exist_start < t_end:
                                conflict_found.append(f"lúc {row['Ca làm việc']} (bởi {row['Người sử dụng']})")
                        except: pass

                if conflict_found: 
                    st.error(f"❌ Rất tiếc, {view_mode} đã bị kẹt lịch:\n" + "\n".join([f"- {c}" for c in conflict_found]))
                else:
                    ca_lam_viec_str = f"{t_start.strftime('%H:%M')} - {t_end.strftime('%H:%M')}"
                    
                    # Ghi nhận vào ma trận lịch
                    sheet_lichtuan.append_row([d_str, ca_lam_viec_str, st.session_state['ho_ten'], view_mode, note])
                    
                    # Nếu là mượn ngay bây giờ, cập nhật trạng thái thiết bị
                    if is_now and d_str == today_str:
                        cell = sheet_thietbi.find(view_mode)
                        sheet_thietbi.update_cell(cell.row, 3, "Đang mượn")
                        sheet_thietbi.update_cell(cell.row, 4, st.session_state['ho_ten'])
                        sheet_lichsu.append_row([get_now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], f"Mượn trực tiếp ({ca_lam_viec_str})", view_mode])
                        st.success(f"✅ Đã ghi nhận mượn {view_mode}. Lịch sẽ tự động thu hồi lúc {t_end.strftime('%H:%M')}.")
                    else:
                        sheet_lichsu.append_row([get_now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], f"Đặt lịch ({d_str} {ca_lam_viec_str})", view_mode])
                        st.success(f"✅ Đã chốt lịch cho {view_mode} thành công lên Calendar!")
                        
                    load_data.clear() 
                    st.rerun()

    # --- TAB 3 & 4 ---
    with tab3:
        st.subheader("Lịch sử hoạt động")
        df_h = load_data("LichSu")
        if not df_h.empty: st.dataframe(df_h.iloc[::-1], use_container_width=True, hide_index=True)

    with tab4:
        st.subheader("🔄 Hoàn trả thủ công từng thiết bị")
        if "Người sử dụng" in df_tb.columns:
            my_list = df_tb[df_tb["Người sử dụng"] == st.session_state['ho_ten']]['Tên'].tolist()
            if not my_list: 
                st.success("Bạn hiện không giữ thiết bị nào.")
            else:
                with st.form("return_form"):
                    st.info("💡 Bạn đang xem và thao tác độc lập với từng thiết bị.")
                    dev_ret = st.selectbox("Chọn 1 thiết bị đang giữ để trả:", my_list)
                    return_note = st.text_input("Ghi chú sau khi dùng (VD: Máy hoạt động tốt, đã vệ sinh...)")
                    
                    if st.form_submit_button("Xác nhận Trả"):
                        cell = sheet_thietbi.find(dev_ret)
                        sheet_thietbi.update_cell(cell.row, 3, "Sẵn sàng")
                        sheet_thietbi.update_cell(cell.row, 4, "")
                        
                        action_str = f"Hoàn trả (Ghi chú: {return_note})" if return_note else "Hoàn trả"
                        sheet_lichsu.append_row([get_now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], action_str, dev_ret])
                        
                        st.success(f"✅ Đã trả thành công {dev_ret}.")
                        load_data.clear() 
                        st.rerun()
