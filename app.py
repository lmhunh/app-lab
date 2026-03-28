import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta, timezone, time as dt_time
import time

# ==========================================
# 1. CẤU HÌNH & KẾT NỐI (GMT+7)
# ==========================================
st.set_page_config(page_title="Hệ thống Lab (Minute Precision)", page_icon="⏱️", layout="wide")

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
# 2. ROBOT TỰ ĐỘNG THU HỒI (THEO PHÚT)
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
                            # Phân tích chuỗi "14:15 - 15:30"
                            _, e_str = ca.split(" - ")
                            e_time = datetime.strptime(e_str.strip(), "%H:%M").time()
                            if latest_end is None or e_time > latest_end:
                                latest_end = e_time
                        except: pass
                    
                    # Thu hồi nếu giờ hiện tại đã vượt qua giờ kết thúc
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
    col_t.title("⏱️ Quản lý Thiết bị Lab (Chi tiết Phút)")
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
                    <div><h3 style='margin: 0;'>{view_mode} đang SẴN SÀNG!</h3></div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style='padding: 20px; border-radius: 10px; background-color: #f8d7da; color: #721c24; display: flex; align-items: center; border: 1px solid #f5c6cb;'>
                    <h1 style='margin: 0; padding-right: 20px; font-size: 3rem;'>🔴</h1>
                    <div>
                        <h3 style='margin: 0;'>{view_mode} đang BẬN!</h3>
                        <p style='margin: 0; font-size: 1.1rem;'>Người đang dùng: <b>{current_user}</b></p>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        st.write("") 

        # 2. MA TRẬN LỊCH ẨN (LOGIC QUÉT THEO PHÚT)
        with st.expander("📅 Bấm vào đây để mở Ma trận lịch (Kiểm tra giờ rảnh)", expanded=False):
            df_matrix_data = df_lich_view[df_lich_view['Thiết bị'] == view_mode] if not df_lich_view.empty else pd.DataFrame()
            matrix = pd.DataFrame("🟢 Trống", index=khung_gio_24h, columns=days_7)
            
            # Quét và tô đỏ ma trận nếu có bất kỳ phút nào bị trùng trong khung giờ đó
            if not df_matrix_data.empty:
                for _, r in df_matrix_data.iterrows():
                    ca = str(r['Ca làm việc'])
                    if " - " in ca and str(r['Ngày']) in days_7:
                        try:
                            s_str, e_str = ca.split(" - ")
                            s_time = datetime.strptime(s_str.strip(), "%H:%M").time()
                            e_time = datetime.strptime(e_str.strip(), "%H:%M").time()
                            
                            for h in range(24):
                                block_start = dt_time(h, 0)
                                block_end = dt_time(h, 59)
                                # Kiểm tra xem khoảng đặt lịch có giao với block 1 tiếng này không
                                if s_time <= block_end and block_start <= e_time:
                                    current_val = matrix.at[f"{h:02d}:00", str(r['Ngày'])]
                                    if "🔴" in current_val:
                                        matrix.at[f"{h:02d}:00", str(r['Ngày'])] += f", {r['Người sử dụng']}"
                                    else:
                                        matrix.at[f"{h:02d}:00", str(r['Ngày'])] = f"🔴 {r['Người sử dụng']}"
                        except: pass

            def style_matrix(val):
                if "🔴" in val: return 'background-color: #ff4b4b; color: white;'
                return 'background-color: #2ecc71; color: white;'
            
            st.info("💡 Ma trận sẽ hiện Đỏ nếu có người sử dụng dù chỉ 1 phút trong khung giờ đó. Click vào để xem chi tiết giờ giấc.")
            event = st.dataframe(
                matrix.style.map(style_matrix),
                use_container_width=True,
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
                
                overlapping_bookings = []
                if not df_matrix_data.empty:
                    df_day = df_matrix_data[df_matrix_data['Ngày'] == s_date]
                    for _, r in df_day.iterrows():
                        try:
                            s_t = datetime.strptime(r['Ca làm việc'].split(" - ")[0].strip(), "%H:%M").time()
                            e_t = datetime.strptime(r['Ca làm việc'].split(" - ")[1].strip(), "%H:%M").time()
                            if s_t <= block_end and block_start <= e_t:
                                overlapping_bookings.append(r)
                        except: pass
                
                if overlapping_bookings:
                    st.error(f"🔴 Trong khung **{s_hour_str}** ngày **{s_date}**, có các lịch sau:")
                    for r in overlapping_bookings:
                        st.write(f"- ⏱️ **{r['Ca làm việc']}**: {r['Người sử dụng']} (*{r['Mục đích']}*)")
                else:
                    st.success(f"🟢 Khung {s_hour_str} hoàn toàn rảnh!")
            
        st.markdown("---")
        
        # 3. FORM THỜI GIAN THEO PHÚT
        st.markdown(f"### 📝 Thời gian sử dụng thiết bị: **{view_mode}**")
        with st.form("smart_booking"):
            c1, c2, c3, c4 = st.columns([1.5, 1, 1, 2])
            
            with c1: 
                d_pick = st.date_input("🗓️ Chọn ngày", min_value=today)
            with c2: 
                is_now = st.checkbox("Sử dụng BÂY GIỜ", value=True)
                if not is_now:
                    # step=60 cho phép người dùng chọn chính xác từng phút
                    t_start = st.time_input("⏳ Từ lúc (Giờ:Phút):", value=get_now().time(), step=60)
                else:
                    t_start = get_now().time()
                    st.write(f"⏳ Từ lúc: **{t_start.strftime('%H:%M')}**")
            with c3: 
                t_end = st.time_input("⏳ Đến lúc (Giờ:Phút):", value=(get_now() + timedelta(hours=1)).time(), step=60)
            with c4: 
                note = st.text_input("Mục đích (VD: Đo phổ ZnO)")
            
            st.markdown("---")
            btn_submit = st.form_submit_button("🔥 Xác nhận")
            
            if btn_submit:
                d_str = d_pick.strftime("%d/%m/%Y")
                today_str = get_now().strftime("%d/%m/%Y")
                
                if t_end <= t_start:
                    st.error("❌ Lỗi: Giờ kết thúc phải lớn hơn giờ bắt đầu!")
                    st.stop()
                
                if d_str == today_str and t_start < get_now().time() and not is_now:
                    st.error(f"⏳ Lỗi: Không thể đặt giờ trong quá khứ!")
                    st.stop()
                
                sheet_lich_rt = sh.worksheet("LichTuan")
                df_lich_rt = pd.DataFrame(sheet_lich_rt.get_all_records())
                
                # THUẬT TOÁN KIỂM TRA TRÙNG LỊCH THEO TỪNG PHÚT
                conflict_found = []
                if not df_lich_rt.empty:
                    df_day_device = df_lich_rt[(df_lich_rt['Ngày'] == d_str) & (df_lich_rt['Thiết bị'] == view_mode)]
                    for _, row in df_day_device.iterrows():
                        try:
                            exist_start = datetime.strptime(row['Ca làm việc'].split(" - ")[0].strip(), "%H:%M").time()
                            exist_end = datetime.strptime(row['Ca làm việc'].split(" - ")[1].strip(), "%H:%M").time()
                            
                            # Nếu có phần giao nhau về thời gian
                            if t_start < exist_end and exist_start < t_end:
                                conflict_found.append(f"{row['Ca làm việc']} (bởi {row['Người sử dụng']})")
                        except: pass

                if conflict_found: 
                    st.error(f"❌ Rất tiếc, {view_mode} đã bị kẹt lịch vào lúc: {', '.join(conflict_found)}")
                else:
                    ca_lam_viec_str = f"{t_start.strftime('%H:%M')} - {t_end.strftime('%H:%M')}"
                    sheet_lichtuan.append_row([d_str, ca_lam_viec_str, st.session_state['ho_ten'], view_mode, note])
                    
                    if is_now and d_str == today_str:
                        cell = sheet_thietbi.find(view_mode)
                        sheet_thietbi.update_cell(cell.row, 3, "Đang mượn")
                        sheet_thietbi.update_cell(cell.row, 4, st.session_state['ho_ten'])
                        sheet_lichsu.append_row([get_now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], f"Mượn trực tiếp ({ca_lam_viec_str})", view_mode])
                        st.success(f"✅ Đã ghi nhận mượn {view_mode}. Lịch sẽ tự động thu hồi lúc {t_end.strftime('%H:%M')}.")
                    else:
                        sheet_lichsu.append_row([get_now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], f"Đặt lịch ({d_str} {ca_lam_viec_str})", view_mode])
                        st.success("✅ Đã đặt lịch thành công!")
                        
                    load_data.clear() 
                    st.rerun()

    # --- TAB 3 & 4 (GIỮ NGUYÊN) ---
    with tab3:
        st.subheader("Lịch sử hoạt động")
        df_h = load_data("LichSu")
        if not df_h.empty: st.dataframe(df_h.iloc[::-1], use_container_width=True, hide_index=True)

    with tab4:
        st.subheader("🔄 Hoàn trả thủ công & Ghi chú tình trạng")
        if "Người sử dụng" in df_tb.columns:
            my_list = df_tb[df_tb["Người sử dụng"] == st.session_state['ho_ten']]['Tên'].tolist()
            if not my_list: st.success("Bạn hiện không giữ thiết bị nào.")
            else:
                with st.form("return_form"):
                    dev_ret = st.selectbox("Thiết bị đang giữ", my_list)
                    return_note = st.text_input("Ghi chú sau khi dùng (VD: Máy chạy tốt, Đã rửa sạch cối...)")
                    
                    if st.form_submit_button("Xác nhận Trả"):
                        cell = sheet_thietbi.find(dev_ret)
                        sheet_thietbi.update_cell(cell.row, 3, "Sẵn sàng")
                        sheet_thietbi.update_cell(cell.row, 4, "")
                        
                        action_str = f"Hoàn trả (Ghi chú: {return_note})" if return_note else "Hoàn trả"
                        sheet_lichsu.append_row([get_now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], action_str, dev_ret])
                        
                        st.success(f"✅ Đã trả {dev_ret}.")
                        load_data.clear() 
                        st.rerun()
