# So sánh huấn luyện raw và clean

Cùng YOLO26n, 20 epoch, batch 16, ảnh đầu vào 640 px, seed 0 và 1, các lần chạy dùng CPU và cùng tập đánh giá 100 ảnh.

## 1. Mức cải thiện và độ dao động

mAP50 trung bình tăng từ 0,71265 lên 0,72735 (+0,01470). Chênh lệch theo từng cặp seed là +0,0139 và +0,0155. Cả hai đều tăng, nhưng độ tăng chỉ cùng cỡ độ lệch chuẩn giữa seed (raw 0,011, clean 0,012). Hai seed cho thấy xu hướng trên lô này, chưa đủ để khẳng định hiệu quả ổn định. Precision tăng từ 0,714 lên 0,813, còn recall giảm từ 0,666 xuống 0,609 và mAP50–95 giảm từ 0,508 xuống 0,502.

## 2. Số ảnh thực dùng

Script ghi 224 ảnh đầu vào cho raw. Log quét tập train ở cell 6 ghi 11 ảnh bị Ultralytics đánh dấu corrupt trong 224 ảnh, còn 213 ảnh có thể dùng. Mục backgrounds vẫn được tính trong dữ liệu train. Clean có 193 ảnh, không có ảnh bị loại ở lần quét này.

## 3. Rò rỉ sang tập test

01_intake.csv ghi 11 ảnh raw bị gắn LEAK_TEST, cả 11 đối chiếu với file trong test. Kết quả hiện tại chưa tách được mức ảnh hưởng của rò rỉ vì clean đồng thời thay đổi cả ảnh và nhãn. Để ước lượng, xác minh từng cặp trùng, đối chiếu với danh sách ảnh thật sự được dùng để train, rồi huấn luyện lại raw chỉ loại các ảnh trùng test. Giữ nguyên nhãn còn lại, seed, cấu hình và tập test. Chênh lệch mAP50 theo từng seed sẽ ước lượng mức ảnh hưởng.

## 4. AP50 theo lớp

| Lớp | Raw trung bình | Clean trung bình | Clean − raw |
|---|---:|---:|---:|
| car | 0,74975 | 0,77790 | +0,02815 |
| person | 0,82040 | 0,81770 | −0,00270 |
| truck | 0,59750 | 0,61065 | +0,01315 |
| bus | 0,68295 | 0,70320 | +0,02025 |

Car tăng nhiều nhất theo trung bình. Tuy nhiên seed 0 giảm 0,0142 còn seed 1 tăng 0,0705. Báo cáo QC ban đầu ghi 53 cảnh báo nghi thiếu vật và 17 cảnh báo nghi sai lớp trên cả lô. Sửa hai loại lỗi này có thể giúp model nhận diện car. Để kiểm tra giả thuyết, cần đối chiếu các ảnh đã duyệt với nhãn car trước và sau sửa vì số cảnh báo trong bảng chưa phân theo lớp.

## 5. Giới hạn của clean

Hàng đợi có 121 ảnh, ngân sách duyệt mô phỏng là 80 nên còn 41 ảnh chưa duyệt. Gate ghi 0 lỗi bắt buộc và 34/193 ảnh còn cảnh báo (17,62%), kết luận Hold. Một cảnh báo cần được xác minh trên ảnh. Bộ clean hiện tại là bản đã qua QC trong ngân sách này. Để ước lượng hiệu quả khi nhãn sạch hơn, có thể duyệt độc lập toàn bộ lô rồi lặp lại phép so sánh.
