# Phần 4 — Interview Questions và Code Interview

## 1. Requirement, Condition, Scenario, Case và Execution khác nhau thế nào?

Requirement là quy tắc chấp nhận: REQ-09 nội thành miễn phí khi subtotal≥500000. Condition là khía cạnh cần kiểm: COND-SHP-INNER xét ngưỡng nội thành; scenario là WHAT: TS-SHP-INNER kiểm ngay quanh ngưỡng. TC-SHP-002 cụ thể hóa subtotal Decimal500000, area inner, expected Decimal0 và state không đổi. Execution là một lần chạy TC-SHP-002 có RUN ID/timestamp/actual/status/ms trong reports/test_execution.csv; cùng case có thể có nhiều execution.

## 2. Test oracle là gì? Vì sao không lấy actual làm expected?

Oracle là căn cứ phân biệt hành vi đúng/sai, ở đây là acceptance criteria Requirement §1.1 và Instruction §1.2. Với500000 nội thành phải phí0 vì dấu≥ trong requirement, dù code có trả30000 thì vẫn FAIL. Lấy actual làm expected sẽ xác nhận chính bug; bộ CSV được khóa hash trước lần chạy đầu và không sửa theo kết quả. Giao diện source cung cấp cách gọi/tên field, không thay thế business oracle.

## 3. Khi nào dùng equivalence partitioning và boundary value analysis?

Partition Shipping theo inner/outer và dưới/tại-trên ngưỡng; Pricing theo rỗng, một/nhiều SKU, giá Decimal có phần thập phân. Boundary value analysis chọn499999/500000/500001 cho mỗi khu vực (TC-SHP-001–006) để bắt sai dấu so sánh; một ca600000 không phát hiện được lỗi tại ngưỡng. TC-PRI-003 dùng0.1×3+0.2 để phát hiện float, không dùng nó để suy ra policy chốt giá.

## 4. Positive, Negative và Edge case với Cart.add?

Positive: TC-CART-008 add A2 rồi A3, một line A5. Negative: TC-CART-002 qty−1 và TC-CART-007 string"1" bị INVALID_QUANTITY. Edge: TC-CART-003 qty1 là số nguyên dương nhỏ nhất; TC-CART-001 qty0 ngay ngoài biên. True là edge về hệ kiểu Python (TC-CART-005), oracle strict integer cần BA xác nhận.

## 5. Fixture là gì? Vì sao cần riêng từng case?

Fixture tạo precondition lặp lại được: Checkout mới, Customer mới, Cart gắn với catalog mới và dữ liệu test có chủ đích. test_runner.fixture("mixed") tạo A2/B1/C1 với stock20/15/12. Nếu TC-INV-005 reserve hết stock mà dùng lại fixture, ca sau có thể FAIL giả; fixture riêng loại bỏ ảnh hưởng này.

## 6. Isolation khác reset sau test thế nào?

Isolation không cho case sau nhìn state của case trước ngay từ đầu; teardown/reset là cơ chế dọn state đã dùng và có thể thiếu field hoặc không chạy sau crash. Fixture mới không cần dựa vào restore giá, kho, used_codes hay charges thành công. Kiểm bằng giữ đồng thời hai bộ object, mutation bộ đầu rồi assert bộ sau không đổi, thay vì chỉ khẳng định có hàm reset.

Bản nâng cấp tự chạy original/reverse/shuffled(seed20261102). 104/104 đối chiếu của hai thứ tự bổ sung khớp status/actual/state trước/sau theo TC ID, kể cả9 ca FAIL; timestamp và ms không so bằng nhau. Đây là bằng chứng không phụ thuộc ba thứ tự đã thử, chưa chứng minh mọi hoán vị hoặc concurrent request.

## 7. ValueError nào PASS, exception nào FAIL?

Nếu expected_type=exception và class ValueError/message INVALID_QUANTITY khớp, đồng thời state đúng, ca PASS. ValueError khác message, TypeError hoặc không raise đều FAIL; error_message ghi diff và traceback tóm tắt cho exception sai. Lỗi schema/setup xảy ra trước gọi nghiệp vụ là BLOCKED, không gộp vào defect ứng dụng. verify luôn chạy state assertion cả khi bắt được exception đúng.

