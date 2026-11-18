# Báo cáo Day 09 — Lê Văn Khởi: 03290 - Lê Văn Khởi

## 1. Kết luận trước

Pipeline kết luận **Hold** cho lô dữ liệu 224 ảnh COCO thô.

- **Số ảnh đầu vào:** 224 ảnh; bị loại 31 ảnh ở cửa nhận dữ liệu (intake) do không đạt chuẩn kỹ thuật (3 ảnh kích thước quá nhỏ < 250px, 2 ảnh hỏng không đọc được, 8 ảnh trùng lặp tuyệt đối, 7 ảnh trùng lặp gần đúng theo pHash, 11 ảnh rò rỉ từ tập kiểm thử).
- **Số ảnh đưa vào pipeline kiểm tra:** 193 ảnh.
- **Số ảnh xuất bản nháp:** 193 ảnh vào thư mục `submission/export/clean_v1` (dataset dạng NHÁP để thử nghiệm nội bộ, chưa được phép phát hành chính thức).
- **Lý do chính:** Sau khâu tự động sửa lỗi (autofix) và người duyệt mô phỏng 80 ảnh, pipeline đã sạch hoàn toàn lỗi bắt buộc (`n_errors = 0`). Tuy nhiên, do ngân sách người duyệt bị giới hạn ở 80 ảnh trong khi hàng đợi cần tới 121 ảnh, vẫn còn 41 ảnh chưa được người thẩm định. Điều này khiến tỉ lệ ảnh còn cảnh báo đạt **17.62%** (34/193 ảnh), vượt quá ngưỡng trần cho phép **10.00%**, do đó cổng chất lượng quyết định giữ lại (**Hold**).

---

## 2. Lỗi và phân việc

Thống kê gom theo mã lỗi từ báo cáo ban đầu `02_error_list_v1`:

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|:---:|---|
| `BAD_SIZE` | 3 ảnh | Máy (intake) | Ảnh có cạnh ngắn < 250px không đạt quy chuẩn tối thiểu, máy tự loại bỏ. |
| `CORRUPT_IMAGE` | 2 ảnh | Máy (intake) | File ảnh bị lỗi cấu trúc nhị phân (UnidentifiedImageError/OSError), máy tự loại bỏ. |
| `DUP_IMAGE_EXACT` | 8 ảnh | Máy (intake) | Ảnh trùng lặp từng byte (MD5 hash trùng khớp 100%), máy tự loại bỏ ảnh thừa. |
| `DUP_IMAGE_NEAR` | 7 ảnh | Máy (intake) | Ảnh trùng lặp gần đúng (khoảng cách pHash $\le 16$), máy tự loại bỏ để tránh thiên lệch dữ liệu. |
| `LEAK_TEST` | 11 ảnh | Máy (intake) | Ảnh trùng với kho test/gold_val, máy tự loại bỏ để ngăn chặn rò rỉ dữ liệu (data leakage). |
| `BAD_CLASS_NAME` | 2 lỗi | Máy (autofix) | File `data.yaml` chứa tên lớp lạ ('Person', 'Bus'), máy tự chuẩn hoá thành chữ thường theo cấu hình. |
| `BAD_CLASS_ID` | 6 dòng | Máy (autofix) | ID lớp ngoài dải [0..3] (như 93, -1, 4, 7), dòng không thể cứu nên máy xóa dòng (`drop_line`). |
| `BAD_FORMAT` | 3 dòng | Máy (autofix) | Dòng nhãn thiếu cột hoặc chứa giá trị NaN/Inf, máy tự xóa dòng (`drop_line`). |
| `BOX_ZERO` | 4 dòng | Máy (autofix) | Bounding box có chiều rộng hoặc chiều cao $\le 0$, máy tự xóa dòng rác (`drop_line`). |
| `DUP_BOX` | 7 dòng | Máy (autofix) | Trùng lặp box cùng lớp với $IoU > 0.9$, máy tự xóa dòng xuất hiện sau (`drop_line`). |
| `BOX_OUT_OF_IMAGE` | 8 dòng | Máy (autofix) | Box tràn ra ngoài mép ảnh quá dung sai 0.002, máy tự nắn tọa độ về dải [0, 1] (`clip_box`). |
| `MISSING_LABEL_FILE` | 6 ảnh | Người (hàng đợi) | Ảnh thiếu file nhãn; máy không được bịa nhãn (rỗng = ảnh nền), bắt buộc người phải gán nhãn mới. |
| `BOX_HUGE` | 3 dòng | Người (hàng đợi) | Cảnh báo box chiếm > 95% diện tích ảnh, nghi ngờ vẽ bao trùm ẩu toàn khung hình. |
| `BOX_TINY` | 6 dòng | Người (hàng đợi) | Cảnh báo box có cạnh < 12px, nghi ngờ quá nhỏ để mô hình phát hiện. |
| `CLASS_RARE` | 4 lỗi | Người (hàng đợi) | Cảnh báo các lớp hiếm xuất hiện bất thường trong tập nhãn. |
| `EMPTY_LABEL` | 11 ảnh | Người (hàng đợi) | File nhãn rỗng: cần mắt người thẩm định xem đây là ảnh nền (negative sample) hay bị bỏ sót nhãn. |
| `POSSIBLE_WRONG_CLASS` | 17 dòng | Người (hàng đợi) | Model yolo26l nghi ngờ nhãn gán sai lớp ($IoU \ge 0.5$ với dự đoán khác lớp), cần người phân xử ngữ nghĩa. |
| `POSSIBLE_MISSING` | 53 dòng | Người (hàng đợi) | Model yolo26l phát hiện vật thể rõ ràng nhưng nhãn không có box, cần người bổ sung nếu thực sự sót. |
| `POSSIBLE_LOOSE_BOX` | 27 dòng | Người (hàng đợi) | Box cùng lớp nhưng vẽ lỏng/lệch ($IoU < 0.5$ với dự đoán model), cần người căn chỉnh lại viền. |
| `POSSIBLE_FALSE_POS` | 28 dòng | Người (hàng đợi) | Box nhãn do người vẽ không khớp với bất kỳ dự đoán nào của model, cần người kiểm tra có vẽ bậy. |

