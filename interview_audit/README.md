# SMA Cross VN30 - Interview Audit Version

Bản này được tách riêng để phục vụ rà soát trước phỏng vấn Quant Researcher TVS.

## Những gì đã sửa

- Không còn mô tả ADX > 25 như tính năng đã triển khai; baseline hiện tại là SMA10/50 thuần.
- Tín hiệu dùng Close(t), nhưng lệnh chỉ thực thi từ Open(t+1), tránh same-close execution.
- Kết quả được gọi đúng phạm vi: fixed universe 30 mã lưu trong repository, không tự nhận là historical point-in-time VN30.
- Có kịch bản transaction cost/slippage để kiểm tra net performance.
- Max Drawdown được tính trên đường NAV/equity theo peak-to-trough.
- NAV dùng một accounting convention thống nhất, compounding theo chuỗi giao dịch.
- Có CAGR, volatility, Sharpe (Rf=0 trong bản audit), Win rate, best/worst trade và Buy & Hold benchmark.
- Có parameter sensitivity để xem vùng tham số; không dùng bảng này để tuyên bố bộ tham số tối ưu.
- Không tự nhận OOS/forward/live. Dữ liệu 2020-2025 đã từng được quan sát trong project cũ nên không thể gọi là clean untouched OOS.

## Chạy lại

Từ root repository:

```bash
python -m pip install -r interview_audit/requirements.txt
python interview_audit/run_research_audit.py
streamlit run interview_audit/app_dashboard_revised.py
```

## Lưu ý quan trọng

Kịch bản cost mặc định chỉ là giả định minh họa:
- commission 15 bps mỗi chiều
- slippage 5 bps mỗi chiều
- sell tax 10 bps

Hãy thay đổi theo dữ liệu execution/biểu phí thực tế nếu dùng cho research chính thức.

Trạng thái corporate-action adjustment của dữ liệu giá trong repository chưa được kiểm chứng độc lập. Vì vậy đây vẫn là một limitation cần nói rõ.
