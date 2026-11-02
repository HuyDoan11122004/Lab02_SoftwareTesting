# Ghi chú evidence E01–E10

Tài liệu này hướng dẫn vị trí cần chụp và nội dung phải diễn giải, không chứa ảnh chụp giả. Theo yêu cầu bổ sung, `STLab02_Report.tex` và bản PDF đen trắng đã được soạn tại thư mục Lab2, đủ12 mục theo Requirement §8; metadata sinh viên/lớp/GitHub để điền sau. Báo cáo nhúng code, console, bảng và biểu đồ từ artifact thật; ảnh chụp UI và E10 GitHub vẫn chưa đầy đủ. Execution hiện tại52 case =43 PASS+9 FAIL+0 BLOCKED;9 FAIL đã recheck trên fixture mới. Lệnh chạy chính còn tự kiểm31 regression của runner và ba thứ tự thực thi, với104/104 đối chiếu bổ sung khớp; run_log.txt ghi console có timestamp, các nhóm kết quả trình bày riêng.

| Evidence | File/hàm/output cần chụp | Điều chứng minh (2–3 câu) |
|---|---|---|
| E01 — Cấu trúc source | Danh sách stlab02_submission: ecommerce_app.py, test_runner.py, test_cases.csv, traceability_matrix.csv, requirements_analysis.md, gradio_dashboard.py, docs/, reports/ và run_log.txt; STLab02_Report.tex/.pdf tại Lab2 | Chứng minh source sản phẩm tách khỏi runner/data/analysis và báo cáo LaTeX/PDF nằm ở thư mục Lab2 theo yêu cầu bổ sung. Chưa tạo notebook/README/repository; không dùng ảnh cấu trúc giả để thay minh chứng chưa có. |
| E02 — REQ/COND/TS/TC/trace | requirements_analysis.md phần7 REQ; test_cases.csv; traceability_matrix.csv cột run_id/execution_status; reports/summary.json | Chứng minh7 REQ thuộc6 module,15 condition,19 scenario,52 case nối tới RUN và không có orphan. Lấy một chuỗi thật như REQ-09→COND-SHP-INNER→TS-SHP-INNER→TC-SHP-002 để giải thích cách trace impact, phân biệt coverage với PASS rate. |
| E03 — Fixture isolation | test_runner.py::fixture, execute_case, snapshot, run_order_checks, compare_order_results; reports/runner_validation.csv test_22; reports/order_independence.csv/.json và order_execution.csv | Mỗi case tạo Checkout/Customer/Cart/Catalog mới; kiểm mutation hai fixture đồng thời xác nhận state không dùng chung. Ba thứ tự original/reverse/shuffled(seed20261102) cho cùng status/actual/toàn bộ state trước/sau ở52 TC,104/104 đối chiếu bổ sung khớp; đây là evidence thực nghiệm về isolation, không chứng minh mọi hoán vị. |
| E04 — Reader/parse/schema | test_runner.py::read_cases, strict_json, validate_row, run_runner_checks; reports/runner_validation.txt/.csv test_02–13 | pandas đọc CSV dạng text để giữ chính xác dữ liệu JSON; validation phân biệt cấu trúc input sai với quantity sai có chủ đích cần đưa vào app. Regression tự động dùng dữ liệu hỏng trong bộ nhớ/CSV tạm để xác nhận BLOCKED trước fixture/dispatch, giữ record khi CSV lỗi và không skip dòng trắng. |
| E05 — Dispatcher/compare | test_runner.py::dispatch, compare, verify; dòng TC-SHP-002 và TC-PAY-005 trong Execution | Chỉ ra từ operation tới hàm thật: Cart.add/subtotal, Promotions.discount, Shipping.calculate, Payments.collect, Checkout.place và Inventory.reserve. compare kiểm type/scalar/list và projection dict; verify kiểm return, exception và state/order ID, tránh hard-code actual thành expected. |
| E06 — try/except và status | test_runner.py::execute_case và verify; TC-CART-001 PASS với expected exception; TC-CART-005 FAIL thiếu exception; runner_validation.csv test_14–21 | Exception đúng class/message vẫn phải kiểm state; test_15–19 mô phỏng sai/thiếu exception và state sai qua dispatcher của runner, xác nhận execution_status=FAIL và traceback khi cần. Mock được tự khôi phục, không sửa ứng dụng; dữ liệu/setup lỗi là BLOCKED và finally ghi ms cho mọi nhánh. |
| E07 — Output đủ suite/timestamp | run_log.txt từ RUN qua RUNNER CHECKS, RECHECK, ORDER tới TOTAL/Verification; reports/test_execution.csv và runner_validation.csv | Chứng minh52 dòng nghiệp vụ được xử lý,43 PASS+9 FAIL+0 BLOCKED,9 FAIL tái hiện;31/31 kiểm runner và ba lượt ORDER được báo riêng. Đây là console Python local múi giờ+07:00, có hash expected/app và verification_complete; không gọi156 lượt của ba thứ tự là156 case duy nhất. |
| E08 — Report/bảng/chart | reports/test_report.xlsx các sheet Execution, Traceability, Summary, Defects; reports/test_dashboard.html; reports/summary.json; reports/order_independence.json | Summary nghiệp vụ vẫn43 PASS/9 FAIL/0 BLOCKED, pass rate82.69% trên52 dòng. HTML/JSON thêm phần31 kiểm runner và bảng ba thứ tự với seed, số khớp và link raw evidence; Gradio tiếp tục đọc execution chính, chỉ kiểm build/callback, không mở share/server. |
| E09 — FAIL/root cause/recheck | docs/defect_reports.md; reports/failure_rechecks.csv; Execution TC-PAY-006/TC-SAFE-002/TC-CART-005; ecommerce_app.py::Cart.add/Checkout.place/Payments.collect | Chụp expected/actual/error cùng stock trước/sau cho mỗi nhóm nguyên nhân, nối TC/REQ/COND/TS và RUN để chứng minh tái hiện thay vì gán mọi FAIL là bug. DEF-001 còn cần BA xác nhận bool, DEF-002 thiếu rollback và DEF-003 validate method muộn; suspect Promotions≤ chỉ là đối chiếu tĩnh ngoài suite đã chọn. |
| E10 — GitHub/README | Chưa có minh chứng; URL GitHub là ô điền trong STLab02_Report.tex/.pdf; hướng dẫn chạy hiện có tại requirements_analysis.md và run_log.txt | Requirement PDF yêu cầu ảnh repo/README nhưng chưa tạo hoặc xác minh repository; báo cáo ghi rõ trạng thái chưa hoàn tất. Cần bổ sung README, URL và ảnh repository truy cập được trước nộp chính thức; hướng dẫn chạy local không được xem là đã đáp ứng E10. |