**Về thứ tự ưu tiên của hàng đợi `05_review_queue.csv`:**
Hàng đợi sắp xếp các ảnh có điểm số nguy cơ (*Priority score*) từ cao xuống thấp. Điểm số được tính bằng tổng trọng số các mã lỗi có trong ảnh kết hợp với độ tin cậy (*confidence score*) của model.
- Ảnh thiếu file nhãn (`NEEDS_LABEL`) có trọng số cao nhất (trọng số 10) vì đây là lỗi nghiêm trọng (`ERROR`), nếu không được duyệt gán nhãn thì pipeline sẽ bị kết luận Rework ngay lập tức.
- Các ảnh dính nhiều lỗi ngữ nghĩa nặng như `POSSIBLE_WRONG_CLASS` (trọng số 3), `POSSIBLE_MISSING` (trọng số 2) kết hợp với các dòng vừa bị máy sửa tự động (`FIXED_DROP_LINE`, `FIXED_CLIP_BOX`) được đẩy lên đầu (ví dụ ảnh `img_0020` đứng đầu với 11.524 điểm).
- Các cảnh báo nhẹ hoặc đơn lẻ như `BOX_TINY` (0.3), `DENSE_IMAGE` (0.3) có trọng số thấp nên xếp phía sau.

**Khả năng xử lý của người duyệt với ngân sách 80 ảnh:**
Hàng đợi review queue có tổng cộng 121 ảnh. Với ngân sách giới hạn 80 ảnh, người duyệt mô phỏng đã xử lý được 80 ảnh có nguy cơ cao nhất: giải quyết triệt để 6 ảnh thiếu nhãn (xóa bỏ toàn bộ lỗi `ERROR`) và xử lý phần lớn các ca sai lớp, sót nhãn nặng. Còn lại 41 ảnh chưa được xem xét, khiến 34 ảnh còn chứa cảnh báo tồn đọng (tỉ lệ 17.62% > 10%).

---

## 3. Calibration (2 ngưỡng)

| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|:---:|:---:|:---:|---|
| `duplicates.phash_dist` | 2 | 16 | 1.00 / 0.50 → 1.00 / 0.83 (DUP_IMAGE_NEAR) | Bắt thêm 2 ảnh gần trùng (tăng từ 3/6 lên 5/6 ảnh), F1 tăng từ 0.67 lên 0.91, vẫn đạt 0 báo nhầm trên tập calib. |
| `second_opinion.conf` | 0.25 | 0.6 | Missing: 0.50 / 1.00 → 0.57 / 1.00<br>Wrong class: 0.56 / 0.83 → 0.62 / 0.83 | Bắt đủ 8/8 ảnh thiếu nhãn (Recall 1.00), giữ 5/6 ảnh sai lớp (Recall 0.83) và giảm số ảnh báo nhầm sai lớp từ 4 xuống 3, giúp giảm tải hàng đợi duyệt. |

**Một chỗ calibration có thể đánh lừa:**
1. **Đánh đổi ngầm giữa các mã lỗi:** Nếu chỉ nhìn vào lỗi thiếu nhãn (`POSSIBLE_MISSING`), việc tăng `conf` từ 0.25 lên 0.6 tưởng như toàn lợi (Recall vẫn 8/8, Precision tăng từ 0.50 lên 0.57). Nhưng thực tế có sự đánh đổi ngầm: số ảnh phát hiện đúng box lỏng (`POSSIBLE_LOOSE_BOX`) bị giảm từ 2/5 xuống 1/5. Ta chấp nhận đánh đổi này vì ưu tiên bắt lỗi thiếu nhãn và sai lớp (vốn có trọng số cao hơn trong hàng đợi duyệt).
2. **Kích thước mẫu nhỏ (39 ảnh):** Chỉ có 6 ảnh gần trùng và 8 ảnh thiếu nhãn trong phép đo tương ứng. Bắt thêm một ảnh gần trùng đã làm recall tăng khoảng 16,7 điểm phần trăm. Ngoài ra, tập calib dựng từ nhãn người sạch với lỗi chèn nhân tạo, không phản ánh trọn vẹn độ phức tạp của dữ liệu thô (raw).

