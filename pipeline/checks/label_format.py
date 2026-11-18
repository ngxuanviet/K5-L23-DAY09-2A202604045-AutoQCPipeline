"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401


def run(ds, cfg):
    c = cfg["label_format"]
    n_classes = len(ds.classes)
    issues = []

    def add(sev, code, stem, msg, line, **extra):
        issues.append(Issue("label_format", sev, code, stem, msg, line=line, extra=extra))

    for lf in ds.label_files():
        stem = lf.stem
        size = None            # chỉ mở ảnh khi thật sự cần (BOX_TINY)
        size_loaded = False
        seen = []              # [(id, cx, cy, w, h)] các dòng hợp lệ ĐÃ duyệt, để so trùng
        for no, ln in ds.read_label_lines(stem) or []:
            try:
                cid, x, y, w, h = parse_yolo_line(ln)
            except ValueError as e:
                add(ERROR, "BAD_FORMAT", stem, f"dòng không đúng 5 cột số ({e}): {ln.strip()[:60]}", no)
                continue
            if not 0 <= cid < n_classes:
                add(ERROR, "BAD_CLASS_ID", stem, f"id lớp {cid} ngoài 0..{n_classes - 1}", no, class_id=cid)
                continue
            if w <= 0 or h <= 0:
                add(ERROR, "BOX_ZERO", stem, f"box rỗng (w={w}, h={h})", no)
                continue

            overflow = max(0.0, -(x - w / 2), (x + w / 2) - 1.0, -(y - h / 2), (y + h / 2) - 1.0)
            if overflow > c["overflow_tol"]:
                add(ERROR, "BOX_OUT_OF_IMAGE", stem, f"box tràn ảnh {overflow:.4f}", no, overflow=overflow)

            box = (x, y, w, h)
            if any(p[0] == cid and iou_xywh(p[1:], box) > c["dup_box_iou"] for p in seen):
                add(ERROR, "DUP_BOX", stem, "box lặp với một dòng trước đó (cùng lớp)", no)
            seen.append((cid, *box))

            if w * h > c["max_box_frac"]:
                add(WARN, "BOX_HUGE", stem, f"box chiếm {w * h:.0%} diện tích ảnh", no, frac=w * h)

            if not size_loaded:
                size, size_loaded = ds.image_size(stem), True
            if size is not None:
                short_px = min(w * size[0], h * size[1])
                if short_px < c["min_box_px"]:
                    add(WARN, "BOX_TINY", stem, f"cạnh ngắn của box chỉ {short_px:.1f}px", no, short_px=short_px)
    return issues
