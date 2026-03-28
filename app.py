import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta, timezone
import time

# ==========================================
# 1. CẤU HÌNH & KẾT NỐI (CỐ ĐỊNH GMT+7)
# ==========================================
st.set_page_config(page_title="Hệ thống Lab (Sync Time)", page_icon="⏱️", layout="wide")

# Khai báo múi giờ Việt Nam (GMT+7)
VN_TZ = timezone(timedelta(hours=7))

def get_now():
    """Hàm lấy thời gian thực chính xác theo GMT+7"""
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
# 2. ROBOT TỰ ĐỘNG THU HỒI (CHẠY THEO GMT+7)
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
    
    # Lấy ngày hôm nay theo chuẩn VN_TZ
    today = get_now().date()
    days_7 = [(today + timedelta(days=i)).strftime("%d/%m/%Y") for i in range(7)]

    tab1, tab2, tab3, tab4 = st.tabs(["📊 Trạng thái", "📅 Ma trận Tương tác", "🕒 Lịch sử", "🔄 Trả thiết bị"])

    # --- TAB 1: TRẠNG THÁI ---
    with tab1:
        st.subheader("Tình trạng thiết bị hiện tại")
        if not df_tb.empty:
            st.dataframe(df_tb, use_container_width=True, hide_index=True)

    # --- TAB 2: MA TRẬN THEO TỪNG THIẾT BỊ ---
    with tab2:
        st.subheader("📅 Bảng đăng ký Lab tương tác")
        
        c_filter, _ = st.columns([1, 2])
        with c_filter:
            view_mode = st.selectbox("🔍 Chọn thiết bị để xem lịch:", all_devices if all_devices else ["Chưa có dữ liệu"])
        
        df_matrix_data = df_lich_view[df_lich_view['Thiết bị'] == view_mode] if not df_lich_view.empty else pd.DataFrame()

        matrix = pd.DataFrame("🟢 Trống", index=khung_gio_24h, columns=days_7)
        if not df_matrix_data.empty:
            for _, r in df_matrix_data.iterrows():
                if str(r['Ngày']) in days_7 and str(r['Ca làm việc']) in khung_gio_24h:
                    matrix.at[str(r['Ca làm việc']), str(r['Ngày'])] = f"🔴 {r['Người sử dụng']}"

        def style_matrix(val):
            if "🔴" in val: return 'background-color: #ff4b4b; color: white;'
            return 'background-color: #2ecc71; color: white;'
        
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
            
            st.markdown(f"### 🔍 Chi tiết lúc **{s_hour}** ngày **{s_date}**")
            booked_details = df_lich_view[(df_lich_view['Ngày'] == s_date) & 
                                          (df_lich_view['Ca làm việc'] == s_hour) & 
                                          (df_lich_view['Thiết bị'] == view_mode)]
            
            if not booked_details.empty:
                r = booked_details.iloc[0]
                st.error(f"🔴 **{view_mode}** đang được đặt bởi **{r['Người sử dụng']}** \n\n 👉 *Mục đích: {r['Mục đích']}*")
            else:
                st.success(f"🟢 **{view_mode}** đang trống! Bạn có thể mượn ngay hoặc đặt lịch bên dưới.")
        
        st.markdown("---")

        st.markdown(f"### 📝 Đăng ký / Mượn nhanh thiết bị: **{view_mode}**")
        with st.form("smart_booking"):
            c1, c2, c3 = st.columns(3)
            with c1: d_pick = st.date_input("Chọn ngày", min_value=today)
            with c2: g_picks = st.multiselect("Chọn các khung giờ", khung_gio_24h)
            with c3: note = st.text_input("Mục đích (VD: Đo phổ ZnO)")
            
            c_sub, c_now = st.columns(2)
            with c_sub: btn_book = st.form_submit_button("🔥 Xác nhận Đặt lịch")
            with c_now: btn_use_now = st.form_submit_button("⚡ Mượn ngay bây giờ")
            
            # --- XỬ LÝ ĐẶT LỊCH ---
            if btn_book:
                d_str = d_pick.strftime("%d/%m/%Y")
                current_time = get_now()
                today_str = current_time.strftime("%d/%m/%Y")
                current_hour = current_time.hour
                
                # 1. KIỂM TRA ĐẶT LỊCH QUÁ KHỨ (Cùng ngày nhưng giờ đã qua)
                if d_str == today_str:
                    past_hours = [g for g in g_picks if int(g.split(":")[0]) <= current_hour]
                    if past_hours:
                        st.error(f"⏳ Lỗi: Bạn không thể đặt các giờ đã qua trong hôm nay ({', '.join(past_hours)}). Hãy chọn từ {current_hour + 1}:00 trở đi!")
                        st.stop()
                
                # 2. KIỂM TRA TRÙNG LỊCH THỜI GIAN THỰC
                sheet_lich_rt = sh.worksheet("LichTuan")
                df_lich_rt = pd.DataFrame(sheet_lich_rt.get_all_records())
                
                conflicts = [g for g in g_picks if not df_lich_rt[(df_lich_rt['Ngày'] == d_str) & (df_lich_rt['Ca làm việc'] == g) & (df_lich_rt['Thiết bị'] == view_mode)].empty]
                
                if conflicts: st.error(f"❌ Rất tiếc, {view_mode} đã bị đặt vào lúc: {', '.join(conflicts)}")
                elif not g_picks: st.warning("Vui lòng chọn khung giờ!")
                else:
                    for g in g_picks:
                        sheet_lichtuan.append_row([d_str, g, st.session_state['ho_ten'], view_mode, note])
                        # Ghi log Đặt lịch
                        sheet_lichsu.append_row([get_now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], f"Đặt lịch ({d_str} {g})", view_mode])
                    st.success("✅ Đã đặt lịch thành công!")
                    load_data.clear() 
                    st.rerun()
            
            # --- XỬ LÝ MƯỢN NGAY ---
            if btn_use_now:
                current_time = get_now()
                d_str = current_time.strftime("%d/%m/%Y")
                h_str = current_time.strftime("%H:00")
                
                sheet_lich_rt = sh.worksheet("LichTuan")
                df_lich_rt = pd.DataFrame(sheet_lich_rt.get_all_records())
                
                conflict = df_lich_rt[(df_lich_rt['Ngày'] == d_str) & (df_lich_rt['Ca làm việc'] == h_str) & (df_lich_rt['Thiết bị'] == view_mode)]
                if not conflict.empty and conflict.iloc[0]['Người sử dụng'] != st.session_state['ho_ten']:
                    st.error(f"⚠️ {view_mode} đang bận! Được {conflict.iloc[0]['Người sử dụng']} đặt lịch lúc này.")
                else:
                    cell = sheet_thietbi.find(view_mode)
                    sheet_thietbi.update_cell(cell.row, 3, "Đang mượn")
                    sheet_thietbi.update_cell(cell.row, 4, st.session_state['ho_ten'])
                    sheet_lichsu.append_row([current_time.strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], "Sử dụng", view_mode])
                    st.success(f"✅ Đã ghi nhận bạn đang sử dụng {view_mode}")
                    load_data.clear() 
                    st.rerun()

    # --- TAB 3 & 4 ---
    with tab3:
        st.subheader("Lịch sử hoạt động")
        df_h = load_data("LichSu")
        if not df_h.empty: st.dataframe(df_h.iloc[::-1], use_container_width=True, hide_index=True)

    with tab4:
        st.subheader("🔄 Hoàn trả thủ công")
        if "Người sử dụng" in df_tb.columns:
            my_list = df_tb[df_tb["Người sử dụng"] == st.session_state['ho_ten']]['Tên'].tolist()
            if not my_list: st.success("Bạn hiện không giữ thiết bị nào.")
            else:
                with st.form("return_form"):
                    dev_ret = st.selectbox("Thiết bị đang giữ", my_list)
                    if st.form_submit_button("Trả sớm"):
                        cell = sheet_thietbi.find(dev_ret)
                        sheet_thietbi.update_cell(cell.row, 3, "Sẵn sàng")
                        sheet_thietbi.update_cell(cell.row, 4, "")
                        sheet_lichsu.append_row([get_now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], "Hoàn trả sớm", dev_ret])
                        st.success(f"✅ Đã trả {dev_ret}")
                        load_data.clear() 
                        st.rerun()