run_runner_checks dùng test_14–19 tự kiểm các nhánh này, gồm mock dispatcher của runner để mô phỏng sai class/message, không raise và exception đúng nhưng làm đổi stock. Mock được khôi phục sau mỗi kiểm, không sửa ứng dụng hoặc expected gốc; một phép kiểm PASS ở đây nghĩa runner đã nhận diện failure giả lập đúng, không phải thêm PASS vào suite nghiệp vụ.

## 8. Vì sao return value chưa đủ cho Inventory/Payments/Orders?

TC-SAFE-002 nhận đúng INVALID_PAYMENT_METHOD nhưng stock18/14/11 thay vì20/15/12 nên FAIL. TC-PAY-006 declined không tạo order/charge đúng nhưng stock vẫn bị trừ; lỗi giao dịch bị bỏ sót nếu chỉ check exception. Với thành công phải kiểm đúng stock, số order, charge amount/key, customer_id, lines, status, discount/shipping/total và voucher-used.

## 9. Decimal thay float và rounding?

Decimal("0.1") biểu diễn chính xác số thập phân, còn float có thể mang sai số nhị phân. TC-PRI-003 kỳ vọng Decimal0.5; không dựng Decimal từ float trung gian hoặc đổi tiền sang float để so sánh. Instruction.money dùng quantize(Decimal("1"), ROUND_HALF_UP) cho discount VND; thời điểm rounding là một phần hợp đồng, không tự round từng line nếu rule chỉ yêu cầu subtotal bằng tổng. Serialize tiền thành chuỗi giữ chính xác, assert return_type=Decimal trước serialize.

## 10. Data-driven testing và dispatch?

Định nghĩa dữ liệu và oracle theo từng dòng CSV, một runner dùng chung quy trình validation → fixture → operation → oracle → report. input_json của TC-SHP-002 có operation shipping, subtotal"500000", area inner; dispatch gọi Shipping.calculate(Decimal(...), ...). Unknown operation hoặc mapping requirement/operation không hợp lệ bị BLOCKED, không bỏ qua hay gọi hàm tùy ý bằng eval.

## 11. Traceability Matrix giúp impact analysis và coverage thế nào?

Matrix nối REQ-09 → COND-SHP-INNER → TS-SHP-INNER → TC-SHP-001/002/003 → RUN và status. Khi ngưỡng đổi700k, tìm ngay ba case nội thành và các ca checkout chịu đổi total. Coverage có nghĩa là đã có case/lần chạy trong phạm vi, không chứng minh không có bug; runner kiểm cả registry15 conditions/19 scenarios và mapping52 case để tránh orphan.

## 12. Test priority khác defect severity?

Priority là thứ tự chạy/sửa dựa vào risk và thời hạn; severity là mức tác hại khi lỗi xảy ra. Case payment safety P0 vì cần kiểm sớm, defect làm thất thoát stock khi request bị reject có severity High; priority sửa P0. DEF-001 bool nhận sai là Major/P1 dự kiến và còn cần BA xác nhận; hai trục không đồng nghĩa và không suy priority chỉ từ số ca FAIL.

## 13. Unit, Integration và System; Checkout.place thuộc mức nào?

Shipping.calculate thuần rule có thể kiểm unit; Cart.add/subtotal là unit ở cấp class với catalog thật nên có dependency nhỏ. Checkout.place dùng Inventory, Promotions, Shipping, Payments thật trong bộ nhớ là integration/service-level. Bộ lab không có web UI, API transport, database hay gateway thật nên không gọi là system/end-to-end triển khai production; “chạy đầu-cuối” ở đây là toàn bộ quy trình test/report được thực thi.

## 14. State transition COD/ONLINE và xác nhận PAID?

COD thành công tạo order PENDING_COD, không charge online dù approved=False ở direct collect (TC-PAY-001). ONLINE approved=True tạo đúng một charge và order PAID (TC-PAY-005). Declined raise PAYMENT_DECLINED, orders/charges không tăng; không có order mới để gắn trạng thái PAID/DECLINED. Assertion nhìn status và charges, không suy paid từ việc order_id tồn tại.

## 15. Idempotency và side effects của retry?

Idempotency nghĩa cùng khóa đại diện cùng request chỉ có tác dụng nghiệp vụ một lần. Trả cùng order mà mỗi retry vẫn reserve hoặc charge là vi phạm; phải kiểm order count, stock, charge count/amount và mã dùng, cả sau2–3 lần retry. Đây là giải thích khái niệm theo câu hỏi; REQ-11 không được chọn và không có case idempotency trong CSV. TC-PRO-012 dùng hai key khác nhau cho declined/success, không phải test idempotency.

