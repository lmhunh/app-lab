import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta, timezone
import time

# ==========================================
# 1. CẤU HÌNH & KẾT NỐI (GMT+7)
# ==========================================
st.set_page_config(page_title="Hệ thống Lab (Unified Flow)", page_icon="⏱️", layout="wide")

VN_TZ = timezone(timedelta(hours=7))

def get_now():
    return datetime.now(VN_TZ)

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

@st.cache_data(ttl=15, show_spinner=False)
def load_data(sheet_name):
    try:
        sheet = sh.worksheet(sheet_name)
        return pd.DataFrame(sheet.get_all_records())
    except gspread.exceptions.APIError:
        time.sleep(2)
        sheet = sh.worksheet(sheet_name)
        return pd.DataFrame(sheet.get_all_records())

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
        current_hour = now.hour
        
        df_today = df_lich[df_lich['Ngày'] == today_str]
        if df_today.empty: return
        has_changes = False

        for _, row in df_tb.iterrows():
            if row.get('Trạng thái') == 'Đang mượn':
                device = row.get('Tên')
                user = row.get('Người sử dụng', '')
                user_bookings = df_today[(df_today['Thiết bị'] == device) & (df_today['Người sử dụng'] == user)]
                
                if not user_bookings.empty:
                    booked_hours = [int(ca.split(":")[0]) for ca in user_bookings['Ca làm việc'] if ":" in str(ca)]
                    if booked_hours and current_hour >= (max(booked_hours) + 1):
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
    col_t.title("⏱️ Quản lý Thiết bị Lab")
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

    tab1, tab2, tab3, tab4 = st.tabs(["📊 Trạng thái", "🔍 Kiểm tra & Đặt lịch", "🕒 Lịch sử", "🔄 Trả thiết bị"])

    # --- TAB 1: TRẠNG THÁI ---
    with tab1:
        st.subheader("Tình trạng thiết bị hiện tại")
        if not df_tb.empty:
            st.dataframe(df_tb, use_container_width=True, hide_index=True)

    # --- TAB 2: KIỂM TRA TRẠNG THÁI & ĐẶT LỊCH ---
    with tab2:
        st.subheader("🔍 Kiểm tra trạng thái thiết bị")
        
        c_filter, _ = st.columns([1, 2])
        with c_filter:
            view_mode = st.selectbox("Chọn thiết bị:", all_devices if all_devices else ["Chưa có dữ liệu"])
        
        # 1. HIỂN THỊ THẺ TRẠNG THÁI NHỎ
        if not df_tb.empty and view_mode in df_tb['Tên'].values:
            current_status = df_tb[df_tb['Tên'] == view_mode].iloc[0]['Trạng thái']
            current_user = df_tb[df_tb['Tên'] == view_mode].iloc[0].get('Người sử dụng', '')
            
            if current_status == 'Sẵn sàng':
                st.markdown(f"""
                <div style='padding: 20px; border-radius: 10px; background-color: #d4edda; color: #155724; display: flex; align-items: center; border: 1px solid #c3e6cb;'>
                    <h1 style='margin: 0; padding-right: 20px; font-size: 3rem;'>🟢</h1>
                    <div>
                        <h3 style='margin: 0;'>{view_mode} đang SẴN SÀNG!</h3>
                        <p style='margin: 0; font-size: 1.1rem;'>Thiết bị hiện đang trống. Bạn có thể mở form bên dưới để sử dụng ngay.</p>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style='padding: 20px; border-radius: 10px; background-color: #f8d7da; color: #721c24; display: flex; align-items: center; border: 1px solid #f5c6cb;'>
                    <h1 style='margin: 0; padding-right: 20px; font-size: 3rem;'>🔴</h1>
                    <div>
                        <h3 style='margin: 0;'>{view_mode} đang BẬN!</h3>
                        <p style='margin: 0; font-size: 1.1rem;'>Hiện đang được sử dụng bởi: <b>{current_user}</b></p>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        st.write("") 

        # 2. MA TRẬN LỊCH ẨN
        with st.expander("📅 Bấm vào đây để mở Ma trận lịch (Kiểm tra giờ rảnh của máy này)", expanded=False):
            df_matrix_data = df_lich_view[df_lich_view['Thiết bị'] == view_mode] if not df_lich_view.empty else pd.DataFrame()

            matrix = pd.DataFrame("🟢 Trống", index=khung_gio_24h, columns=days_7)
            if not df_matrix_data.empty:
                for _, r in df_matrix_data.iterrows():
                    if str(r['Ngày']) in days_7 and str(r['Ca làm việc']) in khung_gio_24h:
                        matrix.at[str(r['Ca làm việc']), str(r['Ngày'])] = f"🔴 {r['Người sử dụng']}"

            def style_matrix(val):
                if "🔴" in val: return 'background-color: #ff4b4b; color: white;'
                return 'background-color: #2ecc71; color: white;'
            
            st.info("💡 Click vào từng ô đỏ để xem chi tiết người đặt.")
            event = st.dataframe(
                matrix.style.map(style_matrix),
                use_container_width=True,
                on_select="rerun",
                selection_mode="single-cell"
            )

            if event and len(event.selection.rows) > 0 and len(event.selection.columns) > 0:
                r_idx = event.selection.rows[0]
                c_idx = event.selection.columns[0]
                s_hour = matrix.index[r_idx]
                s_date = matrix.columns[c_idx]
                
                booked_details = df_lich_view[(df_lich_view['Ngày'] == s_date) & 
                                              (df_lich_view['Ca làm việc'] == s_hour) & 
                                              (df_lich_view['Thiết bị'] == view_mode)]
                
                if not booked_details.empty:
                    r = booked_details.iloc[0]
                    st.error(f"🔴 Tới giờ này, máy sẽ được **{r['Người sử dụng']}** sử dụng. \n\n 👉 *Mục đích: {r['Mục đích']}*")
                else:
                    st.success(f"🟢 Khung giờ này hoàn toàn rảnh!")
            
        st.markdown("---")
        
        # 3. FORM HỢP NHẤT: TỪ GIỜ ... ĐẾN GIỜ ...
        st.markdown(f"### 📝 Thời gian sử dụng thiết bị: **{view_mode}**")
        with st.form("smart_booking"):
            c1, c2, c3, c4 = st.columns([1.5, 1, 1, 2])
            
            current_h = get_now().hour
            
            with c1: 
                d_pick = st.date_input("🗓️ Chọn ngày", min_value=today)
            with c2: 
                # Thêm option "Bây giờ" lên đầu danh sách
                time_start = st.selectbox("⏳ Từ lúc:", ["Bây giờ"] + [f"{i:02d}:00" for i in range(24)])
            with c3: 
                time_end = st.selectbox("⏳ Đến lúc:", [f"{i:02d}:00" for i in range(1, 25)], index=current_h if current_h < 24 else 23)
            with c4: 
                note = st.text_input("Mục đích (VD: Đo phổ ZnO)")
            
            st.markdown("---")
            # GỘP CHUNG THÀNH 1 NÚT XÁC NHẬN DUY NHẤT
            btn_submit = st.form_submit_button("🔥 Xác nhận")
            
            if btn_submit:
                d_str = d_pick.strftime("%d/%m/%Y")
                current_time = get_now()
                today_str = current_time.strftime("%d/%m/%Y")
                
                # Logic thông minh: Tự đánh giá là "Mượn ngay" hay "Đặt lịch"
                if time_start == "Bây giờ":
                    if d_str != today_str:
                        st.error("❌ Lỗi: Tính năng 'Bây giờ' chỉ dùng được cho ngày hôm nay!")
                        st.stop()
                    start_h = current_time.hour
                    is_using_now = True
                else:
                    start_h = int(time_start.split(":")[0])
                    # Nếu chọn đúng ngày hôm nay và giờ bắt đầu bằng giờ hiện tại -> Hiểu là Mượn ngay
                    is_using_now = (d_str == today_str and start_h == current_time.hour)
                
                end_h = 24 if time_end == "24:00" else int(time_end.split(":")[0])
                
                if end_h <= start_h:
                    st.error("❌ Lỗi: Giờ kết thúc phải lớn hơn giờ bắt đầu!")
                    st.stop()
                
                if d_str == today_str and start_h < current_time.hour:
                    st.error(f"⏳ Lỗi: Không thể đặt giờ quá khứ. Hiện tại đã là {current_time.hour}:00!")
                    st.stop()
                
                # Tạo danh sách các giờ sẽ bị bôi đỏ trên ma trận
                g_picks = [f"{h:02d}:00" for h in range(start_h, end_h)]
                
                # Lấy dữ liệu Real-time
                sheet_lich_rt = sh.worksheet("LichTuan")
                df_lich_rt = pd.DataFrame(sheet_lich_rt.get_all_records())
                
                # Rà soát trùng lịch
                conflicts = []
                for g in g_picks:
                    conflict = df_lich_rt[(df_lich_rt['Ngày'] == d_str) & (df_lich_rt['Ca làm việc'] == g) & (df_lich_rt['Thiết bị'] == view_mode)]
                    if not conflict.empty and conflict.iloc[0]['Người sử dụng'] != st.session_state['ho_ten']:
                        conflicts.append(g)
                        
                if conflicts: 
                    st.error(f"❌ Rất tiếc, {view_mode} đã bị người khác đặt vào lúc: {', '.join(conflicts)}")
                else:
                    # 1. Bôi đỏ Ma trận (ghi vào LichTuan)
                    for g in g_picks:
                        already = df_lich_rt[(df_lich_rt['Ngày'] == d_str) & (df_lich_rt['Ca làm việc'] == g) & (df_lich_rt['Thiết bị'] == view_mode) & (df_lich_rt['Người sử dụng'] == st.session_state['ho_ten'])]
                        if already.empty:
                            sheet_lichtuan.append_row([d_str, g, st.session_state['ho_ten'], view_mode, note])
                    
                    # 2. Xử lý Trạng thái Thiết bị và Lịch sử
                    if is_using_now:
                        cell = sheet_thietbi.find(view_mode)
                        sheet_thietbi.update_cell(cell.row, 3, "Đang mượn")
                        sheet_thietbi.update_cell(cell.row, 4, st.session_state['ho_ten'])
                        sheet_lichsu.append_row([get_now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], f"Mượn trực tiếp ({start_h}:00 -> {time_end})", view_mode])
                        st.success(f"✅ Đã ghi nhận bạn mượn {view_mode} đến {time_end}. Ma trận đã được đồng bộ!")
                    else:
                        display_start = "Bây giờ" if time_start == "Bây giờ" else f"{start_h:02d}:00"
                        sheet_lichsu.append_row([get_now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], f"Đặt lịch ({d_str} {display_start} -> {time_end})", view_mode])
                        st.success("✅ Đã đặt lịch thành công. Ma trận đã được đồng bộ!")
                        
                    load_data.clear() 
                    st.rerun()

    # --- TAB 3 & 4 (GIỮ NGUYÊN LỊCH SỬ) ---
    with tab3:
        st.subheader("Lịch sử hoạt động")
        df_h = load_data("LichSu")
        if not df_h.empty: st.dataframe(df_h.iloc[::-1], use_container_width=True, hide_index=True)

    # --- TAB 4: TRẢ THIẾT BỊ VÀ THÊM GHI CHÚ TÌNH TRẠNG MÁY ---
    with tab4:
        st.subheader("🔄 Hoàn trả thủ công & Ghi chú tình trạng")
        if "Người sử dụng" in df_tb.columns:
            my_list = df_tb[df_tb["Người sử dụng"] == st.session_state['ho_ten']]['Tên'].tolist()
            if not my_list: st.success("Bạn hiện không giữ thiết bị nào.")
            else:
                with st.form("return_form"):
                    dev_ret = st.selectbox("Thiết bị đang giữ", my_list)
                    # Mục ghi chú sau sử dụng (Tùy chọn)
                    return_note = st.text_input("Ghi chú sau khi dùng (VD: Máy chạy tốt, Đã rửa sạch cối...)")
                    
                    if st.form_submit_button("Xác nhận Trả"):
                        cell = sheet_thietbi.find(dev_ret)
                        sheet_thietbi.update_cell(cell.row, 3, "Sẵn sàng")
                        sheet_thietbi.update_cell(cell.row, 4, "")
                        
                        # Gắn ghi chú vào chung với cột Hành động để lịch sử gọn gàng
                        action_str = f"Hoàn trả (Ghi chú: {return_note})" if return_note else "Hoàn trả"
                        sheet_lichsu.append_row([get_now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], action_str, dev_ret])
                        
                        st.success(f"✅ Đã trả {dev_ret}. Cảm ơn bạn đã cập nhật tình trạng thiết bị!")
                        load_data.clear() 
                        st.rerun()
