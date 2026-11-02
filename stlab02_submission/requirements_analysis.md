# Phân tích yêu cầu và thiết kế oracle

## Nguồn, phạm vi và quy trình

Đã đọc toàn bộ `STLab02 - Test Case Execution (Instruction).docx.pdf` (11 trang) và `STLab02 - Test Case Execution (Requirement).docx.pdf` (8 trang). Nguồn oracle là Requirement §1.1, §1.3 và Instruction §1.2; mô tả module ở Instruction §1.1, §2.3–2.5 bổ sung cách hiểu. Mã ứng dụng §2.6 chỉ cung cấp giao diện, tên field và từ vựng exception để dispatcher gọi đúng; kết quả trả về hiện tại không quyết định expected. Với error token không được acceptance criteria quy định nguyên văn, dùng quy ước giao diện `ValueError` + token tương ứng; thay đổi thông điệp cần BA xác nhận, không tự thay expected theo actual.

Chọn đúng REQ-02, REQ-03, REQ-05, REQ-09, REQ-10, REQ-15, REQ-16, thuộc sáu module Cart, Pricing, Promotion, Shipping, Payment và Inventory. Không chọn REQ-06/08/11 làm requirement hay tạo case riêng cho chúng. Kiểm tra stock sau declined là assertion bổ sung về an toàn giao dịch theo Instruction §2.5 và yêu cầu của người dùng, đi kèm REQ-10/05; không cộng thêm requirement coverage. Voucher state sau thành công/thất bại dùng mô tả lifecycle chung, không tính thêm REQ-07.

52 ca được thiết kế trước lần thực thi đầu tiên. SHA256 toàn bộ `test_cases.csv` đã khóa: `78588938e04be88dc600b6949fc62a2814ff8689daa2cfc131ee31f3cda1df69`. Runner kiểm hash trước/sau, không có nhánh ghi CSV gốc. Mọi dòng execution_status và actual_result trong dữ liệu gốc đều rỗng; chỉ report chứa actual. Không điều chỉnh expected sau khi chạy.

Ứng dụng được trích nguyên mã §2.6, bỏ magic `%%writefile` và header/footer PDF; nối dòng `payment_method:str` bị ngắt bởi chiều rộng trang vào khai báo Order. Không sửa logic, kể cả bug có chủ đích. SHA256 bất biến: `51a5bd940307df21a67352b69551c041dbbfb542cfb8fe26d29b8d09ae221b03`.

## REQ-02 — Cart

- Actor: người mua và API nhận quantity.
- Rule: quantity là số nguyên dương; cùng SKU cộng dồn thành một line. Không mất line cũ khi thêm dữ liệu không hợp lệ.
- Precondition: catalog mới với SKU active; giỏ rỗng hoặc đã có A; có ca bổ sung C inactive để bảo vệ setup của luồng thêm giỏ.
- Input: `Cart.add(sku, quantity)`; A/B/C; quantity `0`, `-1`, `1`, `1.5`, `true`, `false`, `"1"`; chuỗi A2 rồi A3, A1/B1/A1.
- Output: None khi hợp lệ, line/quantity chính xác; ValueError INVALID_QUANTITY nếu không hợp lệ, state không đổi. SKU inactive là PRODUCT_UNAVAILABLE, được trace như tiền điều kiện tích hợp, không cộng REQ-01 vào coverage.
- Risk: bool là subclass của int trong Python; float/string bị ép kiểu âm thầm; duplicate line gây tính tiền hoặc reserve sai; nhập invalid làm tăng line cũ.
- Clarification: bool có phải quantity không? Oracle chọn kiểu integer nghiệp vụ nghiêm ngặt: bool bị từ chối dù Python coi True là int. DEF liên quan phải ghi là cần BA xác nhận. Chưa có giới hạn qty tối đa hay yêu cầu kiểm stock ngay lúc add; không tự đặt giới hạn 20 ở Cart.
- Conditions: COND-CART-TYPE (kiểu/biên), COND-CART-MERGE (cộng dồn/state).
- Scenarios: TS-CART-QUANTITY, TS-CART-MERGE, TS-CART-REJECT. Cases: TC-CART-001–011.

## REQ-03 — Pricing

