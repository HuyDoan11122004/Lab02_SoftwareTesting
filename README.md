# STLab02 – Test Case Execution

Bài thực hành kiểm thử ứng dụng EduCommerce bằng Python, với dữ liệu test từ CSV và báo cáo tự động.

## Nội dung

- `stlab02_submission/ecommerce_app.py`: ứng dụng được kiểm thử.
- `stlab02_submission/test_runner.py`: đọc dữ liệu, thực thi, kiểm tra kết quả và xuất báo cáo.
- `stlab02_submission/test_cases.csv`, `traceability_matrix.csv`: test case và truy vết REQ → COND → TS → TC.
- `stlab02_submission/docs/`: phân tích lỗi, bài giải và hướng dẫn chụp minh chứng.
- `stlab02_submission/reports/`: kết quả CSV, Excel, HTML, JSON và biểu đồ.
- `STLab02_Report.tex`, `STLab02_Report.pdf`: mã LaTeX và báo cáo PDF; `photos/` chứa ảnh minh chứng.

## Cài đặt và chạy

Yêu cầu Python 3.10 trở lên; bài đã chạy với Python 3.12. Thực hiện tại thư mục Lab2:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install pandas openpyxl matplotlib gradio
python3 stlab02_submission/test_runner.py
```

Mỗi lượt chạy đầy đủ tạo lại thư mục `reports/`, cập nhật traceability và ghi thêm vào `run_log.txt`. Tái hiện riêng một case trên fixture mới, giữ các báo cáo đã lưu:

```bash
python3 stlab02_submission/test_runner.py --case TC-PAY-006
```

## Xem kết quả

Mở [dashboard HTML](stlab02_submission/reports/test_dashboard.html) bằng trình duyệt hoặc [báo cáo Excel](stlab02_submission/reports/test_report.xlsx).

Kết quả đã lưu: **52 case — 43 PASS, 9 FAIL, 0 BLOCKED**, pass rate **82.69%**; phạm vi gồm 7 requirement, 15 condition và 19 scenario. Phần làm thêm gồm **31/31 kiểm tra runner đạt** và kiểm ba thứ tự original/reverse/shuffled, với **104/104 đối chiếu bổ sung khớp**.

Chín FAIL được nhóm thành ba nguyên nhân trong [defect reports](stlab02_submission/docs/defect_reports.md); DEF-001 về quantity kiểu bool còn cần BA xác nhận. Các lần recheck xác nhận tái hiện lỗi, chưa phải kết quả sau sửa lỗi.

## Báo cáo PDF và minh chứng

Điền thông tin sinh viên/GitHub trong `STLab02_Report.tex`, đặt ảnh đúng tên theo [hướng dẫn minh chứng](stlab02_submission/docs/evidence_notes.md), rồi biên dịch bằng XeLaTeX hai lần:

```bash
xelatex STLab02_Report.tex
xelatex STLab02_Report.tex
```

