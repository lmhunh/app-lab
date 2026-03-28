import streamlit as st
import pandas as pd
import gspread
from datetime import datetime
import json # Đảm bảo có thư viện này để xử lý dữ liệu

def connect_to_gsheets():
    try:
        # Lấy dữ liệu từ "Két sắt" Secrets
        creds_dict = dict(st.secrets["my_creds"])
        
        # 1. Loại bỏ khoảng trắng thừa ở đầu/cuối
        pk = creds_dict["private_key"].strip()
        
        # 2. Xử lý ký tự xuống dòng (Trị dứt điểm lỗi JWT và PEM)
        creds_dict["private_key"] = pk.replace("\\n", "\n")
        
        return gspread.service_account_from_dict(creds_dict)
    except Exception as e:
        st.error(f"❌ Lỗi xử lý khóa bí mật: {e}")
        st.stop()
# --- 1. CẤU HÌNH TRANG ---
st.set_page_config(page_title="Hệ thống Quản lý Lab", layout="wide")

# --- 2. DÁN ĐOẠN MÃ KẾT NỐI VÀO ĐÂY ---
def connect_to_gsheets():
    # Kiểm tra xem "my_creds" đã được dán vào ô Secrets chưa
    if "my_creds" in st.secrets:
        creds_dict = dict(st.secrets["my_creds"])
        # Vá lỗi ký tự xuống dòng quan trọng để tránh lỗi JWT Signature
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        return gspread.service_account_from_dict(creds_dict)
    else:
        st.error("❌ Không tìm thấy 'my_creds' trong Secrets!")
        st.stop()

# --- 3. KHỞI TẠO KẾT NỐI (GỌI HÀM VỪA DÁN) ---
try:
    gc = connect_to_gsheets()
    sh = gc.open("Quan_ly_lab") # Tên file Sheets trên Drive
    sheet_thietbi = sh.worksheet("ThietBi")
    sheet_lichsu = sh.worksheet("LichSu")
    sheet_taikhoan = sh.worksheet("TaiKhoan")
except Exception as e:
    st.error(f"❌ Lỗi kết nối dữ liệu: {e}")
    st.stop()

# --- 4. CÁC PHẦN TIẾP THEO (LOGIN, GIAO DIỆN...) ---
# (Phần code hiển thị danh sách thiết bị nghiên cứu ZnO, Cu2O của bạn...)
# --- LOGIC ĐĂNG NHẬP & QUẢN LÝ ---
# (Sử dụng session_state để quản lý trạng thái đăng nhập như bạn đã viết)
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