- Actor: người mua và checkout sử dụng subtotal.
- Rule: subtotal bằng tổng giá × số lượng, kết quả Decimal chính xác, không dùng float.
- Precondition: giỏ được setup bằng Cart.add; giá Decimal xác định trước thao tác. Không chạy test chốt giá khi thay đổi giữa add và checkout vì chưa có oracle được duyệt.
- Input/output: A2/B1/C1 → Decimal 850000; rỗng → Decimal 0; A0.1×3+B0.2×1 → Decimal 0.5; B1 → 300000; giá A0×1 → 0. Không round subtotal khi criterion chỉ quy định phép cộng; giá lẻ dùng để kiểm biểu diễn Decimal.
- Risk: float sinh 0.5000000000000001; số 0 bị hiểu là thiếu giá; state bị đổi bởi phép đọc.
- Clarification: giá chốt ở add hay checkout; có cho phép giá lẻ VND/giá 0/giá âm không; thời điểm rounding? Bộ test hiện tại dùng giá 0 như biên số học của Pricing, không kết luận Catalog cho phép bán hàng miễn phí. Không áp đặt chính sách snapshot giá mới.
- Conditions: COND-PRI-SUM, COND-PRI-ZERO. Scenarios: TS-PRI-SUM, TS-PRI-EMPTY, TS-PRI-DECIMAL. Cases: TC-PRI-001–005.

## REQ-05 — Promotion

- Actor: khách đăng nhập muốn dùng SAVE10.
- Rule: chỉ khách authenticated và chưa dùng mã mới đủ quyền; phép tính discount không tự tiêu hao voucher. Order thành công mới cập nhật used_codes theo lifecycle mô tả chung.
- Precondition: subtotal 600000 để tránh trộn bài mẫu threshold/cap; user mới/chưa đăng nhập/đã dùng; fixture riêng từng ca.
- Input/output: eligible → Decimal 60000 theo công thức SAVE10 đã mô tả, guest → LOGIN_REQUIRED, used → VOUCHER_USED. Luồng Cart → Promotion kiểm quantity 0/-1/1/float/bool/string trước khi tính; đặt giá A600000 trước thao tác để quantity 1 đủ điều kiện. Quantity invalid không được bỏ qua chỉ vì có voucher.
- Risk: guest hưởng ưu đãi, dùng lại mã, đánh dấu mã khi chỉ preview hoặc payment declined; rollback kho sai làm retry gây hao hụt.
- Clarification: dùng mã tính theo account hay order; voucher hết hạn/hoa thường; định nghĩa bool giống REQ-02. Các error token là hợp đồng test; không đặt rule mới cho token không được mô tả.
- Conditions: COND-PRO-ELIGIBLE, COND-PRO-REJECT, COND-PRO-INPUT. Scenarios: TS-PRO-ELIGIBILITY, TS-PRO-USED, TS-PRO-QUANTITY, TS-PRO-CHECKOUT, TS-PRO-RETRY-AFTER-DECLINE. Cases: TC-PRO-001–012.

## REQ-09 — Shipping

- Actor: người mua lựa chọn khu vực.
- Rule: inner: subtotal ≥500000 phí 0, dưới ngưỡng phí 30000; outer luôn 50000. Instruction §2.4 nói dùng subtotal trước giảm.
- Precondition: input subtotal Decimal, area đúng `inner`/`outer`; phép tính không tác động kho/đơn/charge/voucher.
- Input/output: inner 499999/500000/500001 → 30000/0/0; outer cùng ba số → 50000/50000/50000.
- Risk: nhầm > với ≥; dùng total sau giảm; miễn ngoại thành nhầm; thay đổi ngưỡng không đồng bộ test/report.
- Clarification: chuẩn hóa địa chỉ và mã khu vực; phí cho giỏ rỗng hoặc tổng âm chưa được chọn kiểm; thuế và voucher ship chưa được mô tả.
- Conditions: COND-SHP-INNER, COND-SHP-OUTER. Scenarios: TS-SHP-INNER, TS-SHP-OUTER. Cases: TC-SHP-001–006.

## REQ-10 — Payment

- Actor: khách thanh toán COD/ONLINE và cổng thanh toán giả lập approved.
- Rule: COD → PENDING_COD; ONLINE approved → PAID, có đúng một charge bằng total; declined → PAYMENT_DECLINED và không có order/charge. Kiểm thêm stock không đổi khi giao dịch thất bại theo Instruction §2.5; phân biệt assertion cốt lõi REQ-10 với invariant giao dịch này trong defect.
- Precondition: số tiền Decimal, method đúng case, kho đủ; tests tích hợp kiểm đầy đủ order customer_id, lines, total, status, discount, shipping, payment_method và ID không rỗng/đã lưu.
- Input/output: collect 230000, COD approved=False vẫn pending; ONLINE true/false; checkout A2/B1/C1 subtotal 850000 thành công giảm kho A2/B1/C1; declined không tạo đơn. B1 declined kiểm thêm dưới ngưỡng với shipping 30000 (total 330000).
- Risk: pending bị gắn PAID; charge dù declined; tạo order trước approval; trừ kho rồi không hoàn khi bị từ chối.
- Clarification: approved có phải bool strict; tiền charge có bao gồm phí; refund/timeout chưa mô phỏng. Không kiểm retry idempotency vì REQ-11 ngoài phạm vi.
- Conditions: COND-PAY-COD, COND-PAY-ONLINE. Scenarios: TS-PAY-COLLECT, TS-PAY-CHECKOUT. Cases: TC-PAY-001–007.

