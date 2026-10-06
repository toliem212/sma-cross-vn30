# SMA Cross VN30 bằng Python

Dự án phân tích một chiến lược giao dịch theo xu hướng bằng Python, sử dụng tín hiệu giao cắt SMA10/SMA50 trên dữ liệu ngày của 30 mã cổ phiếu.

## Phương pháp

- Tín hiệu mua xuất hiện khi SMA10 cắt lên SMA50.
- Tín hiệu bán xuất hiện khi SMA10 cắt xuống SMA50.
- Tín hiệu được xác nhận theo giá đóng cửa ngày t.
- Giao dịch được mô phỏng tại giá mở cửa của phiên kế tiếp.
- Vốn ban đầu mặc định là 100.000.000 VNĐ cho mỗi mã.
- Phí giao dịch mô phỏng là 0,15% mỗi chiều.
- Trượt giá mô phỏng là 0,05% mỗi chiều.
- Thuế khi bán mô phỏng là 0,10%.

Các chỉ tiêu chính gồm tổng tỷ suất sinh lời, tăng trưởng bình quân năm, mức biến động, hệ số Sharpe, mức sụt giảm tối đa, tỷ lệ giao dịch có lãi và kết quả so sánh với phương án mua và nắm giữ.

## Chạy chương trình

```powershell
python run_backtest.py
python -m streamlit run app_dashboard.py
```

## Cấu trúc chính

- `app_dashboard.py`: giao diện phân tích trên Streamlit.
- `run_backtest.py`: chạy lại kết quả cho 30 mã và phép thử độ nhạy tham số.
- `research_engine.py`: các hàm tính tín hiệu, mô phỏng giao dịch và chỉ tiêu.
- `data/price/`: dữ liệu giá.
- `results/`: kết quả xuất từ mô hình.
