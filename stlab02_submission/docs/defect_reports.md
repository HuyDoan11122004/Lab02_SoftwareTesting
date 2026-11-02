# Defect reports và xác nhận tái hiện

## Căn cứ kết luận

Bộ52 ca có43 PASS,9 FAIL,0 BLOCKED; mỗi FAIL đã chạy riêng lần nữa qua execute_case, fixture mới hoàn toàn. reports/failure_rechecks.csv chứa9 dòng với reproduced=True, so sánh cả actual JSON và status giữa hai lần. Không sửa expected hoặc ecommerce_app.py sau khi chạy; hai SHA256 trong requirements_analysis.md khớp trước/sau. Một lần gọi `python test_runner.py --case <TC-ID>` tái hiện đúng ca mà không ghi đè report toàn bộ.

Bản nâng cấp còn tự chạy31 kiểm hồi quy runner và kiểm original/reverse/shuffled(seed20261102). Hai thứ tự bổ sung có104/104 đối chiếu khớp, cả9 FAIL giữ nguyên actual/state; xem reports/order_execution.csv và order_independence.csv/.json. Điều này tăng evidence về fixture isolation, không thay thế business oracle, không tạo defect mới từ lỗi giả lập trong self-test và không chứng minh defect sản phẩm đã được sửa.

Defect được nhóm theo nguyên nhân gốc, không tạo chín ticket trùng nhau. DEF-001 là **ứng viên cần BA xác nhận định nghĩa integer/bool**; DEF-002 và DEF-003 là lỗi an toàn giao dịch đã tái hiện. Các assertion core REQ-10 về không tạo order/charge khi declined thực tế đều đúng; FAIL của nhóm đó do invariant stock theo Instruction §2.5 và yêu cầu kiểm state. Không gán lỗi không tồn tại cho Payments.collect hoặc voucher-used.

## DEF-001 — Cart nhận True làm quantity nguyên dương

**Trạng thái:** tái hiện2/2 case, cần xác nhận BA; phù hợp giả định oracle integer nghiệp vụ nghiêm ngặt, chưa khẳng định business đã phê duyệt loại bool. **Severity dự kiến:** Major (dữ liệu sai kiểu đi qua pricing/promotion), **Priority:** P1 (sau lỗi hao hụt kho P0). Severity mô tả tác động, priority là thứ tự xử lý.

| TC | REQ | Condition | Scenario |
|---|---|---|---|
| TC-CART-005 | REQ-02 | COND-CART-TYPE | TS-CART-QUANTITY |
| TC-PRO-008 | REQ-05 | COND-PRO-INPUT | TS-PRO-QUANTITY |

**Rule/oracle.** Requirement §1.1 và Instruction §1.2 REQ-02 ghi số nguyên dương; chưa nói bool. requirements_analysis.md đã chọn từ trước “quantity kiểu integer, không phải boolean”. TC-PRO-008 mang cùng kiểm tra type trong tiền điều kiện luồng voucher, không phải bug về quyền SAVE10. Không dựa vào actual để đổi expected thành chấp nhận True.

**Bước tái hiện.** (1) fixture("empty"); (2) với TC-PRO-008, setup giá A=Decimal600000; (3) Cart.add("A", True); TC-PRO-008 tiếp tục Cart.subtotal và Promotions.discount("SAVE10",subtotal,user); (4) snapshot giỏ/kho/order/charge/used_codes. Tái hiện bằng `python test_runner.py --case TC-CART-005` và `--case TC-PRO-008`.

| Quan sát | Expected | Actual |
|---|---|---|
| Exception | ValueError INVALID_QUANTITY ở Cart.add | không raise |
| Cart lines trước/sau | [] → [] | [] → [{sku:A,quantity:true}] |
| Return TC-CART-005 | không có return do exception | None |
| Return TC-PRO-008 | không được tới bước discount | Decimal60000 |
| Stock trước/sau | A20/B15/C12 → nguyên trạng | nguyên trạng, đúng |
| Orders/charges/used_codes | 0 / [] / [] | đúng, không side effect thanh toán |

**Root cause.** ecommerce_app.py → Cart.add → dòng40: `if not isinstance(quantity,int) or quantity<1: ...`. Python coi isinstance(True,int) là True và True<1 là False, nên đi tới dòng43 append(CartLine(...)). Theo giả định strict integer, kiểm kiểu này quá rộng. Điều kiện nhận float/string/0/−1 vẫn đúng; không sửa ứng dụng trong bài nộp.

**Đề xuất sửa.** Sau khi BA xác nhận, dùng `type(quantity) is not int or quantity < 1` hoặc loại `isinstance(quantity,bool)` riêng trước kiểm int. Không âm thầm convert string/float/bool. Nếu BA muốn chấp nhận bool, phải thay đổi hợp đồng/test expected qua quy trình phê duyệt riêng; bản hiện tại vẫn giữ nguyên oracle ban đầu và ghi rõ uncertainty.

**Regression.** TC-CART-001–007,011; TC-PRO-004–009 kiểm0/−1/1/float/bool/string; TC-CART-008/009 bảo đảm cộng dồn không hỏng. Evidence: hai dòng FAIL và hai dòng RECHECK tương ứng, actual chứa JSON true để không đánh đồng với int1.

