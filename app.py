import streamlit as st
import pandas as pd
import gspread
import json
from datetime import datetime

# --- 1. CẤU HÌNH TRANG ---
st.set_page_config(page_title="Hệ thống Quản lý Lab", layout="wide")

# --- 2. KẾT NỐI DỮ LIỆU ---
def connect_to_gsheets():
    # THAY "my_creds" THÀNH TÊN BẠN ĐẶT TRONG SECRETS (VÍ DỤ: LAB_KEY)
    secret_name = "my_creds" 
    
    if secret_name in st.secrets:
        try:
            creds_data = st.secrets[secret_name]
            if isinstance(creds_data, str):
                # Tự sửa lỗi dấu xuống dòng trong mã khóa
                fixed_json = creds_data.replace("\\n", "\n")
                creds_dict = json.loads(fixed_json, strict=False)
            else:
                creds_dict = dict(creds_data)
            
            if "private_key" in creds_dict:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
                
            return gspread.service_account_from_dict(creds_dict)
        except Exception as e:
            st.error(f"❌ Lỗi xử lý Secrets: {e}")
            st.stop()
    else:
        st.error(f"❌ Không tìm thấy tên '{secret_name}' trong mục Secrets của Streamlit!")
        st.stop()

# Khởi tạo kết nối
try:
    gc = connect_to_gsheets()
    # HÃY ĐẢM BẢO TÊN FILE SHEETS DƯỚI ĐÂY ĐÚNG 100% VỚI GOOGLE DRIVE
    sh = gc.open("Quan_ly_lab") 
    sheet_thietbi = sh.worksheet("ThietBi")
    sheet_lichsu = sh.worksheet("LichSu")
    sheet_taikhoan = sh.worksheet("TaiKhoan")
except Exception as e:
    st.error(f"❌ Lỗi kết nối Google Sheets: {e}")
    st.info("Mẹo: Kiểm tra lại tên File Sheets hoặc quyền chia sẻ của Email Bot.")
    st.stop()

# --- 3. QUẢN LÝ ĐĂNG NHẬP ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['ho_ten'] = ""

if not st.session_state['logged_in']:
    st.title("🔐 Đăng nhập Hệ thống Lab")
    with st.form("login"):
        u = st.text_input("Tài khoản")
        p = st.text_input("Mật khẩu", type="password")
        if st.form_submit_button("Đăng nhập"):
            df_tk = pd.DataFrame(sheet_taikhoan.get_all_records())
            match = df_tk[(df_tk['TaiKhoan'].astype(str) == str(u)) & (df_tk['MatKhau'].astype(str) == str(p))]
            if not match.empty:
                st.session_state['logged_in'] = True
                st.session_state['ho_ten'] = match.iloc[0]['HoTen']
                st.rerun()
            else: st.error("❌ Sai tài khoản hoặc mật khẩu!")
else:
    # GIAO DIỆN CHÍNH
    col_t, col_l = st.columns([8, 2])
    with col_t: st.title(f"🧪 Chào mừng {st.session_state['ho_ten']}!")
    with col_l:
        if st.button("🚪 Đăng xuất"):
            st.session_state['logged_in'] = False
            st.rerun()
    
    tab1, tab2, tab3 = st.tabs(["📊 Danh sách", "🔄 Mượn/Trả", "🕒 Lịch sử"])
    
    with tab1:
        df = pd.DataFrame(sheet_thietbi.get_all_records())
        st.dataframe(df, use_container_width=True, hide_index=True)

    with tab2:
        df = pd.DataFrame(sheet_thietbi.get_all_records())
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Đăng ký Mượn")
            ready = df[df['Trạng thái'] == 'Sẵn sàng']['Tên'].tolist() if not df.empty else []
            with st.form("form_muon"):
                d = st.selectbox("Chọn thiết bị", ready)
                n = st.text_input("Ghi chú")
                if st.form_submit_button("Xác nhận Mượn"):
                    if d:
                        row = sheet_thietbi.find(d).row
                        sheet_thietbi.update_cell(row, 3, "Đang mượn")
                        sheet_thietbi.update_cell(row, 4, st.session_state['ho_ten'])
                        sheet_thietbi.update_cell(row, 5, n)
                        sheet_lichsu.append_row([datetime.now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], "Mượn", d])
                        st.success(f"Đã mượn {d}"); st.rerun()
        with c2:
            st.subheader("Đăng ký Trả")
            borrowed = df[df['Trạng thái'] == 'Đang mượn']['Tên'].tolist() if not df.empty else []
            with st.form("form_tra"):
                d_t = st.selectbox("Thiết bị trả", borrowed)
                if st.form_submit_button("Xác nhận Trả"):
                    if d_t:
                        row = sheet_thietbi.find(d_t).row
                        sheet_thietbi.update_cell(row, 3, "Sẵn sàng")
                        sheet_thietbi.update_cell(row, 4, "")
                        sheet_thietbi.update_cell(row, 5, "Đã trả")
                        sheet_lichsu.append_row([datetime.now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state['ho_ten'], "Trả", d_t])
                        st.success(f"Đã trả {d_t}"); st.rerun()

    with tab3:
        st.subheader("Lịch sử gần đây")
        history = pd.DataFrame(sheet_lichsu.get_all_records())
        if not history.empty: st.dataframe(history.iloc[::-1], use_container_width=True, hide_index=True)