## Reporter và phép tính

test_runner.py::summarize dùng executed=PASS+FAIL và assert executed+BLOCKED bằng số dòng CSV; pass rate=PASS/total, bao gồm BLOCKED trong mẫu số. `data_complete` đòi không blocked/không thiếu; `all_passed` đòi thêm FAIL=0, vì hoàn tất execution không đồng nghĩa hệ thống không lỗi. Traceability coverage ghi7/7 REQ đã thực thi,52/52 mapping,15 condition/19 scenario,orphans=[]; đây là độ phủ thiết kế đã chọn, không phải tất cả16 REQ.

test_runner.py::export_reports không ghi lại test_cases.csv, chỉ xuất actual sang reports và cập nhật RUN/status của matrix. Defects sheet có một dòng mỗi failed case nối Defect ID, còn docs/defect_reports.md nhóm theo ba nguyên nhân gốc để không đếm trùng defect. reports/failure_rechecks.csv lưu đủ expected/actual/state/ms cho recheck, không thay execution chính.

run_runner_checks xuất31 dòng riêng vào runner_validation.csv; PASS ở đây nghĩa công cụ đã xử lý dữ liệu hỏng/failure giả lập đúng, không phải cộng thêm PASS nghiệp vụ. run_order_checks tái dùng lượt gốc rồi chạy reverse/shuffled mới, lưu156 lượt trong order_execution.csv; bảng đối chiếu phát hiện cả ID trùng/thiếu/thừa, BLOCKED và sai state/actual dù status giống nhau. Dùng actual gốc để kiểm tính nhất quán giữa thứ tự không thay acceptance oracle; verification_complete/exit2 chặn xác nhận đầy đủ khi một trong hai bộ kiểm không đạt.

## Kiểm tra bổ sung và giới hạn

reports/runner_validation.txt/.csv được tái tạo tự động qua unittest trong test_runner.py, gồm cả ba snippet Code Interview ở test_30 và hash ở test_31. Kiểm import/build/callback Gradio và đối chiếu workbook là bước QA riêng khi bàn giao, không được nhận là một phần31 kiểm tự động. Mọi dữ liệu hỏng chỉ ở bộ nhớ hoặc thư mục tạm dưới reports; không sửa expected gốc, không tăng số52 case nghiệp vụ.

Đã kiểm thuộc tính/order/stock/payment/voucher trong phạm vi các operation được chọn; không có concurrency, gateway thật, network failure, policy chốt giá đã được BA duyệt hoặc regression sau fix production. Các case tương lai trong Part3 được đánh dấu rõ chưa thực thi. Báo cáo LaTeX/PDF hiện đã có; các ô metadata, ảnh chụp UI, README và E10 GitHub còn cần bổ sung, được ghi rõ trong phần Self-review.

## Chèn ảnh từ thư mục photos

Đặt `photos/` cùng cấp với `STLab02_Report.tex` tại thư mục Lab2. Mục 7.5 của báo cáo có 12 khung chờ: E01–E08 mỗi mục một ảnh, E09 có ba ảnh theo ba nhóm defect, E10 một ảnh. LaTeX tự thay khung chờ bằng ảnh khi tìm thấy file; không có ảnh vẫn biên dịch được, khung chờ không được tính là evidence đã hoàn tất.

Tên file mặc định: `E01.png`, `E02.png`, …, `E08.png`, `E09_DEF001.png`, `E09_DEF002.png`, `E09_DEF003.png`, `E10.png`. Có thể dùng đuôi `.jpg`, `.jpeg`, `.pdf` hoặc `.PNG`/`.JPG`/`.JPEG` với cùng tên gốc. Chụp màn hình thật theo hướng dẫn E01–E10 phía trên; không đặt ảnh QA hoặc ảnh minh họa vào các vị trí minh chứng thực thi.

Muốn đổi tên hoặc thêm ảnh, sửa/thêm lệnh ở mục 7.5 của file LaTeX:

```latex
\EvidencePhoto[8cm]{ten_anh}{Chú thích ảnh}{Giải thích điều ảnh chứng minh.}
```

Ví dụ trên tìm `photos/ten_anh.png` hoặc các đuôi được hỗ trợ; `[8cm]` là chiều cao tối đa, mặc định 6cm và giữ nguyên tỉ lệ. Biên dịch bằng XeLaTeX từ thư mục Lab2 rồi kiểm lại chữ trong ảnh, chú thích, metadata và Self-review trước khi nộp.
