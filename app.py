import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta

# ==========================================
# 1. CẤU HÌNH & KẾT NỐI
# ==========================================
st.set_page_config(page_title="Hệ thống Lab (Auto-Return)", page_icon="⏱️", layout="wide")

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

def load_data(sheet):
    return pd.DataFrame(sheet.get_all_records())

# ==========================================
# 2. ROBOT TỰ ĐỘNG THU HỒI THIẾT BỊ
# ==========================================
def auto_return_devices(sheet_tb, sheet_lich, sheet_ls):
    """Quét và tự động thu hồi thiết bị khi hết thời gian đăng ký trong When2meet"""
    try:
        df_tb = load_data(sheet_tb)
        df_lich = load_data(sheet_lich)
        
        if df_tb.empty or df_lich.empty: return
        
        now = datetime.now()
        today_str = now.strftime("%d/%m/%Y")
        current_hour = now.hour
        
        # Lấy danh sách lịch đăng ký của ngày hôm nay
        df_today = df_lich[df_lich['Ngày'] == today_str]
        if df_today.empty: return

        # Quét các thiết bị đang có người mượn
        for _, row in df_tb.iterrows():
            if row.get('Trạng thái') == 'Đang mượn':
                device = row.get('Tên')
                user = row.get('Người sử dụng', '')
                
                # Tìm xem người này có đăng ký thiết bị này hôm nay không
                user_bookings = df_today[(df_today['Thiết bị'] == device) & (df_today['Người sử dụng'] == user)]
                if not user_bookings.empty:
                    # Lấy ra các giờ họ đã đặt (VD: "08:00" -> 8)
                    booked_hours = [int(ca.split(":")[0]) for ca in user_bookings['Ca làm việc'] if ":" in str(ca)]
                    if booked_hours:
                        # Thời gian hết hạn = Khung giờ đặt cuối cùng + 1 (VD: Đặt 15:00 -> 16:00 hết hạn)
                        expire_hour = max(booked_hours) + 1
                        
                        # Nếu giờ hiện tại đã vượt qua hoặc bằng giờ hết hạn -> Tự động thu hồi
                        if current_hour >= expire_hour:
                            cell = sheet_tb.find(device)
                            sheet_tb.update_cell(cell.row, 3, "Sẵn sàng")
                            sheet_tb.update_cell(cell.row, 4, "") # Xóa tên
                            
                            # Ghi vào lịch sử để mọi người cùng thấy
                            now_s = now.strftime("%d/%m/%Y %H:%M:%S")
                            sheet_ls.append_row([now_s, "🤖 Hệ thống (Auto)", "Thu hồi tự động", device])
    except Exception as e:
        pass # Nếu có lỗi thì bỏ qua để không làm sập giao diện web

# ==========================================
# 3. QUẢN LÝ ĐĂNG NHẬP
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state.update({'logged_in': False, 'ho_ten': ""})

