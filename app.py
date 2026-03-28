import streamlit as st
import pandas as pd
import gspread
from datetime import datetime

# ==========================================
# 1. CẤU HÌNH TRANG
# ==========================================
st.set_page_config(page_title="Hệ thống Quản lý Lab", page_icon="🧪", layout="wide")

# ==========================================
# 2. HÀM KẾT NỐI (TRỊ DỨT ĐIỂM LỖI PEM & JWT)
# ==========================================
@st.cache_resource
def connect_to_gsheets():
    try:
        # Lấy dữ liệu từ "Két sắt" Secrets
        creds_dict = dict(st.secrets["my_creds"])
        
        # BỘ LỌC LÀM SẠCH PRIVATE_KEY
        if "private_key" in creds_dict:
            pk = creds_dict["private_key"]
            # 1. Loại bỏ khoảng trắng/dòng trống ở đầu và cuối
            pk = pk.strip()
            # 2. Ép tất cả các chuỗi "\n" bị lỗi thành lệnh xuống dòng thực sự
            pk = pk.replace("\\n", "\n")
            # Cập nhật lại key đã làm sạch
            creds_dict["private_key"] = pk
            
        return gspread.service_account_from_dict(creds_dict)
    except Exception as e:
        st.error(f"❌ Lỗi giải mã bí mật từ Secrets: {e}")
        st.stop()

# Khởi tạo kết nối Google Sheets
try:
    gc = connect_to_gsheets()
    # Tên file phải khớp 100% trên Google Drive
    sh = gc.open("Quan_ly_lab") 
    sheet_thietbi = sh.worksheet("ThietBi")
    sheet_taikhoan = sh.worksheet("TaiKhoan")
    sheet_lichsu = sh.worksheet("LichSu")
    sheet_lichtuan = sh.worksheet("LichTuan")
except Exception as e:
    st.error(f"❌ Lỗi kết nối Google Sheets: {e}")
    st.info("💡 Bạn đã Share file Sheets cho email bot (culi-109@...) với quyền Editor chưa?")
    st.stop()

# ==========================================
# 3. HÀM TẢI DỮ LIỆU
# ==========================================
def load_data(sheet):
    return pd.DataFrame(sheet.get_all_records())

# ==========================================
# 4. QUẢN LÝ ĐĂNG NHẬP
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['ho_ten'] = ""

if not st.session_state['logged_in']:
    st.title("🔐 Đăng nhập Hệ thống Lab")
    with st.form("login_form"):
        username = st.text_input("Tài khoản")
        password = st.text_input("Mật khẩu", type="password")
        submit_login = st.form_submit_button("Đăng nhập")

        if submit_login:
            df_tk = load_data(sheet_taikhoan)
            # Kiểm tra tài khoản
            match = df_tk[(df_tk['TaiKhoan'].astype(str) == str(username)) & 
                          (df_tk['MatKhau'].astype(str) == str(password))]

            if not match.empty:
                st.session_state['logged_in'] = True
                st.session_state['ho_ten'] = match.iloc[0]['HoTen']
                st.rerun()
            else:
                st.error("❌ Sai tài khoản hoặc mật khẩu!")

# ==========================================
# 5. GIAO DIỆN CHÍNH (SAU KHI ĐĂNG NHẬP)
# ==========================================
else:
    col_title, col_logout = st.columns([8, 2])
    with col_title:
        st.title("🧪 Phần mềm Quản lý Thiết bị Lab")
    with col_logout:
        st.write(f"👤 Chào, **{st.session_state['ho_ten']}**")
        if st.button("🚪 Đăng xuất"):
            st.session_state['logged_in'] = False
            st.rerun()

    st.markdown("---")
    df = load_data(sheet_thietbi)
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Trạng thái thiết bị", "🔄 Mượn / Trả", "🕒 Lịch sử", "📅 Lịch theo tuần"])

    # --- TAB 1: HIỂN THỊ DANH SÁCH ---
    with tab1:
        st.subheader("Danh sách thiết bị hiện tại")
        def color_status(val):
            color = 'red' if val == 'Hỏng' else ('orange' if val == 'Đang mượn' else 'green')
            return f'color: {color}'
        
        if not df.empty:
            st.dataframe(df.style.map(color_status, subset=['Trạng thái']), use_container_width=True, hide_index=True)
        else:
            st.info("Chưa có dữ liệu thiết bị.")

    # --- TAB 2: MƯỢN / TRẢ ---
    with tab2:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Đăng ký Mượn")
            ready_devices = df[df['Trạng thái'] == 'Sẵn sàng']['Tên'].tolist() if not df.empty else []
            with st.form("borrow_form"):
                selected_device = st.selectbox("Chọn thiết bị", ready_devices)
                note = st.text_input("Ghi chú mượn (VD: Đo phổ mẫu mới)")
                if st.form_submit_button("Xác nhận Mượn"):
                    if selected_device:
                        cell = sheet_thietbi.find(selected_device)
                        sheet_thietbi.update_cell(cell.row, 3, "Đang mượn")
                        sheet_thietbi.update_cell(cell.row, 4, st.session_state['ho_ten'])
                        sheet_thietbi.update_cell(cell.row, 5, note)
                        
                        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                        sheet_lichsu.append_row([now, st.session_state['ho_ten'], "Mượn", selected_device])
                        st.success(f"✅ Đã mượn {selected_device}")
                        st.rerun()

        with col2:
            st.subheader("Đăng ký Trả")
            borrowed_devices = df[df['Trạng thái'] == 'Đang mượn']['Tên'].tolist() if not df.empty else []
            with st.form("return_form"):
                return_device = st.selectbox("Chọn thiết bị trả", borrowed_devices)
                if st.form_submit_button("Xác nhận Trả"):
                    if return_device:
                        cell = sheet_thietbi.find(return_device)
                        sheet_thietbi.update_cell(cell.row, 3, "Sẵn sàng")
                        sheet_thietbi.update_cell(cell.row, 4, "")
                        sheet_thietbi.update_cell(cell.row, 5, "Đã trả")
                        
                        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                        sheet_lichsu.append_row([now, st.session_state['ho_ten'], "Trả", return_device])
                        st.success(f"✅ Đã trả {return_device}")
                        st.rerun()

    # --- TAB 3: LỊCH SỬ ---
    with tab3:
        st.subheader("Lịch sử giao dịch gần đây")
        history_data = load_data(sheet_lichsu)
        if not history_data.empty:
            st.dataframe(history_data.iloc[::-1], use_container_width=True, hide_index=True)
        else:
            st.info("Chưa có lịch sử giao dịch.")
