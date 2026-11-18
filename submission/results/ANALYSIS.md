# Phân tích kết quả train: raw vs clean

Cấu hình (giống nhau cho cả hai): `yolo26n.pt`, 20 epoch, batch 16, imgsz 640, seed 0 và 1, val = `gold_val` (40 ảnh), test = `data/test` (100 ảnh, nhãn người). Chỉ khác dữ liệu train: `raw` = 224 ảnh nhãn gốc; `clean` = 202 ảnh sau pipeline (`export/clean_v1`, quyết định Hold, bản nháp).

| biến thể | seed 0 mAP50 | seed 1 mAP50 | TB ± độ lệch |
|---|---:|---:|---|
| raw | 0.7256 | 0.7259 | 0.726 ± 0.000 |
| clean | 0.7180 | 0.6832 | 0.701 ± 0.025 |

## 1. Chênh lệch so với nhiễu giữa các seed
mAP50(clean) − mAP50(raw) = −0,025. Độ lệch chuẩn giữa hai seed của clean là 0,025 (của raw ≈ 0), nên chênh lệch chỉ cỡ **một độ lệch chuẩn**. Chỉ có 2 seed mỗi biến thể và test chỉ 100 ảnh, nên không kết luận được. Độ lệch ≈ 0 của raw chỉ là trùng hợp của 2 seed, không có nghĩa raw ổn định hơn.

## 2. `raw` thực sự train trên bao nhiêu ảnh?
`train_images` ghi 224, nhưng Ultralytics tự bỏ **11 ảnh** khi quét nhãn (log ô 6: `216 images, 19 backgrounds, 11 corrupt`, rồi `Using 213 train`), nên `raw` thực sự train trên **213 ảnh**. 11 ảnh bị bỏ là: `img_0010` (không mở được), `img_0136` (ảnh cắt cụt), `img_0020` (id lớp 93), `img_0104` (id 7), `img_0194` và `img_0199` (id 4), `img_0099` và `img_0117` (giá trị âm), `img_0014` và `img_0022` (toạ độ ngoài [0,1]), `img_0179` (dòng thiếu cột). `clean` không có ảnh nào bị bỏ (`202 images, 4 backgrounds, 0 corrupt`), train trên đủ 202 ảnh. Ngoài ra Ultralytics coi 19 ảnh của `raw` là ảnh nền (không có nhãn: file nhãn rỗng hoặc thiếu), so với 4 ảnh của `clean`, nên `raw` còn dạy model rằng nhiều ảnh không có vật nào.

## 3. `raw` có trùng ảnh với test không?
Có (và cả 5 đều **không** nằm trong 11 ảnh bị Ultralytics bỏ ở mục 2, nên vẫn được train): 5 ảnh (`img_0049`, `img_0101`, `img_0167`, `img_0174`, `img_0221`) trùng với `test/test_033`, `test_039`, `test_044`, `test_085`, `test_009` (`01_intake.csv`, mã `LEAK_TEST`), cộng 12 ảnh trùng nhau trong chính raw. Điểm của raw bị thổi phồng bao nhiêu thì **chưa đo**. Cách kiểm: train lại raw sau khi bỏ 5 ảnh rò rỉ, hoặc tính mAP trên test đã loại 5 ảnh tương ứng, rồi so với kết quả hiện tại.

## 4. Lớp nào được lợi / bị hại
AP50 trung bình 2 seed (raw → clean): car 0,738 → 0,738; person 0,822 → 0,823; bus 0,695 → 0,703; **truck 0,648 → 0,538**. Gần như mọi chênh lệch đến từ truck: lớp hiếm nhất (32 box trong nhãn raw; 41/748 box trong clean theo `class_stats.csv`, tức clean có nhiều box truck hơn mà AP vẫn thấp hơn), và trong clean dao động mạnh giữa hai seed (0,590 và 0,486). Với lớp ít mẫu và test nhỏ, AP của truck rất nhạy, nên chưa chắc đây là tác động thật của dữ liệu.

## 5. `clean` còn lỗi gì?
Không còn lỗi bắt buộc, nhưng pipeline kết luận Hold: 38/202 ảnh (18,8%) còn cảnh báo ngữ nghĩa (21 `FALSE_POS`, 20 `LOOSE_BOX`, 13 `MISSING`, 3 `WRONG_CLASS`), và hàng đợi 125 ảnh vượt ngân sách duyệt 80 (45 ảnh chưa duyệt). Nên `clean` chưa phải chặn trên của "dữ liệu sạch": nhãn của nó vẫn là nhãn model + máy sửa, chưa được người xác nhận hết.

## Kết luận
Không có bằng chứng rằng dữ liệu sau pipeline cho model tốt hơn (mAP50 giảm 0,025, trong phạm vi nhiễu của 2 seed). Việc tiếp theo: tăng số seed (≥ 5), kiểm tác động của 5 ảnh rò rỉ trong test, và cho người duyệt hết hàng đợi rồi train lại để kiểm "clean" thật sự.