if not st.session_state['logged_in']:
    st.title("🔐 Đăng nhập Hệ thống Lab")
    with st.form("login"):
        u = st.text_input("Tài khoản")
        p = st.text_input("Mật khẩu", type="password")
        if st.form_submit_button("Đăng nhập"):
            df_tk = load_data(sheet_taikhoan)
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
    col_t.title("⏱️ Quản lý Thiết bị Lab - Auto Return")
    with col_l:
        st.write(f"👤 **{st.session_state['ho_ten']}**")
        if st.button("🚪 Đăng xuất"):
            st.session_state['logged_in'] = False
            st.rerun()

    st.markdown("---")
    
    # KÍCH HOẠT ROBOT TỰ ĐỘNG THU HỒI TRƯỚC KHI TẢI GIAO DIỆN
    auto_return_devices(sheet_thietbi, sheet_lichtuan, sheet_lichsu)
    
    # Tải dữ liệu hiển thị (Bao gồm cả các máy vừa được Robot thu hồi)
    df_tb = load_data(sheet_thietbi)
    df_lich_view = load_data(sheet_lichtuan)
    
    khung_gio_24h = [f"{i:02d}:00" for i in range(24)]
    today = datetime.now().date()
    days_7 = [(today + timedelta(days=i)).strftime("%d/%m/%Y") for i in range(7)]

    tab1, tab2, tab3, tab4 = st.tabs(["📊 Trạng thái", "📅 Ma trận Đặt lịch", "🕒 Lịch sử", "🔄 Trả thiết bị"])

    # --- TAB 1: TRẠNG THÁI ---
    with tab1:
        st.subheader("Tình trạng thiết bị hiện tại")
        if not df_tb.empty:
            st.dataframe(df_tb, use_container_width=True, hide_index=True)

    # --- TAB 2: ĐẶT LỊCH ---
    with tab2:
        st.subheader("📅 Bảng đăng ký Lab theo tuần (When2meet)")
        
        matrix = pd.DataFrame("", index=khung_gio_24h, columns=days_7)
        if not df_lich_view.empty:
            for _, r in df_lich_view.iterrows():
                if str(r['Ngày']) in days_7 and str(r['Ca làm việc']) in khung_gio_24h:
                    matrix.at[str(r['Ca làm việc']), str(r['Ngày'])] = f"🔴 {r['Người sử dụng']}"

        def style_matrix(val):
            if "🔴" in val: return 'background-color: #ff4b4b; color: white;'
            return 'background-color: #2ecc71; color: white;'
        
        st.write("💡 **Xanh:** Trống | **Đỏ:** Đã có lịch")
        st.dataframe(matrix.style.map(style_matrix), use_container_width=True)

        st.markdown("### 📝 Đăng ký & Mượn Thiết bị")
        with st.form("smart_booking"):
            c1, c2, c3 = st.columns(3)
            with c1: d_pick = st.date_input("Chọn ngày", min_value=today)
            with c2: g_picks = st.multiselect("Chọn các khung giờ", khung_gio_24h)
            with c3: 
                tb_pick = st.selectbox("Thiết bị", df_tb['Tên'].tolist() if not df_tb.empty else [])
                note = st.text_input("Mục đích (VD: Khảo sát màng Cu2O)")
            
            c_submit, c_now = st.columns(2)
            with c_submit:
                btn_book = st.form_submit_button("🔥 Xác nhận Đặt lịch")
            with c_now:
                btn_use_now = st.form_submit_button("⚡ Mượn ngay bây giờ")
            
            # XỬ LÝ ĐẶT LỊCH (TƯƠNG LAI)
            if btn_book:
                df_lich_rt = load_data(sheet_lichtuan)
                d_str = d_pick.strftime("%d/%m/%Y")
                conflicts = [g for g in g_picks if not df_lich_rt[(df_lich_rt['Ngày'] == d_str) & (df_lich_rt['Ca làm việc'] == g) & (df_lich_rt['Thiết bị'] == tb_pick)].empty]
                
                if conflicts: st.error(f"❌ Trùng lịch tại: {', '.join(conflicts)}")
                elif not g_picks: st.warning("Chọn ít nhất 1 khung giờ!")
                else:
                    for g in g_picks:
                        sheet_lichtuan.append_row([d_str, g, st.session_state['ho_ten'], tb_pick, note])
                    st.success("✅ Đã đặt lịch thành công!")
                    st.rerun()
            
            # XỬ LÝ MƯỢN NGAY (THỰC TẾ LẤY MÁY RA DÙNG)
            if btn_use_now:
                d_str = datetime.now().strftime("%d/%m/%Y")
                h_str = datetime.now().strftime("%H:00")
                df_lich_rt = load_data(sheet_lichtuan)
                
                # Kiểm tra xem giờ này có ai đặt trước không
                conflict = df_lich_rt[(df_lich_rt['Ngày'] == d_str) & (df_lich_rt['Ca làm việc'] == h_str) & (df_lich_rt['Thiết bị'] == tb_pick)]
                if not conflict.empty and conflict.iloc[0]['Người sử dụng'] != st.session_state['ho_ten']:
                    st.error(f"⚠️ Không thể mượn! Máy này đã được **{conflict.iloc[0]['Người sử dụng']}** đặt lịch vào giờ này.")
                else:
                    cell = sheet_thietbi.find(tb_pick)
                    sheet_thietbi.update_cell(cell.row, 3, "Đang mượn")
                    sheet_thietbi.update_cell(cell.row, 4, st.session_state['ho_ten'])
                    
                    now_s = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    sheet_lichsu.append_row([now_s, st.session_state['ho_ten'], "Sử dụng", tb_pick])
                    st.success(f"✅ Đã ghi nhận bạn đang sử dụng {tb_pick}")
                    st.rerun()

    # --- TAB 3: LỊCH SỬ ---
    with tab3:
        st.subheader("Lịch sử hoạt động")
        df_h = load_data(sheet_lichsu)
        if not df_h.empty:
            st.dataframe(df_h.iloc[::-1], use_container_width=True, hide_index=True)

    # --- TAB 4: TRẢ THIẾT BỊ ---
    with tab4:
        st.subheader("🔄 Hoàn trả thủ công")
        st.info("Hệ thống sẽ tự động thu hồi khi hết giờ đặt lịch. Bạn chỉ cần dùng form này nếu muốn trả máy **sớm hơn** dự kiến.")
        user_col = "Người sử dụng"
        if user_col in df_tb.columns:
            my_list = df_tb[df_tb[user_col] == st.session_state['ho_ten']]['Tên'].tolist()
            if not my_list:
                st.success("Bạn hiện không giữ thiết bị nào.")
            else:
                with st.form("return_form"):
                    dev_ret = st.selectbox("Thiết bị đang giữ", my_list)
                    if st.form_submit_button("Trả sớm"):
                        cell = sheet_thietbi.find(dev_ret)
                        sheet_thietbi.update_cell(cell.row, 3, "Sẵn sàng")
                        sheet_thietbi.update_cell(cell.row, 4, "")
                        
                        now_s = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                        sheet_lichsu.append_row([now_s, st.session_state['ho_ten'], "Hoàn trả sớm", dev_ret])
                        st.success(f"✅ Đã trả {dev_ret}")
                        st.rerun()