## 16. Phân biệt lỗi sản phẩm và lỗi script/fixture?

Trước hết đối chiếu expected với rule, kiểm data/types/precondition, rồi chạy riêng case bằng fixture mới và so state. Nếu fixture sai giá hoặc operation gọi nhầm thì sửa script/setup theo thiết kế đã duyệt, không sửa expected; rerun toàn bộ. Nếu actual vẫn vi phạm rule trên fixture đúng và source xác định được nguyên nhân thì ghi defect. 9 FAIL đều có recheck tương ứng; DEF-001 được giữ dưới dạng cần xác nhận bool, không mặc định mọi FAIL là lỗi sản phẩm đã chốt.

## 17. Gradio có thay raw evidence/log không?

Không. Dashboard là phép lọc/tổng hợp và có thể đang xem subset hay report cũ; raw Execution CSV ghi expected/actual/error/state/ms/RUN, run_log.txt ghi console timestamp và failure_rechecks.csv chứng minh tái hiện. Gradio đọc lại CSV theo mỗi callback, hiển thị counts sau lọc nhưng không thay mẫu số pass rate suite gốc. Đã kiểm import/build và callbacks, không mở server hoặc share=True.

HTML/summary.json hiện trình bày riêng31 kiểm runner và bảng ba thứ tự. order_execution.csv lưu156 lượt của52 ca; order_independence.csv lưu phép đối chiếu, không gộp156 thành số case duy nhất hay biến9 FAIL ổn định thành PASS.

## 18. Sanity và regression sau sửa bug?

Sanity chạy nhanh đúng defect đã sửa và một ca success lân cận: DEF-003 dùng TC-SAFE-002 và TC-PAY-005, bảo đảm method lạ không trừ kho và ONLINE hợp lệ vẫn charge đúng. Regression chạy toàn bộ52 case trên fixture sạch, đặc biệt decline/atomicity/voucher sequence và biên Shipping. Không sửa production trong nhiệm vụ này; recheck hiện tại xác nhận FAIL, chưa phải retest sau fix hay bằng chứng bug đã hết.

## 19. Một repository/bộ source cần gì để tái hiện Colab?

Về nguyên tắc cần mã ứng dụng nguyên bản, runner, dataset expected, mapping trace, phiên bản Python/thư viện, lệnh chạy sạch, report mẫu và giải thích cách thiết lập trong README. Với phạm vi người dùng hiện tại, không tạo repository/README hoặc thao tác GitHub; thông tin môi trường/lệnh chạy được đặt trong requirements_analysis.md, raw evidence ở reports và run_log.txt. Người nhận chạy Python3.10+, cài đúng bốn thư viện, rồi `python test_runner.py` từ stlab02_submission để tái hiện.

## 20. Nếu chỉ đủ thời gian chạy5 case, chọn theo risk ra sao?

Chọn TC-SAFE-002 (unsupported method gây side effect), TC-PAY-006 (declined nhiều SKU), TC-INV-002 (atomicity thiếu B), TC-PAY-005 (đường mua thành công/paid/charge/total), TC-PRO-012 (voucher qua declined rồi retry với key mới). Bộ này ưu tiên mất hàng/tiền và happy path để tránh runner chỉ kiểm rejection. Thiếu thời gian phải báo coverage hạn chế; không suy bộ5 ca bao phủ quantity typing hay sáu biên Shipping. Nếu đợt thay đổi chỉ liên quan shipping, thay tập ưu tiên bằng biên mới và integration total theo impact analysis.

## Code Interview A — Sửa exception oracle

Lỗi thiết kế là catch mọi exception rồi gán FAIL dù đó chính là expected. CSV phải lưu riêng class/message và state mong đợi; không dùng chuỗi actual bắt được để tạo expected. Mẫu dùng hàm compare có thật trong test_runner.py:

