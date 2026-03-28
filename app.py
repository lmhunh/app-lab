import streamlit as st
import pandas as pd
import gspread
from datetime import datetime

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="Hệ thống Quản lý Lab", layout="wide")

# --- KẾT NỐI GOOGLE SHEETS ---
# Dùng file credentials.json đang để cùng thư mục để đăng nhập
gc = gspread.service_account(filename='credentials.json')

# Mở file Google Sheets (Thay 'Quản lý Lab' bằng tên chính xác file của bạn)
try:
    sh = gc.open("Quan_ly_lab")
    sheet_thietbi = sh.worksheet("ThietBi")
    sheet_lichsu = sh.worksheet("LichSu")
except Exception as e:
    st.error("❌ Không thể kết nối với Google Sheets. Vui lòng kiểm tra lại file credentials.json và quyền chia sẻ (Share) của file Sheets.")
    st.stop()

# --- HÀM TẢI DỮ LIỆU ---
def load_data():
    # Lấy toàn bộ dữ liệu từ sheet Thiết bị
    data = sheet_thietbi.get_all_records()
    return pd.DataFrame(data)

# --- GIAO DIỆN CHÍNH ---
st.title("🧪 Phần mềm Quản lý Thiết bị Lab")

# Lấy dữ liệu hiện tại
df = load_data()

# Tạo 3 tab trên giao diện
tab1, tab2, tab3 = st.tabs(["📊 Trạng thái thiết bị", "🔄 Mượn / Trả", "🕒 Lịch sử"])

# TAB 1: HIỂN THỊ TRẠNG THÁI
with tab1:
    st.subheader("Danh sách thiết bị hiện tại")
    # Tùy chỉnh màu sắc dựa trên trạng thái
    def color_status(val):
        color = 'red' if val == 'Hỏng' else ('orange' if val == 'Đang mượn' else 'green')
        return f'color: {color}'
    
    # Kiểm tra nếu bảng có dữ liệu thì mới hiển thị
    if not df.empty:
        st.dataframe(df.style.map(color_status, subset=['Trạng thái']), use_container_width=True)
    else:
        st.info("Chưa có dữ liệu thiết bị. Bạn hãy thêm vào Google Sheets nhé!")

# TAB 2: CHỨC NĂNG MƯỢN TRẢ
with tab2:
    col1, col2 = st.columns(2)
    
    # --- FORM MƯỢN THIẾT BỊ ---
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
            submit_borrow = st.form_submit_button("Xác nhận Mượn")
            
            if submit_borrow:
                if borrower_name == "":
                    st.warning("⚠️ Vui lòng nhập tên người mượn!")
                elif not selected_device:
                    st.warning("⚠️ Không có thiết bị nào đang sẵn sàng!")
                else:
                    # 1. Cập nhật Sheet ThietBi
                    cell = sheet_thietbi.find(selected_device)
                    sheet_thietbi.update_cell(cell.row, 3, "Đang mượn") 
                    sheet_thietbi.update_cell(cell.row, 4, borrower_name) 
                    sheet_thietbi.update_cell(cell.row, 5, note) 
                    
                    # 2. Ghi log vào Sheet LichSu
                    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    sheet_lichsu.append_row([now, borrower_name, "Mượn", selected_device])
                    
                    st.success(f"✅ Đã ghi nhận: {borrower_name} mượn {selected_device}")
                    st.rerun() 
                    
    # --- FORM TRẢ THIẾT BỊ ---
    with col2:
        st.subheader("Đăng ký Trả")
        if not df.empty and 'Trạng thái' in df.columns:
            borrowed_devices = df[df['Trạng thái'] == 'Đang mượn']['Tên'].tolist()
        else:
            borrowed_devices = []
            
        with st.form("return_form"):
            return_device = st.selectbox("Chọn thiết bị cần trả", borrowed_devices)
            returner_name = st.text_input("Tên người trả")
            submit_return = st.form_submit_button("Xác nhận Trả")
            
            if submit_return:
                if returner_name == "":
                    st.warning("⚠️ Vui lòng nhập tên người trả!")
                elif not return_device:
                    st.warning("⚠️ Không có thiết bị nào đang được mượn!")
                else:
                    # 1. Cập nhật lại Sheet ThietBi
                    cell = sheet_thietbi.find(return_device)
                    sheet_thietbi.update_cell(cell.row, 3, "Sẵn sàng")
                    sheet_thietbi.update_cell(cell.row, 4, "")
                    sheet_thietbi.update_cell(cell.row, 5, "Đã trả")
                    
                    # 2. Ghi log vào Sheet LichSu
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