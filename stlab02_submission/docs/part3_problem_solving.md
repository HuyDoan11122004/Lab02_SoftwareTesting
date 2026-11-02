# Phần 3 — Problem Solving

Các case có TC ID dưới đây là dòng thật trong test_cases.csv; evidence thực thi nằm trong reports/test_execution.csv và reports/failure_rechecks.csv, nối bằng ID. Các case `PS-PRICE-*`/`PS-SHIP-*` là thiết kế cho policy tương lai chưa chạy; `PS-ISO-*`/`PS-COMP-*` được kiểm tự động qua bộ hồi quy runner ở mục3.6–3.7. Chúng không được cộng vào52 case nghiệp vụ, không sửa ứng dụng hay expected hiện tại.

## 3.1. Hai SKU, một SKU thiếu tồn kho

**Nguyên nhân/risk.** Nếu kiểm và trừ trong cùng một vòng lặp, A còn đủ sẽ bị trừ trước khi phát hiện B thiếu. Theo REQ-15, A phải giữ nguyên khi toàn bộ đơn bị reject, bất kể thứ tự line; trạng thái orders/charges cũng không thay đổi.

**File/function.** ecommerce_app.py → Inventory.reserve và Checkout.place; test_runner.py → fixture, snapshot, dispatch, verify. **Thay đổi dự kiến:** giữ hai giai đoạn kiểm toàn bộ rồi trừ, dùng transaction/lock nếu sau này có cạnh tranh; không thay đổi gì trong bản ứng dụng của bài này. Chỉ nhìn return hoặc OUT_OF_STOCK chưa chứng minh atomicity.

| Case | Data và thao tác | Expected độc lập |
|---|---|---|
| TC-INV-001 | stock A20/B15/C12; cart A2/B100; reserve(lines) | ValueError OUT_OF_STOCK; stock20/15/12; orders0; charges[]; mã chưa dùng |
| TC-INV-002 | cùng data; Checkout.place(COD) | cùng exception; A không bị trừ; không order/charge |
| TC-INV-003 | đổi line thành B100/A2; reserve | kết quả rejection và state giống TC-INV-001 |
| TC-INV-005 | cart A2/B1/C1, stock2/1/1; reserve | không exception, return None, stock0/0/0 |

**Evidence.** Chụp dispatch nhánh reserve và snapshot trước/sau của bốn dòng này; cặp thứ tự thuận/ngược cho thấy kết quả không phụ thuộc thứ tự. Việc Inventory.reserve kiểm hết rồi mới trừ được xác minh từ source sau khi đối chiếu oracle, không dùng để lập expected.

## 3.2. Voucher chỉ đánh dấu used sau thành công

**Nguyên nhân/risk.** Đánh dấu SAVE10 ngay khi preview hoặc trước approval làm khách mất quyền ưu đãi sau giao dịch thất bại. Sequence cần theo dõi used_codes ở từng bước, orders và charges; nếu used_codes đúng mà stock sai thì phân loại lỗi kho/điều phối, không quy lỗi tiêu hao mã.

**File/function.** ecommerce_app.py → Promotions.discount, Checkout.place, Payments.collect; test_runner.py → dispatch/promotion_sequence, snapshot, verify. **Thay đổi dự kiến:** validate quyền dùng mã trước payment, ghi used_codes cùng commit order thành công, hoàn stock khi payment fail. Không sửa production trong bài này.

| Case | Data và thao tác | Expected |
|---|---|---|
| TC-PRO-011 | user mới, A3=600000, SAVE10, ONLINE approved=False | PAYMENT_DECLINED; used_codes[]; orders0; charges[]; stock A20 |
| TC-PRO-010 | fixture mới cùng giỏ/voucher, COD | discount60000, total540000, pending; used_codes[SAVE10]; orders1; stock A17 |
| TC-PRO-012 | cùng fixture: declined key `TC-PRO-012-decline`, rồi approved key `TC-PRO-012-success` | event1 lỗi, mã chưa dùng và stock A20; event2 PAID total540000, một charge540000; mã dùng một lần, orders1, stock A17 |

**Evidence.** TC-PRO-012 ghi cả return sequence và state sau mỗi event. Nếu chỉ assert used_codes cuối sequence sẽ bỏ sót stock bị trừ hai lần; đối chiếu thêm DEF-002 và recheck từng ca FAIL.

## 3.3. Mã thanh toán lạ