```python
from test_runner import fixture, snapshot, compare

def check_invalid_quantity():
    app, user, cart = fixture("empty")
    before = snapshot(app, user, cart)
    try:
        cart.add("A", 0)
    except Exception as error:
        assert type(error) is ValueError, (type(error).__name__, str(error))
        assert str(error) == "INVALID_QUANTITY"
    else:
        raise AssertionError("EXPECTED_EXCEPTION_NOT_RAISED")
    after = snapshot(app, user, cart)
    assert not compare(before, after), "Rejection changed state"
    return "PASS"
```

Mẫu này kiểm cả trường hợp không raise; state được kiểm sau expected exception, không return PASS ngay trong except. Runner thật dùng verify để thu mọi diff thay vì dừng ở assert đầu tiên; exception ngoài mong đợi thêm traceback. Validation/schema/setup trước hành vi là BLOCKED.

## Code Interview B — Bổ sung assertion để tránh false positive

Chỉ assert order_id khác None là oracle thiếu: một order có ID vẫn có thể sai tiền, gắn PAID khi chưa charge hoặc trừ kho sai. Ví dụ runnable trên fixture mixed của TC-PAY-005; expected lấy từ850000=200000×2+300000+150000 và rule payment/shipping:

```python
from copy import deepcopy
from decimal import Decimal
from test_runner import fixture, snapshot

def check_paid_order():
    app, user, cart = fixture("mixed")
    before = snapshot(app, user, cart)
    key = "INTERVIEW-B"
    order = app.place(user, cart, method="ONLINE", approved=True, key=key)
    assert isinstance(order.order_id, str) and order.order_id
    assert len(app.orders) == before["orders_count"] + 1
    assert app.orders[order.order_id] is order
    assert order.customer_id == "U_NEW"
    assert order.lines == [("A", 2), ("B", 1), ("C", 1)]
    assert order.status == "PAID" and order.payment_method == "ONLINE"
    assert type(order.total) is Decimal
    assert order.discount == Decimal("0")
    assert order.shipping == Decimal("0")
    assert order.total == Decimal("850000")
    assert order.total == Decimal("850000") - order.discount + order.shipping
    assert order.total >= Decimal("0")
    after = snapshot(app, user, cart)
    assert after["stock"] == {"A": 18, "B": 14, "C": 11}
    assert app.payments.charges == [{"key": key, "amount": Decimal("850000")}]
    assert after["used_codes"] == before["used_codes"] == []
    assert after["lines"] == before["lines"]
    return "PASS"
```

Với COD, expected status=PENDING_COD và charges=[]; với declined/invalid method phải check orders0/charges[]/stock nguyên, thay vì chờ có order_id. Assertions này không có nghĩa mọi ID phải có format ORD-xxxx; ID được xem opaque.

## Code Interview C — Shared fixture

Khởi tạo một fixture ở đầu notebook rồi dùng cho mọi case gây order-dependent failure: case đầu giảm stock, đổi giá hoặc dùng SAVE10 làm ca sau sai. Khôi phục mỗi stock không đủ nếu bỏ quên used_codes, prices, by_key hoặc charges. Đặt fixture bên trong execute_case; một sequence nghiệp vụ trong cùng ca được dùng chung object có chủ đích.

```python
from decimal import Decimal
from test_runner import fixture

def check_fresh_fixture():
    first_app, first_user, first_cart = fixture("mixed")
    next_app, next_user, next_cart = fixture("mixed")
    assert first_app is not next_app
    assert first_user is not next_user and first_cart is not next_cart
    assert first_app.catalog is not next_app.catalog
    first_app.catalog.products["B"].price = Decimal("1")
    first_app.catalog.products["A"].stock = 0
    first_user.used_codes.add("SAVE10")
    assert next_app.catalog.products["B"].price == Decimal("300000")
    assert next_app.catalog.products["A"].stock == 20
    assert next_user.used_codes == set()
    assert next_app.orders == {} and next_app.payments.charges == []
    assert next_cart.subtotal() == Decimal("850000")
    return "PASS"
```

Ba đoạn code được thực thi tự động qua test_30_code_interview_examples trong run_runner_checks mỗi lần chạy `python test_runner.py`; kết quả nằm trong reports/runner_validation.txt và .csv. Bộ này có31 kiểm regression bằng unittest chuẩn, tách khỏi52 ca CSV; không tăng coverage nghiệp vụ hay thay expected gốc. Exit2 nếu hồi quy runner hoặc kiểm độc lập thứ tự không đạt, dù các ca nghiệp vụ có thể vẫn báo PASS.