## REQ-15 — Inventory Atomicity

- Actor: checkout và bộ phận quản lý kho.
- Rule: nếu bất cứ SKU nào thiếu, reject toàn bộ, không trừ SKU còn đủ; đủ toàn bộ mới trừ mỗi SKU đúng quantity.
- Precondition: A20/B15/C12, giỏ A2+B100 hoặc đảo thứ tự; nhiều SKU đủ; stock bằng đúng demand; SKU C stock 0 ở cuối.
- Input/output: reserve/checkout thiếu B → OUT_OF_STOCK, mọi stock giữ nguyên, không order/charge; đủ A2/B1/C1 → stock18/14/11; stock đúng2/1/1 →0/0/0.
- Risk: vòng lặp vừa kiểm vừa trừ dẫn đến trừ A trước khi thấy B thiếu; phụ thuộc thứ tự line; so sánh ≤ loại sai trường hợp vừa đủ.
- Clarification: atomicity giữa request đồng thời, transaction/lock ngoài mô hình bộ nhớ; stock trừ khi reserve hay khi giao hàng; duplicate raw CartLine có thể bypass Cart.add chưa được đưa vào bộ test.
- Conditions: COND-INV-ENOUGH, COND-INV-REJECT. Scenarios: TS-INV-RESERVE, TS-INV-CHECKOUT. Cases: TC-INV-001–006.

## REQ-16 — Payment Safety

- Actor: API caller gửi payment method.
- Rule: chỉ COD/ONLINE, giá trị khác phải INVALID_PAYMENT_METHOD; rejection không tạo order, charge, tiêu hao voucher hoặc làm giảm kho. Thứ tự validate trước reserve là cách đáp ứng invariant này, không phải yêu cầu phải có một cấu trúc code cụ thể.
- Precondition: method WALLET/online/chuỗi rỗng/CRYPTO, giỏ mới đủ kho cho ca checkout để tránh OUT_OF_STOCK che lỗi method.
- Input/output: direct collect và checkout đều raise ValueError với đúng token, mọi state giao dịch không đổi.
- Risk: unsupported method bị phát hiện quá muộn sau reserve; gateway không được hỗ trợ nhưng hàng bị giữ; lower-case được xử lý không thống nhất.
- Clarification: có normalize case/space hay không? Hiện dùng hai giá trị viết hoa đúng tài liệu; chưa có WALLET, không tự thêm phương thức mới.
- Conditions: COND-SAFE-DIRECT, COND-SAFE-CHECKOUT. Scenarios: TS-SAFE-COLLECT, TS-SAFE-CHECKOUT. Cases: TC-SAFE-001–005.

## Traceability, kỹ thuật và cách thực thi

Chuỗi REQ → COND → TS → TC được ghi trong CSV và matrix; RUN thêm sau thực thi, nối bằng test_case_id duy nhất và số dòng CSV (header là dòng 1). 15 condition, 19 scenario đều có case, không có case ngoài 7 REQ đã chọn. Có hơn 10 ca negative/boundary: riêng quantity sai ở Cart/Promotion, sáu biên Shipping và các ca payment/inventory rejection đã vượt mức này.

Oracle gồm `value` (return + state), `exception` (đúng class/message + state dù đã raise), `state` (return + snapshot/state của sequence). Dict expected là phép chiếu field cần kiểm; list kiểm đúng độ dài/thứ tự, scalar so sánh cả kiểu để `True` không bằng `1`. Decimal được assert loại trước khi serialize thành chuỗi exact. Order ID chỉ yêu cầu không rỗng và có trong orders; không đoán thuật toán sinh ID. Các state trước/sau đầy đủ nằm ở report.

Fixture keys: empty; one_a; one_b; 600k; mixed; decimal; unauthenticated; used; inactive; short_b; short_first. `input_json.setup` cho phép override prices, stock, active sau khi xây giỏ. Không dùng shared Checkout/Customer/Cart giữa các case. Một sequence bên trong TC-PRO-012 cố ý dùng cùng đối tượng để kiểm lifecycle; case tiếp theo luôn dựng mới.

Môi trường cần Python 3.10+ và bốn thư viện `pandas openpyxl matplotlib gradio` (cài bằng `python -m pip install pandas openpyxl matplotlib gradio`). Từ thư mục `stlab02_submission`, chạy `python test_runner.py`; runner tự làm sạch đúng reports/ rồi tạo lại toàn bộ CSV/XLSX/HTML/JSON, recheck từng FAIL và ghi nối console có timestamp vào run_log.txt. CLI `python test_runner.py --case TC-SAFE-002` chạy riêng một ca bằng fixture mới, in JSON và ghi log mà không ghi đè report bộ đầy đủ. Chạy `python gradio_dashboard.py` chỉ build giao diện, không launch server.