**Nguyên nhân/risk.** Nếu chỉ Payments.collect kiểm method, Checkout.place có thể reserve trước khi thấy WALLET không hỗ trợ. Exception đúng nhưng kho thay đổi là một failure thực sự của rejection an toàn; direct collect có thể PASS trong khi tích hợp FAIL.

**File/function.** ecommerce_app.py → Checkout.place, Inventory.reserve, Payments.collect; test_runner.py → dispatch và verify. **Thay đổi dự kiến:** xác thực auth/cart/method/voucher/area trước mọi mutation; sau đó reserve → collect → commit order, có rollback nếu collect raise. Đề xuất validation method riêng để không gọi collect hai lần và gây charge lặp.

| Case | Data và thao tác | Expected |
|---|---|---|
| TC-SAFE-001 | collect(850000, WALLET, True, key=TC-SAFE-001) | ValueError INVALID_PAYMENT_METHOD; charges[]; orders0; stock20/15/12 |
| TC-SAFE-002 | A2/B1/C1; place(method=WALLET) | đúng exception; stock20/15/12; orders0; charges[]; used_codes[] |
| TC-SAFE-003 | cùng giỏ, method=`online` | rejected theo hai giá trị viết hoa trong hợp đồng; state không đổi |

**Evidence.** So sánh direct và checkout trong Execution cùng error_message/state; source location Checkout.place trước app.payments.collect giải thích DEF-003. Không xem việc có exception là đủ để PASS.

## 3.4. Giá sản phẩm thay đổi

**Nguyên nhân/risk.** REQ-03 quy định công thức Decimal nhưng chưa xác định thời điểm chốt giá. Kết luận dynamic price là bug chỉ từ code sẽ tạo oracle sai. BA/PO cần trả lời: chốt lúc add, xác nhận checkout hay payment; có thông báo/đồng ý lại; voucher và phí ship dựa theo giá nào; giá hết hạn và làm tròn ra sao?

**File/function.** ecommerce_app.py → Product.price, CartLine, Cart.subtotal, Checkout.place; test_runner.py → fixture/setup và dispatch. **Thay đổi dự kiến:** chỉ sau quyết định BA, hoặc thêm unit_price snapshot vào CartLine, hoặc tính lại và yêu cầu xác nhận giá checkout. Cập nhật requirement/condition/scenario/test-data phiên bản mới sau phê duyệt; không sửa expected khóa hiện tại.

| Case dự kiến | Data | Expected theo quyết định cần duyệt |
|---|---|---|
| PS-PRICE-01 | add B1 khi300000, sau đó đổi B350000 trước checkout; inner, COD | nếu snapshot: subtotal300000, ship30000, total330000; nếu dynamic: subtotal350000, ship30000, total380000; phương án nào áp dụng phải được BA xác nhận trước chạy |
| PS-PRICE-02 | add A1+B1 khi200000+300000, đổi B299999 trước checkout | snapshot: subtotal500000, ship0,total500000; dynamic: subtotal499999,ship30000,total529999 |

**Evidence.** Hai case thay đổi giữa hai thời điểm chưa thực thi, trạng thái “chờ oracle”. TC-PRI-003 thực tế dùng giá Decimal đã cố định trong setup; TC-PRI-004 dùng B300000 làm baseline. Evidence hiện có chỉ chứng minh phép cộng với giá xác định, không giải quyết được policy chốt giá.

## 3.5. Cùng SKU nhập hai lần

**Nguyên nhân/risk.** Hai line A riêng hoặc ghi đè 2 thành3 đều vi phạm REQ-02; subtotal/kho sai theo. Kiểm stock lúc Cart.add và giới hạn tối đa chưa được yêu cầu; không tự biến stock20 thành max cart quantity20. Cart.add phải từ chối lần thêm không hợp lệ mà giữ nguyên số lượng cũ.

**File/function.** ecommerce_app.py → Cart.add/subtotal, Inventory.reserve; test_runner.py → dispatch/cart_add và snapshot. **Thay đổi dự kiến:** bảo đảm một line mỗi SKU, validate type/value trước mutation, dùng kiểu int nghiêm ngặt nếu BA duyệt loại bool; kiểm tồn kho nguyên tử khi đặt hàng.

