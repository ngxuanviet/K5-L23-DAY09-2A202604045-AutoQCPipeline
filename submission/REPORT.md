# Báo cáo Day 09 — Nguyễn Xuân Việt, 2A202604045

## 1. Kết luận trước
Pipeline kết luận **Hold** (mã thoát 10). Vào 224 ảnh; cổng vào loại 22 ảnh (3 `BAD_SIZE`, 2 `CORRUPT_IMAGE`, 8 `DUP_IMAGE_EXACT`, 4 `DUP_IMAGE_NEAR`, 5 `LEAK_TEST`), còn **202 ảnh** vào dataset nháp `export/clean_v1` (không phải bản phát hành).
Lý do: không còn lỗi bắt buộc (0 ERROR sau sửa tự động + người duyệt), nhưng **38/202 ảnh (18,8%)** còn cảnh báo chưa được người duyệt, ≥ ngưỡng 10% của gate.

## 2. Lỗi và phân việc
Lấy từ `02_error_list_v1` (lô 224 ảnh trước khi loại/sửa).

| Mã lỗi | Số ảnh/dòng | Ai sửa | Vì sao |
|---|---:|---|---|
| `CORRUPT_IMAGE`, `BAD_SIZE` | 2 + 3 ảnh | máy (loại ảnh) | luật rõ ràng, không cứu được |
| `DUP_IMAGE_EXACT`, `DUP_IMAGE_NEAR` | 8 + 4 ảnh | máy (loại ảnh) | trùng byte / phash ≤ 10 |
| `LEAK_TEST` | 5 ảnh | máy (loại ảnh) | trùng ảnh kho test/val, giữ lại làm hỏng phép đo |
| `BAD_FORMAT`, `BAD_CLASS_ID`, `BOX_ZERO`, `DUP_BOX` | 3 + 6 + 4 + 7 = 20 dòng | máy (xoá dòng) | lỗi cú pháp, không có nghĩa để sửa |
| `BOX_OUT_OF_IMAGE` | 8 dòng | máy (cắt về [0,1]) | giữ nguyên lớp, chỉ sửa hình học |
| `BAD_CLASS_NAME` | 1 `data.yaml` | máy | ghi lại tên lớp theo cấu hình |
| `MISSING_LABEL_FILE` | 6 ảnh | **người** | máy không được bịa nhãn; 6 ảnh này đứng đầu hàng đợi |
| `POSSIBLE_MISSING` / `WRONG_CLASS` / `LOOSE_BOX` / `FALSE_POS` | 52 / 18 / 24 / 27 ảnh (128 cảnh báo) | **người** | cần hiểu ý nghĩa; model lớn cũng có thể sai |
| `BOX_TINY`, `BOX_HUGE`, `EMPTY_LABEL` | 4 / 3 / 12 ảnh | **người** | cảnh báo, không tự sửa |

Hàng đợi `05_review_queue.csv` có 125 ảnh, xếp theo tổng trọng số của các mã trong `configs/pipeline.yaml`: đầu bảng là `img_0020` (điểm 11,5: vừa bị xoá dòng, vừa `POSSIBLE_MISSING`, vừa `POSSIBLE_WRONG_CLASS`), kế đó 6 ảnh `NEEDS_LABEL` (điểm 10), rồi các ảnh nhiều cảnh báo ngữ nghĩa. Ngân sách 80 ảnh duyệt hết 80/125, còn **45 ảnh chưa ai xem**. Cảnh báo ngữ nghĩa giảm từ 128 (v1) xuống 57 (v3: 21 FALSE_POS, 20 LOOSE_BOX, 13 MISSING, 3 WRONG_CLASS).

## 3. Calibration (2 ngưỡng)
Kết quả đầy đủ ở `submission/calibration/calibration_report.md`.

| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | **10** | `DUP_IMAGE_NEAR`: 1,00 / 0,50 → 1,00 / 0,67 | cờ này tự xoá ảnh nên ưu tiên precision; 4–14 cùng 1,00 / 0,67, chọn giữa vùng phẳng |
| `second_opinion.conf` | 0.25 | **0.6** | `MISSING` 0,50 / 1,00 → 0,57 / 1,00; `WRONG_CLASS` 0,56 / 0,83 → 0,62 / 0,83; `LOOSE_BOX` 0,29 / 0,40 → 0,20 / 0,20; `FALSE_POS` không đổi 0,31 / 1,00 | giữ recall `MISSING` = 1,00. Từ 0,7 recall tụt (0,88 rồi 0,75 ở 0,8): hàng đợi gọn hơn nhưng bỏ sót ảnh thiếu nhãn |

**Chỗ calibration có thể đánh lừa:** `phash_dist = 16` có recall `NEAR` cao nhất trên calib (0,83) nhưng trên raw nó loại 4 ảnh nhiều hơn mức 10, và khi mở xem từng cặp thì 2 cặp là ảnh **khác nhau** (người đánh tennis vs người trượt tuyết; người lướt sóng vs người ngồi bàn): xoá nhầm ảnh tốt. Calib chỉ 39 ảnh nên một cặp trùng thêm làm recall nhảy 0,67 → 0,83. Tương tự `LOOSE_BOX` chỉ có 5 lỗi chèn: recall chạy 0,60 → 0,20 chỉ vì 2 lỗi, nên không đủ cơ sở chọn `conf` theo cột này.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
**(a) Gate chặn đúng.** `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb` (không có người duyệt, 6 ảnh thiếu file nhãn còn nguyên): kết luận **Rework**, mã thoát **20**, còn 6 lỗi bắt buộc (`MISSING_LABEL_FILE`), và **không xuất** dataset (`work/exp_nb/clean_v1` không tồn tại). Với ngân sách 80, người duyệt gán nhãn cho 6 ảnh đó nên chạy chính thức không còn lỗi bắt buộc.