## Nâng cấp: hồi quy runner và kiểm thứ tự thực thi

Cùng lệnh `python test_runner.py` tự chạy thêm hai bước sau, không cần thư viện mới và không thêm case vào CSV đã khóa:

1. `run_runner_checks()` chạy **31 kiểm tra bằng unittest của thư viện chuẩn**. Các nhóm gồm schema/JSON/ID/operation/fixture; exception đúng, sai class/message, thiếu hoặc ngoài mong đợi; exception đúng nhưng state sai; completeness; fixture isolation; độ nhạy của phép so thứ tự; ba snippet Code Interview và hai SHA256 bất biến. Dữ liệu cố ý hỏng là bản trong bộ nhớ hoặc CSV tạm dưới reports, được xóa sau kiểm; không thay expected gốc. Mock chỉ thay hàm fixture/dispatch của runner trong phạm vi một phép kiểm rồi tự khôi phục; không thay hàm hay file ứng dụng.
2. `run_order_checks()` dùng lần chạy chính làm **original**, chạy mới toàn bộ 52 ca theo **reverse** và **shuffled**, seed cố định **20261102**. Mỗi lượt vẫn dùng fixture mới từng case, giữ nguyên key bằng TC ID và số dòng CSV gốc; không ghi đè execution chính hoặc trace RUN bằng thứ tự bổ sung. So theo TC ID duy nhất, kiểm cả status, actual_result, observed_before và observed_after; JSON được chuẩn hóa thứ tự key nhưng vẫn phân biệt true với1. Timestamp, thời gian chạy, RUN/evidence và traceback không phải dữ liệu nghiệp vụ để so bằng nhau.

Kết quả hiện tại: **31/31 kiểm runner PASS**, cả ba thứ tự đều **43 PASS / 9 FAIL / 0 BLOCKED**; **104/104 đối chiếu ở hai thứ tự bổ sung khớp**, không sai lệch. File raw ghi156 lượt thực thi (52×3, không tính9 recheck riêng hoặc các phép kiểm runner); số case nghiệp vụ duy nhất và mẫu số pass rate vẫn52. Kết quả FAIL ổn định vẫn là FAIL, không biến thành PASS nhờ độ ổn định. Dùng actual của original chỉ làm mốc kiểm tính nhất quán giữa thứ tự, không làm business expected.

| Artifact tự sinh | Nội dung |
|---|---|
| reports/runner_validation.txt | Log unittest và tổng hợp PASS/failure/error/skip |
| reports/runner_validation.csv | 31 dòng check ID/status/ms/timestamp/RUN/error |
| reports/order_execution.csv | 156 lượt thực thi đầy đủ, có order_name/execution_index/shuffle_seed và state |
| reports/order_independence.csv | Đối chiếu từng TC với original, cờ khớp status/actual/before/after và lý do sai lệch |
| reports/order_independence.json | Tổng hợp ba thứ tự, seed, chuỗi TC thực tế, số đối chiếu/sai lệch |
| reports/summary.json và test_dashboard.html | Kết quả nghiệp vụ và hai bộ kiểm bổ sung, trình bày riêng |

`verification_complete` chỉ true nếu execution đủ, mọi FAIL tái hiện, hồi quy runner đạt và ba thứ tự nhất quán. CLI trả **exit2** khi một điều kiện này không đạt; **exit3** khi suite gặp lỗi không xử lý được; **exit0** khi xác minh đầy đủ, kể cả có lỗi sản phẩm đã ghi nhận. Vì vậy exit0 không có nghĩa52 ca đều PASS. Phép thử ba thứ tự là evidence thực nghiệm về isolation, chưa chứng minh tất cả52! hoán vị hoặc concurrency production.

Trong máy thực thi này, `/usr/bin/python3` là Python hệ thống không có thư viện cần thiết; Python 3.12 dùng cho chạy thật là `/Users/dhuy/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python`. Pandas/openpyxl có sẵn; matplotlib/gradio đã được cài theo quyền cho phép. Báo cáo ghi version Python và hash để tái hiện. Theo yêu cầu bổ sung, báo cáo LaTeX/PDF đen trắng được đặt tại thư mục Lab2 dưới tên `STLab02_Report.tex` và `STLab02_Report.pdf`, trình bày đủ12 mục theo Requirement §8. Thông tin sinh viên/lớp/GitHub để người thực hiện điền sau; README, repository và minh chứng truy cập GitHub chưa được tạo/xác minh.

Các mục Part 3 về policy giá mới/ngưỡng 700k là thiết kế dự kiến, chưa thực thi và chưa sửa expected đã khóa. Muốn sửa CSV trong tương lai phải có phê duyệt thay expected, cập nhật lock với evidence thiết kế mới; bản hiện tại không làm bước đó.