| Case | Data | Expected |
|---|---|---|
| TC-CART-008 | A2 rồi A3 trên giỏ mới, giá A200000 | return None, đúng một line A5; subtotal suy ra1000000; stock vẫn20. Oracle CSV của ca này kiểm lines/state, subtotal1000000 là assertion bổ sung đề xuất |
| TC-CART-009 | A1 rồi B1 rồi A1 | hai line theo thứ tự A2/B1; subtotal suy ra700000; stock chưa đổi |
| TC-CART-011 | fixture đã A1 rồi add A0 | INVALID_QUANTITY, giữ đúng A1 và stock20 |
| TC-CART-005 | giỏ mới add A True | theo giả định integer nghiêm ngặt: INVALID_QUANTITY, không line; phải xác nhận BA trước kết luận defect chính thức |

**Evidence.** observed_before/observed_after và expected lines của TC-CART-008/009/011; chỉ ra riêng assertion subtotal đề xuất chưa nằm trong các ca Cart này. TC-PRI-001/003/004 đang thực thi kiểm subtotal; không tuyên bố ca Cart đã kiểm điều chưa làm.

## 3.6. Data-driven tests bị phụ thuộc nhau

**Nguyên nhân/risk.** Một Checkout/Catalog dùng chung giữ giá/stock/orders/charges/used_codes từ ca trước; reset ở teardown không chắc chạy nếu có exception. Fixture mới trước mỗi case tránh phụ thuộc teardown; copy sâu state chỉ dùng để chụp evidence, không thay thế tạo object mới.

**File/function.** test_runner.py → fixture, execute_case, run_runner_checks, run_order_checks và compare_order_results; ecommerce_app.py chỉ được import và gọi. **Thay đổi đã cài:** mỗi execute_case gọi Checkout(), Customer(), Cart() riêng; setup chỉ tác động catalog mới; recheck FAIL cũng gọi execute_case lại. Lệnh chạy chính tự kiểm original/reverse/shuffled với seed20261102, so theo TC ID và giữ nguyên số dòng dữ liệu gốc.

| Case/cặp kiểm | Data | Expected |
|---|---|---|
| TC-PRI-003 → TC-PRI-004 | ca đầu đổi A0.1/B0.2; ca sau B1 mặc định | first subtotal Decimal0.5; second300000, không phải0.2; ca sau stock20/15/12 |
| TC-INV-005 → fixture mixed mới | first stock2/1/1 rồi reserve hết; second fixture mixed | first stock0/0/0; second trước test là20/15/12, không OUT_OF_STOCK do ca trước |
| PS-ISO-01/02 (kiểm runner) | tạo mixed hai lần, đổi stock/price/used_codes của bộ đầu | identity app/user/cart/catalog khác; bộ sau giữ A20/B300000/used_codes[] |
| PS-ISO-03 (thứ tự đảo) | chạy52 TC theo thứ tự ngược CSV, fixture mới mỗi ca | từng TC có cùng status, actual và toàn bộ state trước/sau như original;43 PASS/9 FAIL/0 BLOCKED |
| PS-ISO-04 (xáo trộn) | random.Random(20261102).shuffle trên danh sách52 dòng | cùng dữ liệu nghiệp vụ như original,52/52 ca khớp; thứ tự tái tạo được theo seed |

**Evidence.** `run_runner_checks` có test_22_fixture_objects_and_state_are_isolated và test_25–29 kiểm độ nhạy của phép so thứ tự; log/CSV của31 phép kiểm được tự sinh mỗi lần chạy. reports/order_execution.csv chứa156 lượt và state; reports/order_independence.csv có104/104 đối chiếu reverse/shuffled khớp; JSON ghi seed và chuỗi TC thực tế. Execution chính vẫn52 dòng, không cộng thêm104 lượt vào số case hoặc đổi FAIL thành PASS. Giữ đồng thời hai fixture khi kiểm identity; ba thứ tự đạt là evidence thực nghiệm, chưa chứng minh mọi hoán vị.

## 3.7. Dashboard báo PASS dù thiếu test

**Nguyên nhân/risk.** 17 PASS không thay thế 20 dòng đầu vào. Với3 parse lỗi, status phải là17 PASS/0 FAIL/3 BLOCKED; pass rate trên toàn bộ CSV là85%, execution completeness85%; không được trình bày100% như toàn bộ suite đã PASS.

**File/function.** test_runner.py → read_cases, validate_row, execute_case, summarize, run_runner_checks, run_suite, export_reports. **Cơ chế đã cài:** pandas.read_csv không skip bad lines; lỗi JSON/schema/ID/operation được tạo record BLOCKED có lý do, actual `not_executed`, thời gian và evidence. Parse CSV toàn cục lỗi dùng stdlib csv để khôi phục record và block thay vì bỏ qua. `assert executed + blocked == csv_count`, `len(results)==csv_count`; PASS rate mẫu số luôn là csv_count; `data_complete` đòi không BLOCKED, `all_passed` đòi thêm không FAIL và verification_complete; WARNING cấm kết luận100% khi chưa đủ. Các kiểm regression cố ý đưa dữ liệu lỗi để xác nhận BLOCKED và xác nhận exception sai/thiếu không bị PASS.