# --- TAB 4: ĐĂNG KÝ LỊCH THEO TUẦN (GIAO DIỆN WHEN2MEET) ---
    with tab4:
        st.subheader("📅 Ma trận lịch trình Lab trong tuần")
        
        # 1. Lấy dữ liệu và xử lý ngày tháng
        df_lich = load_data(sheet_lichtuan)
        
        # Tạo danh sách 7 ngày trong tuần tới (từ hôm nay)
        today = datetime.now().date()
        days_of_week = [(today + pd.Timedelta(days=i)).strftime("%d/%m/%Y") for i in range(7)]
        time_slots = ["Sáng (8h-12h)", "Chiều (13h-17h)", "Tối (18h-22h)"]

        # 2. Hiển thị Ma trận (Heatmap)
        if not df_lich.empty:
            # Tạo bảng trống (Row: Ca làm việc, Col: Ngày)
            matrix = pd.DataFrame("", index=time_slots, columns=days_of_week)
            
            # Đổ dữ liệu từ Sheets vào bảng ma trận
            for _, row in df_lich.iterrows():
                if row['Ngày'] in days_of_week and row['Ca làm việc'] in time_slots:
                    # Hiển thị: Tên người (Tên thiết bị)
                    content = f"{row['Người đăng ký']} ({row['Thiết bị']})"
                    # Nếu ô đã có người, thêm dấu phẩy để tránh ghi đè
                    if matrix.at[row['Ca làm việc'], row['Ngày']] == "":
                        matrix.at[row['Ca làm việc'], row['Ngày']] = content
                    else:
                        matrix.at[row['Ca làm việc'], row['Ngày']] += f" | {content}"

            # Hàm tô màu cho bảng giống When2meet
            def highlight_booked(val):
                if val != "":
                    return 'background-color: #ff4b4b; color: white;' # Màu đỏ nếu có người đặt
                return 'background-color: #2ecc71; color: white;'     # Màu xanh nếu trống
            
            st.write("💡 **Xanh:** Trống | **Đỏ:** Đã có lịch")
            st.dataframe(matrix.style.applymap(highlight_booked), use_container_width=True)
        else:
            st.info("Chưa có lịch đăng ký nào cho tuần này.")

        st.markdown("---")
        
        # 3. Form Đăng ký (Giữ lại form để nhập liệu)
        st.markdown("### 📝 Đăng ký ca làm việc mới")
        c1, c2, c3 = st.columns(3)
        with st.form("new_booking"):
            with c1:
                ngay_dk = st.date_input("Chọn ngày", min_value=today)
            with c2:
                ca_dk = st.selectbox("Chọn ca", time_slots)
                thiet_bi_dk = st.selectbox("Thiết bị", df['Tên'].tolist() if not df.empty else ["Bàn lab"])
            with c3:
                muc_dich = st.text_input("Mục đích sử dụng", placeholder="VD: Rửa cốc,...")
            
            if st.form_submit_button("Xác nhận đăng ký"):
                if muc_dich:
                    ngay_str = ngay_dk.strftime("%d/%m/%Y")
                    sheet_lichtuan.append_row([ngay_str, ca_dk, st.session_state['ho_ten'], thiet_bi_dk, muc_dich])
                    st.success("Đã cập nhật lịch trình!")
                    st.rerun()
                else:
                    st.warning("Vui lòng nhập mục đích!")