---

## 4. Cửa chặn và điều pipeline KHÔNG bắt được

**(a) Thực nghiệm chứng minh Quality Gate chặn đúng:**
Chạy lệnh kiểm thử với ngân sách người duyệt bằng 0:
```cmd
python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb
```
- **Hiện tượng quan sát:**
  + Do ngân sách người duyệt bằng 0, 6 ảnh thiếu file nhãn (`MISSING_LABEL_FILE`) không có ai gán nhãn.
  + Autofix tuân thủ nghiêm ngặt nguyên tắc không bịa nhãn ma, nên 6 lỗi bắt buộc này còn nguyên sau cả 3 vòng QC.
  + Cửa chặn (gate) phát hiện `n_errors = 6 > 0`, lập tức ra kết luận **REWORK** và thoát với mã thoát **20**.
  + Thư mục `work/exp_nb` hoàn toàn **KHÔNG được tạo/xuất** (thông báo in rõ: `KHÔNG xuất: còn lỗi bắt buộc (Rework)`).
- **Ý nghĩa kỹ thuật:** Trong lần chạy này, 6 lỗi thiếu file nhãn đủ để gate quyết định Rework và chặn xuất dữ liệu.

**(b) Các điểm mù mà pipeline không bắt được:**
1. **Ảnh trùng lặp bị biến đổi mạnh (Heavy augmentation/cropping):** Thuật toán pHash chỉ chịu được nén nhẹ, đổi màu hoặc watermark nhỏ ($Hamming \le 16$). Ảnh cắt xén hoặc xoay mạnh có thể vượt ngưỡng khoảng cách pHash và bị bỏ sót. Thí nghiệm này chưa đo mức biến đổi khiến bộ kiểm tra bỏ sót.
2. **Sai sót ngữ nghĩa mà cả người và model cùng mắc (Shared semantic blindspot):** Khi gặp các trường hợp ranh giới mơ hồ (ví dụ xe bán tải pickup nằm giữa `car` và `truck`, hoặc xe khách nhỏ nằm giữa `bus` và `truck`), nếu cả người gán nhãn lẫn model YOLO26l đều nhầm lẫn giống nhau, `second_opinion` sẽ coi đây là đồng thuận chuẩn (`agreement is silent`) và bỏ qua không cảnh báo.
3. **Box lỏng viền nhẹ sát ngưỡng:** Nếu người vẽ lỏng viền với $IoU = 0.51$ (vừa vặn nằm trên ngưỡng `iou_loose = 0.5`), hệ thống sẽ chấp nhận là box khớp tốt mà không cảnh báo `POSSIBLE_LOOSE_BOX`.

---

## 5. Train: raw vs clean (tùy chọn, chấm riêng)

Chưa chạy (Môi trường làm việc cục bộ là máy Windows không trang bị GPU; phần huấn luyện đối chứng mô hình YOLOv26n trên 20 epoch và 2 seed được chấm riêng 15 điểm và sẽ được thực hiện trên Google Colab theo đúng hướng dẫn tại `docs/COLAB.md`).

---

## 6. Quyết định và ghi chú AI

**(a) Quyết định cuối cùng:**
- Quyết định hiện tại: **`Hold`**.
- Với 193 ảnh, Release yêu cầu 0 lỗi bắt buộc và tối đa 19 ảnh còn cảnh báo chưa xử lý (19/193 < 10%). Hiện còn 34 ảnh, nên cần giải quyết cảnh báo trên ít nhất 15 ảnh rồi kiểm tra lại cả lô. Kết quả hiện tại vẫn là Hold theo ngân sách 80 ảnh và ngưỡng 10% của lab.

**(b) Ghi chú sử dụng AI:**
- **Prompt chính:** "Phân tích yêu cầu bài lab Day 09 theo tư duy TDD, xây dựng lần lượt 4 module label_format, gate, autofix, second_opinion; chú ý xử lý các trường hợp biên như file nhãn rỗng, chia cho 0, ưu tiên xoá dòng trước cắt box, và bảo toàn số dòng gốc."
- **Cách kiểm tra code AI:** Mở file test đối chiếu từng assert statement, chạy unit test riêng từng file sau mỗi thay đổi, soi kỹ code về mặt quản lý ngoại lệ (Exception Handling), kiểm tra tính bất biến của các file mẫu đề bài và đối chiếu chặt chẽ số liệu calibration thực tế.
- **Một lần AI đề xuất sai và cách khắc phục:** Trong module `gate.py`, AI ban đầu đề xuất làm tròn `round(warn_ratio, 4)` trước khi so sánh với ngưỡng `warn_ratio_hold`. Điều này tiềm ẩn nguy cơ làm tròn sớm (*Premature rounding bug*, ví dụ 200/2001 = 0.09995 bị làm tròn thành 0.1000 dẫn tới phán nhầm Hold). Em đã phát hiện và yêu cầu sửa lại: dùng tỉ lệ thô (`raw_ratio`) để so ngưỡng và chỉ làm tròn khi trả về kết quả trong dict.