**Thay đổi đã cài:** lệnh chạy chính tự sinh31 kết quả unittest; exit2 khi có BLOCKED, FAIL không tái hiện, hồi quy runner không đạt hoặc đổi thứ tự làm sai lệch; exit3 khi suite gặp lỗi không xử lý được. Exit0 xác nhận quy trình đầy đủ, vẫn có thể có9 FAIL sản phẩm; status/counts trong summary là nguồn sự thật, không dùng exit0 đồng nghĩa không defect. Nếu dùng CI sau này có thể thêm policy riêng làm job thất bại khi còn FAIL sản phẩm.

| Case kiểm runner | Data | Expected |
|---|---|---|
| PS-COMP-01 | frame20 dòng:17 PASS,3 BLOCKED vì input_json sai | total20,executed17,blocked3,pass_rate85.0,data_complete=False,all_passed=False |
| PS-COMP-02 | frame19 kết quả nhưng csv_count20 | summarize raise AssertionError DATA_COMPLETENESS_FAILED hoặc RESULT_ROW_COUNT_MISMATCH; không tạo headline100% |
| PS-COMP-03 | copy TC-CART-003 với input_json=`{bad`; copy khác operation lạ; hai ID trùng | validate_row trả lý do riêng; execute_case gán BLOCKED; mỗi dòng vẫn có evidence, actual và ms |

**Evidence.** reports/runner_validation.txt và .csv được tự sinh mỗi lần chạy: test_23 kiểm17 PASS/3 BLOCKED→85%, test_24 từ chối thiếu record, test_02/05/06 kiểm invalid JSON/duplicate/unknown operation đều BLOCKED trước fixture/dispatch. Summary suite thật ghi52 dòng,31 kiểm runner báo riêng; actual dùng làm mốc so thứ tự không trở thành expected nghiệp vụ. Dữ liệu hỏng nằm trong bộ nhớ/CSV tạm dưới reports và được xóa, không ghi đè CSV/expected khóa.

## 3.8. Đổi quy định miễn phí vận chuyển lên700k

**Nguyên nhân/risk.** Giữ dữ liệu quanh500k sẽ bỏ sót ranh giới mới. Đây là yêu cầu tương lai, không được sửa expected của suite500k để làm việc hiện tại PASS.

**File/function và impact.** REQ-09 phải phiên bản mới; COND-SHP-INNER và TS-SHP-INNER thay oracle; dataset TC-SHP-001/002/003 cần thay thế có phê duyệt. TC-SHP-004/005/006 outer là regression giữ50000; ecommerce_app.py → Shipping.calculate cần cấu hình ngưỡng700000. Checkout.place và assertion total/order ở TC-PRO-010/012 (600k từ ship0 sang30000, total540000 sang570000) phải đánh giá lại; case payment850k không đổi, B300k vẫn30000. Không đổi ngưỡng voucher vì đây là policy shipping, không phải SAVE10.

**Thay đổi dự kiến:** xin duyệt rule mới, version dataset/expected, cập nhật code shipping và fixture cho biên699999/700000/700001; kiểm integration trước/sau discount và báo cáo trace đầy đủ. Bản nộp không thực hiện các sửa đổi này.

| Case thiết kế tương lai | Data | Expected nếu policy700k được duyệt |
|---|---|---|
| PS-SHIP-01 | inner699999 | Decimal30000 |
| PS-SHIP-02 | inner700000 | Decimal0 |
| PS-SHIP-03 | inner700001 | Decimal0 |
| PS-SHIP-04 | outer699999/700000/700001 | Decimal50000 cho cả ba |
| PS-SHIP-05 | inner600000, SAVE10 eligible giảm60000 | ship30000 theo subtotal trước giảm; total570000 |

**Evidence.** Matrix hiện tại nối sáu ca Shipping tới REQ-09; Execution chứng minh policy500k đang được kiểm. Các PS-SHIP chưa chạy; sau duyệt sẽ cần execution report/hash mới và regression Payment/Promotion có total bị ảnh hưởng, không thay expected lịch sử.