## DEF-002 — Checkout không hoàn stock khi ONLINE declined

**Trạng thái:** xác nhận tái hiện trên4 ca và4 recheck, fixture đúng; không có lỗi test script đã được dùng để điều chỉnh expected. **Severity:** High (giảm tồn kho khi không bán được hàng, retry làm hụt thêm), **Priority:** P0. Cùng một nguyên nhân thiếu rollback được ghi một mục dù thấy ở Payment và Promotion.

| TC | REQ | Condition | Scenario |
|---|---|---|---|
| TC-PRO-011 | REQ-05 | COND-PRO-REJECT | TS-PRO-CHECKOUT |
| TC-PRO-012 | REQ-05 | COND-PRO-ELIGIBLE | TS-PRO-RETRY-AFTER-DECLINE |
| TC-PAY-006 | REQ-10 | COND-PAY-ONLINE | TS-PAY-CHECKOUT |
| TC-PAY-007 | REQ-10 | COND-PAY-ONLINE | TS-PAY-CHECKOUT |

**Rule/oracle.** REQ-10 yêu cầu declined không tạo đơn; yêu cầu này hiện đạt. Instruction §2.5 nói rõ khi online declined thì mọi stock đã giữ phải hoàn lại; đây là invariant bổ sung đã ghi trong expected trước chạy, phù hợp yêu cầu người dùng phải kiểm stock. REQ-08 không được chọn làm requirement hay cộng coverage. Quyền voucher ở REQ-05/lifecycle không bị tiêu hao sau declined, nên không báo thêm bug used_codes.

**Bước tái hiện.** (1) fixture mới theo từng dòng; (2) chụp stock/orders/charges/used_codes; (3) Checkout.place(user,cart,method="ONLINE",approved=False,key=TC-ID), TC-PRO-011 có voucher="SAVE10"; (4) bắt PAYMENT_DECLINED rồi chụp state. Riêng TC-PRO-012 giữ cùng app trong **một case**, lần2 approved=True với key mới; quan sát từng event và state cuối. Không phải retry cùng idempotency key.

| TC | Stock trước A/B/C | Expected sau | Actual sau | Order/charge/voucher |
|---|---|---|---|---|
| TC-PRO-011 |20/15/12|20/15/12|17/15/12|orders0,charges[],used[] đúng; PAYMENT_DECLINED đúng |
| TC-PRO-012 event1 |20/15/12|20/15/12|17/15/12|declined, orders0,charges[],used[] đúng |
| TC-PRO-012 event2 |expected20/15/12, actual17/15/12|17/15/12 cuối sequence|14/15/12 cuối sequence|orders1 PAID,total540000; một charge540000,used[SAVE10] đúng |
| TC-PAY-006 |20/15/12|20/15/12|18/14/11|orders0,charges[],used[] đúng; PAYMENT_DECLINED đúng |
| TC-PAY-007 |20/15/12|20/15/12|20/14/12|orders0,charges[],used[] đúng; PAYMENT_DECLINED đúng |

**Expected vs actual return/state.** Các ca declined đơn kỳ vọng đúng class/message ValueError PAYMENT_DECLINED và không có order. Actual khớp exception nhưng state kho sai; diff/traceback trong error_message chỉ ra trường stock, không phải thiếu PAYMENT_DECLINED. Sequence trả hai event; event2 order/payment/used_codes đều đúng, tồn kho14 thay17 là failure còn lại từ event1.

**Root cause.** ecommerce_app.py → Checkout.place → dòng94 `self.inventory.reserve(cart.lines)` chạy trước dòng97 `payment_state=self.payments.collect(total,method,approved,key)`. Payments.collect dòng77 raise PAYMENT_DECLINED; Checkout.place không có try/except/release quanh collect nên stack unwind giữ stock đã giảm. Inventory.release tồn tại dòng52–53 nhưng không được gọi ở đường lỗi. Tìm nguyên nhân sau khi kiểm input, fixture và đối chiếu acceptance; không sửa expected hay mã sản phẩm.

**Đề xuất sửa.** Bao bọc giai đoạn reserve/payment/commit bằng transaction; nếu collect thất bại sau reserve thành công thì release đúng các line đã giữ rồi re-raise cùng exception. Không release khi reserve chưa thành công, tránh tăng stock ảo. Với production cần giải quyết cạnh tranh, commit/charge thất bại và compensation có log; lab chỉ cần bảo đảm đường declined đúng invariant.

**Regression.** Tất cả4 ca FAIL ở trên; TC-PAY-002/003/004/005 bảo đảm approved/COD/direct decline không bị hỏng; TC-PRO-010 đảm bảo dùng mã chỉ sau success; TC-INV-001–006 đảm bảo atomicity và exact-stock không bị release sai. Evidence: reports/failure_rechecks.csv reproduced=True cho4 ID và observed_before/after; run_log.txt có timestamp từng recheck.

## DEF-003 — Method không hợp lệ bị phát hiện sau khi đã reserve stock