**(b) Điểm mù có bằng chứng.**
1. *Ảnh trùng quá ngưỡng:* `img_0084` và `img_0074` là cùng một ảnh (khác phash 16) nhưng cả hai vẫn nằm trong `export/clean_v1` vì ngưỡng 10; hạ ngưỡng xuống 16 thì xoá nhầm ảnh khác (mục 3). Không có ngưỡng phash nào tách được hai trường hợp này.
2. *Ca mơ hồ về ngữ nghĩa:* `img_0155` có box người nhưng đó là hình trên màn hình TV. Máy chỉ so với model (cũng thấy "người"), không có cách biết ngữ cảnh; chỉ người quyết được.
3. *Box lỏng nhẹ:* `POSSIBLE_LOOSE_BOX` trên calib chỉ đạt precision/recall 0,20 / 0,20 ở `conf` đã chọn, và v3 vẫn còn 20 cảnh báo loại này: phần lớn box lỏng không bị bắt.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Train trên Colab T4: `yolo26n.pt`, 20 epoch, batch 16, imgsz 640, seed 0 và 1; cùng val (`gold_val`, 40 ảnh) và test (`data/test`, 100 ảnh, nhãn người). Chi tiết ở `submission/results/ANALYSIS.md`.

| biến thể | #ảnh train | seed | mAP50 (TB ± độ lệch) | mAP50-95 | precision | recall |
|---|---:|---:|---|---|---|---|
| raw | 224 | 2 | 0.726 ± 0.000 | 0.512 ± 0.004 | 0.764 ± 0.061 | 0.649 ± 0.028 |
| clean | 202 | 2 | 0.701 ± 0.025 | 0.487 ± 0.008 | 0.759 ± 0.003 | 0.625 ± 0.019 |

`raw` ghi 224 ảnh nhưng Ultralytics tự bỏ 11 ảnh (id lớp lạ, giá trị âm, toạ độ ngoài ảnh, ảnh hỏng/cắt cụt), nên thực sự train trên **213 ảnh**; `clean` train đủ 202 ảnh, không ảnh nào bị bỏ.

Chênh mAP50 (clean − raw) = **−0,025**, xấp xỉ **một độ lệch chuẩn giữa các seed của clean** (0,025; hai seed clean là 0,718 và 0,683). Với 2 seed và test 100 ảnh, **không kết luận được** `clean` tốt hơn hay kém hơn `raw`; chỉ có thể nói `clean` không cho thấy cải thiện.

Theo lớp (AP50 trung bình 2 seed, raw → clean): car 0,738 → 0,738; person 0,822 → 0,823; bus 0,695 → 0,703; **truck 0,648 → 0,538**. Toàn bộ chênh lệch nằm ở lớp truck (hiếm nhất: 32 box trong nhãn raw, 41/748 box trong clean), và dao động mạnh giữa hai seed của clean (0,590 vs 0,486).

Giả thuyết: (1) `raw` bị thổi phồng vì 5 ảnh `LEAK_TEST` trùng với ảnh test (cả 5 đều không nằm trong 11 ảnh bị bỏ nên vẫn được train) và 12 ảnh trùng khác cùng nằm trong train, trong khi `clean` đã loại hết; (2) `clean` mất 22/224 ảnh, trong đó có ảnh chứa truck, nên lớp hiếm nhất chịu thiệt nhiều nhất; (3) `clean` vẫn còn 38 ảnh cảnh báo ngữ nghĩa chưa duyệt (nhãn máy, 18,8%), nên chưa phải "dữ liệu sạch" thật. Cách kiểm: huấn luyện lại `raw` sau khi bỏ 5 ảnh rò rỉ (so với `raw` gốc), và tăng số seed (≥ 5) để ước lượng nhiễu của truck.

## 6. Quyết định và ghi chú AI
**(a) Quyết định cuối: Hold.** Dataset `clean_v1` là bản nháp, chưa được phát hành. Muốn thành Release cần ≤ 10% ảnh còn cảnh báo, tức ≤ 20/202: hiện 38, nên phải để người duyệt thêm **ít nhất khoảng 18 ảnh** trong 45 ảnh chưa duyệt (nâng ngân sách từ 80 lên ≥ 98), ưu tiên `POSSIBLE_FALSE_POS` và `POSSIBLE_LOOSE_BOX`. Hạ `conf` xuống 0,8 cũng cho Release (7,9%) nhưng đổi bằng việc bỏ sót thêm ảnh thiếu nhãn (recall `MISSING` 1,00 → 0,75): tôi không chọn cách đó.

**(b) Ghi chú AI.** Có dùng Claude Code để viết 4 module từ docstring + test của đề và để chạy sweep calibration.
- *Prompt chính:* "làm từng bước bài này", sau đó từng module theo thứ tự `label_format` → `gate` → `autofix` → `second_opinion`.
- *Cách kiểm:* chạy `pytest` (79 test xanh), chạy script thử thêm các ca ngoài test (dòng dính 2 lỗi, dòng trống giữa file, nhiều dự đoán/ảnh), chạy lại `pipeline.run` từ đầu và mở xem các cặp ảnh bị coi là trùng.
- *Một lần sai/suýt sai:* theo bảng calibration, `phash_dist = 16` trông tốt nhất (recall cao nhất); chỉ khi mở ảnh mới thấy nó xoá nhầm ảnh khác nhau, nên đã chọn 10.
