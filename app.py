import streamlit as st
import pandas as pd
import gspread
from datetime import datetime

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="Hệ thống Quản lý Lab", layout="wide")

# --- KẾT NỐI GOOGLE SHEETS BẢO MẬT ---
# Code tự động nhận diện: Nếu đang chạy trên web (có st.secrets) thì dùng két sắt, nếu chạy ở máy tính thì dùng file.
try:
    if "gcp_service_account" in st.secrets:
        gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
    else:
        gc = gspread.service_account(filename='credentials.json')
except Exception as e:
    st.error("Chưa cấu hình xong file bảo mật. Đang chờ thiết lập...")
    st.stop()
try:
    sh = gc.open("Quan_ly_lab")
    sheet_thietbi = sh.worksheet("ThietBi")
    sheet_lichsu = sh.worksheet("LichSu")
except Exception as e:
    st.error(f"❌ Lỗi chi tiết: {e}")
    st.stop()

# --- HÀM TẢI DỮ LIỆU ---
def load_data():
    data = sheet_thietbi.get_all_records()
    return pd.DataFrame(data)

# --- GIAO DIỆN CHÍNH ---
st.title("🧪 Phần mềm Quản lý Thiết bị Lab")

df = load_data()

tab1, tab2, tab3 = st.tabs(["📊 Trạng thái thiết bị", "🔄 Mượn / Trả", "🕒 Lịch sử"])

# TAB 1: HIỂN THỊ TRẠNG THÁI
with tab1:
    st.subheader("Danh sách thiết bị hiện tại")
    def color_status(val):
        color = 'red' if val == 'Hỏng' else ('orange' if val == 'Đang mượn' else 'green')
        return f'color: {color}'
    
    if not df.empty:
        st.dataframe(df.style.map(color_status, subset=['Trạng thái']), use_container_width=True)
    else:
        st.info("Chưa có dữ liệu thiết bị. Bạn hãy thêm vào Google Sheets nhé!")

# TAB 2: CHỨC NĂNG MƯỢN TRẢ
with tab2:
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Đăng ký Mượn")
        if not df.empty and 'Trạng thái' in df.columns:
            ready_devices = df[df['Trạng thái'] == 'Sẵn sàng']['Tên'].tolist()
        else:
            ready_devices = []
            
        with st.form("borrow_form"):
            selected_device = st.selectbox("Chọn thiết bị", ready_devices)
            borrower_name = st.text_input("Tên của bạn")
            note = st.text_input("Mục đích mượn / Ghi chú")
            # Nút bấm bắt buộc phải thụt lề ngang bằng với các dòng trên
            submit_borrow = st.form_submit_button("Xác nhận Mượn")
            
            if submit_borrow:
                if borrower_name == "":
                    st.warning("⚠️ Vui lòng nhập tên người mượn!")
                elif not selected_device:
                    st.warning("⚠️ Không có thiết bị nào đang sẵn sàng!")
                else:
                    cell = sheet_thietbi.find(selected_device)
                    sheet_thietbi.update_cell(cell.row, 3, "Đang mượn") 
                    sheet_thietbi.update_cell(cell.row, 4, borrower_name) 
                    sheet_thietbi.update_cell(cell.row, 5, note) 
                    
                    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    sheet_lichsu.append_row([now, borrower_name, "Mượn", selected_device])
                    
                    st.success(f"✅ Đã ghi nhận: {borrower_name} mượn {selected_device}")
                    st.rerun() 
                    
    with col2:
        st.subheader("Đăng ký Trả")
        if not df.empty and 'Trạng thái' in df.columns:
            borrowed_devices = df[df['Trạng thái'] == 'Đang mượn']['Tên'].tolist()
        else:
            borrowed_devices = []
            
        with st.form("return_form"):
            return_device = st.selectbox("Chọn thiết bị cần trả", borrowed_devices)
            returner_name = st.text_input("Tên người trả")
            # Nút bấm bắt buộc phải thụt lề ngang bằng với các dòng trên
            submit_return = st.form_submit_button("Xác nhận Trả")
            
            if submit_return:
                if returner_name == "":
                    st.warning("⚠️ Vui lòng nhập tên người trả!")
                elif not return_device:
                    st.warning("⚠️ Không có thiết bị nào đang được mượn!")
                else:
                    cell = sheet_thietbi.find(return_device)
                    sheet_thietbi.update_cell(cell.row, 3, "Sẵn sàng")
                    sheet_thietbi.update_cell(cell.row, 4, "")
                    sheet_thietbi.update_cell(cell.row, 5, "Đã trả")
                    
                    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    sheet_lichsu.append_row([now, returner_name, "Trả", return_device])
                    
                    st.success(f"✅ Đã ghi nhận trả thiết bị: {return_device}")
                    st.rerun()

# TAB 3: XEM LỊCH SỬ
with tab3:
    st.subheader("Lịch sử Mượn / Trả gần đây")
    history_data = sheet_lichsu.get_all_records()
    if history_data:
        df_history = pd.DataFrame(history_data)
        st.dataframe(df_history.iloc[::-1], use_container_width=True)
    else:
        st.info("Chưa có lịch sử giao dịch nào.")