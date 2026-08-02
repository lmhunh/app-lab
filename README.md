# 🔬 Hệ thống Quản lý Thiết bị Lab 109 (Lab Equipment Management System)

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.20+-red.svg)](https://streamlit.io/)
[![Live App](https://img.shields.io/badge/Live-Demo-success.svg)](https://[tên-app-của-bạn].streamlit.app/)

Ứng dụng web được xây dựng bằng Python và Streamlit nhằm số hóa quy trình quản lý, mượn/trả máy móc tại phòng thí nghiệm Lab 109. Dự án giúp giải quyết triệt để tình trạng trùng lịch sử dụng thiết bị và loại bỏ hoàn toàn việc ghi chép sổ sách thủ công.

---

## 🚀 Tính năng nổi bật (Key Features)

* **📊 Bảng điều khiển trực quan (Dashboard):** Hiển thị trạng thái thiết bị theo thời gian thực (Sẵn sàng 🟢, Đang mượn 🔴, Bảo trì 🟡).
* **📅 Hệ thống đặt lịch thông minh:** Cho phép thành viên chọn ngày/giờ mượn máy. Tự động kiểm tra và ngăn chặn nếu phát hiện trùng lặp thời gian với người khác.
* **🔐 Phân quyền người dùng (Role-based Access):** Phân tách rõ ràng giữa quyền Quản trị viên (Admin - được quyền sửa/xóa thiết bị) và quyền Sinh viên (Member - chỉ được xem và đặt lịch).
* **📱 Thiết kế đáp ứng (Responsive UI):** Giao diện Dark-mode hiện đại, hiển thị tối ưu trên cả màn hình máy tính và thiết bị di động.

---

## 🛠️ Công nghệ sử dụng (Tech Stack)

* **Frontend & Tương tác UI:** Streamlit
* **Xử lý Logic & Backend:** Python
* **Xử lý dữ liệu:** Pandas
* **Cơ sở dữ liệu:** [Ghi rõ công nghệ bạn đang dùng, ví dụ: Firebase Firestore / Google Sheets API]

---

## 💻 Hướng dẫn Cài đặt & Chạy cục bộ (Local Installation)

Để chạy thử ứng dụng này trên máy tính cá nhân của bạn, hãy làm theo các bước sau:

**1. Clone kho lưu trữ về máy:**
```bash
git clone [https://github.com/lmhunh/app-lab.git](https://github.com/lmhunh/app-lab.git)
cd app-lab