**Trạng thái:** xác nhận3/3 ca checkout và3 recheck. **Severity:** High (request không được hỗ trợ vẫn làm giảm hàng sẵn bán), **Priority:** P0. Đây là lỗi validate quá muộn, tách khỏi thiếu rollback cho một method ONLINE hợp lệ nhưng declined ở DEF-002; có thể dùng chung cơ chế rollback phòng vệ nhưng cần sửa thứ tự validation riêng.

| TC | REQ | Condition | Scenario |
|---|---|---|---|
| TC-SAFE-002 | REQ-16 | COND-SAFE-CHECKOUT | TS-SAFE-CHECKOUT |
| TC-SAFE-003 | REQ-16 | COND-SAFE-CHECKOUT | TS-SAFE-CHECKOUT |
| TC-SAFE-005 | REQ-16 | COND-SAFE-CHECKOUT | TS-SAFE-CHECKOUT |

**Rule/oracle.** REQ-16 chỉ chấp nhận COD/ONLINE; “bị từ chối” được thiết kế là không tạo side effect giao dịch. Phần lõi reject đúng exception đang đạt, nhưng request chưa hợp lệ không được tiêu hao stock. Đây là assertion state được yêu cầu và đã viết trước khi chạy; chưa có yêu cầu hỗ trợ hoặc normalize WALLET/CRYPTO/online.

**Bước tái hiện.** (1) fixture("mixed") có A2/B1/C1 và stock20/15/12; (2) chụp state; (3) Checkout.place(..., method="WALLET") hoặc "online"/"CRYPTO", key bằng TC-ID; (4) bắt ValueError INVALID_PAYMENT_METHOD, chụp state và so với snapshot trước. CLI `python test_runner.py --case TC-SAFE-002` in cùng thông tin.

| Trường | Expected (cả3 case) | Actual (cả3 case) |
|---|---|---|
| Exception | ValueError INVALID_PAYMENT_METHOD | đúng |
| Stock A/B/C trước/sau |20/15/12 →20/15/12|20/15/12 →18/14/11|
| Orders, charges, used_codes |0,[],[]|đúng, không order/charge/mã đã dùng|
| Cart lines |A2/B1/C1 nguyên trạng|đúng|

**Root cause.** ecommerce_app.py → Checkout.place dòng94 reserve trước khi dòng97 collect. Method validation chỉ ở Payments.collect dòng76: `if method!='ONLINE': raise ValueError('INVALID_PAYMENT_METHOD')` sau nhánh COD dòng75. Vì Checkout.place không validate method trước reserve, yêu cầu không hợp lệ vẫn giảm kho. Direct collect TC-SAFE-001/004 PASS chứng minh lỗi nằm ở trình tự điều phối, không phải collect chấp nhận WALLET.

**Đề xuất sửa.** Validate method thuộc{"COD","ONLINE"} ở đầu Checkout.place trước mutation; tách validation thuần khỏi collect để không charge trước reserve hoặc gọi payment hai lần. Vẫn cần rollback phòng vệ theo DEF-002 khi đã reserve và payment lỗi. Không thêm phương thức mới hoặc normalize case khi chưa được duyệt.

**Regression.** TC-SAFE-001–005, TC-PAY-001–007, TC-INV-002/006; thêm tương lai (chưa có trong CSV) giỏ thiếu kho+method lạ để BA quyết định precedence lỗi, và unsupported method+voucher để xác nhận không tiêu hao mã. Evidence: ba dòng FAIL/RECHECK, stock before/after và dòng source94/97/76.

## Đối chiếu các nghi vấn được yêu cầu

- **Reserve trước validate:** auth/cart ở87–88, voucher ở90 và shipping area ở91 đã được kiểm trước reserve94; chỉ payment method bị validate muộn ở97→76. Không kết luận toàn bộ validation đều chạy sau reserve.
- **Không rollback khi payment fail:** đã xác nhận DEF-002 bằng4 ca, không chỉ suy ra từ source.
- **Method lạ nhưng kho bị trừ:** đã xác nhận DEF-003; exception đúng không che state sai.
- **Toán tử Promotions.discount dòng64:** source dùng `subtotal <= v.min_subtotal`, trong khi Instruction §1.2 mô tả ≥500000 đủ ngưỡng. Đây là nghi vấn có căn cứ tĩnh, nhưng REQ-06 là worked example bị loại và không có ca voucher tại500000 trong suite này. Không gán defect đã thực thi/tái hiện hoặc cộng vào9 FAIL; cần kiểm riêng ở phạm vi được duyệt. Biên Shipping500000 PASS không phải evidence cho biên Promotion.

Không phát hiện lỗi script/fixture gây9 FAIL trên: các ca positive và đối chứng trực tiếp PASS, snapshot đúng precondition, mọi FAIL tái hiện y hệt trên fixture mới. 31 kiểm tự động của run_runner_checks còn thử invalid JSON/schema/ID/operation, exception oracle, completeness và độ nhạy so thứ tự; kết quả ở reports/runner_validation.txt/.csv được tái tạo bằng lệnh chạy chính. Không tuyên bố đã sửa hoặc retest production sau fix.
