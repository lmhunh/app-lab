import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta

# ==========================================
# 1. CẤU HÌNH & KẾT NỐI
# ==========================================
st.set_page_config(page_title="Hệ thống Lab (Thời gian thực)", page_icon="⏱️", layout="wide")

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
    """Hàm tải dữ liệu luôn lấy bản mới nhất từ máy chủ Google"""
    return pd.DataFrame(sheet.get_all_records())

# ==========================================
# 2. LOGIC ĐĂNG NHẬP
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
# 3. GIAO DIỆN CHÍNH
# ==========================================
else:
    # --- Sidebar/Header ---
    col_t, col_l = st.columns([8, 2])
    col_t.title("⏱️ Quản lý Thiết bị Lab - Chống trùng thời gian thực")
    with col_l:
        st.write(f"👤 **{st.session_state['ho_ten']}**")
        if st.button("🚪 Đăng xuất"):
            st.session_state['logged_in'] = False
            st.rerun()

    st.markdown("---")
    # Lấy dữ liệu hiển thị giao diện
    df_tb = load_data(sheet_thietbi)
    df_lich_view = load_data(sheet_lichtuan)
    
    khung_gio_24h = [f"{i:02d}:00" for i in range(24)]
    today = datetime.now().date()
    days_7 = [(today + timedelta(days=i)).strftime("%d/%m/%Y") for i in range(7)]

    tab1, tab2, tab3, tab4 = st.tabs(["📊 Trạng thái", "📅 Ma trận Đặt lịch", "🕒 Lịch sử Real-time", "🔄 Trả thiết bị"])

    # --- TAB 1: TRẠNG THÁI ---
    with tab1:
        st.subheader("Tình trạng thiết bị hiện tại")
        if not df_tb.empty:
            st.dataframe(df_tb, use_container_width=True, hide_index=True)

    # --- TAB 2: ĐẶT LỊCH (KIỂM TRA THỜI GIAN THỰC) ---
    with tab2:
        st.subheader("📅 Bảng đăng ký Lab theo tuần (When2meet)")
        
        # 1. Hiển thị Ma trận
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

        # 2. Form Đặt Lịch
        st.markdown("### 📝 Đăng ký ca làm việc")
        with st.form("smart_booking"):
            c1, c2, c3 = st.columns(3)
            with c1: d_pick = st.date_input("Chọn ngày", min_value=today)
            with c2: g_picks = st.multiselect("Chọn các khung giờ", khung_gio_24h)
            with c3: 
                tb_pick = st.selectbox("Thiết bị", df_tb['Tên'].tolist() if not df_tb.empty else [])
                note = st.text_input("Mục đích (VD: Khảo sát màng Cu2O)")
            
            if st.form_submit_button("🔥 Xác nhận Đặt lịch"):
                # BƯỚC QUAN TRỌNG: Tải lại dữ liệu Lịch TẮP LỰC ngay khoảnh khắc bấm nút
                df_lich_realtime = load_data(sheet_lichtuan)
                d_str = d_pick.strftime("%d/%m/%Y")
                
                conflicts = []
                for g in g_picks:
                    # Kiểm tra trên bản dữ liệu MỚI NHẤT
                    is_taken = not df_lich_realtime[
                        (df_lich_realtime['Ngày'] == d_str) & 
                        (df_lich_realtime['Ca làm việc'] == g) & 
                        (df_lich_realtime['Thiết bị'] == tb_pick)
                    ].empty
                    if is_taken: conflicts.append(g)
                
                if conflicts:
                    st.error(f"❌ Rất tiếc! Trong lúc bạn đang chọn, ai đó đã nhanh tay đặt thiết bị này vào lúc: {', '.join(conflicts)}")
                elif not g_picks:
                    st.warning("Vui lòng chọn ít nhất 1 khung giờ!")
                else:
                    now_rt = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    for g in g_picks:
                        # Ghi vào lịch tuần
                        sheet_lichtuan.append_row([d_str, g, st.session_state['ho_ten'], tb_pick, note])
                        # Ghi vào lịch sử hệ thống theo thời gian thực
                        sheet_lichsu.append_row([now_rt, st.session_state['ho_ten'], f"Đặt lịch ({d_str} {g})", tb_pick])
                    
                    st.success("✅ Đã đặt lịch thành công và ghi vào lịch sử thời gian thực!")
                    st.rerun()

    # --- TAB 3: LỊCH SỬ THỜI GIAN THỰC ---
    with tab3:
        st.subheader("Lịch sử hoạt động (Real-time)")
        df_h = load_data(sheet_lichsu)
        if not df_h.empty:
            st.dataframe(df_h.iloc[::-1], use_container_width=True, hide_index=True)

    # --- TAB 4: TRẢ THIẾT BỊ ---
    with tab4:
        st.subheader("🔄 Hoàn trả thiết bị")
        user_col = "Người sử dụng"
        if user_col in df_tb.columns:
            my_list = df_tb[df_tb[user_col] == st.session_state['ho_ten']]['Tên'].tolist()
            if not my_list:
                st.info("Bạn hiện không giữ thiết bị nào.")
            else:
                with st.form("return_form"):
                    dev_ret = st.selectbox("Thiết bị đang giữ", my_list)
                    if st.form_submit_button("Xác nhận hoàn trả"):
                        cell = sheet_thietbi.find(dev_ret)
                        sheet_thietbi.update_cell(cell.row, 3, "Sẵn sàng")
                        sheet_thietbi.update_cell(cell.row, 4, "") # Xóa tên
                        
                        # Ghi nhận thời gian thực chuẩn đến từng giây
                        now_s = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                        sheet_lichsu.append_row([now_s, st.session_state['ho_ten'], "Hoàn trả", dev_ret])
                        st.success(f"✅ Đã trả {dev_ret}")
                        st.rerun()
        else:
            st.error(f"❌ Không tìm thấy cột '{user_col}' trong Google Sheets!")
