"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict  # noqa: F401

import yaml  # noqa: F401

from ..common import ERROR, parse_yolo_line  # noqa: F401


DROP_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}


def _is_remove(code):
    return code.startswith("DUP_IMAGE") or code in {"LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}


def _clip(line):
    """Cắt box về [0,1]. Trả về dòng mới, hoặc None nếu box không còn diện tích (hoặc dòng không parse được)."""
    try:
        c, x, y, w, h = parse_yolo_line(line)
    except ValueError:
        return None
    x1, y1 = max(0.0, x - w / 2), max(0.0, y - h / 2)
    x2, y2 = min(1.0, x + w / 2), min(1.0, y + h / 2)
    if x2 - x1 <= 0 or y2 - y1 <= 0:
        return None
    return f"{c} {(x1 + x2) / 2:.6f} {(y1 + y2) / 2:.6f} {x2 - x1:.6f} {y2 - y1:.6f}"


def fix(ds, issues, cfg):
    fixes = []

    def log(image, line, action, before, after):
        fixes.append({"image": image, "line": line, "action": action, "before": before, "after": after})

    errors = [i for i in issues if i.severity == ERROR]

    # 1) Xoá ảnh trước: issue dòng của ảnh đã xoá sẽ bị bỏ qua êm ở bước sau.
    removed = set()
    for i in errors:
        if _is_remove(i.code) and i.image not in removed:
            removed.add(i.image)
            paths = [p for p in ds.image_files() if p.stem == i.image]
            before = ", ".join(p.name for p in paths) or i.image
            for p in paths:
                p.unlink()
            lp = ds.label_path(i.image)
            if lp.exists():
                lp.unlink()
            log(i.image, None, "remove_image", before, f"(đã xoá: {i.code})")

    # 2) Sửa data.yaml
    if any(i.code == "BAD_CLASS_NAME" for i in errors):
        before = [ds.yaml_names().get(k) for k in range(len(cfg["classes"]))]
        d = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
        d["names"] = {k: n for k, n in enumerate(cfg["classes"])}
        ds.yaml_path.write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8")
        log("data.yaml", None, "rename_classes", str(before), str(list(cfg["classes"])))

    # 3) Ảnh thiếu file nhãn: chuyển người, không bịa nhãn
    seen_missing = set()
    for i in errors:
        if i.code == "MISSING_LABEL_FILE" and i.image not in removed and i.image not in seen_missing:
            seen_missing.add(i.image)
            log(i.image, None, "needs_label", "(không có file)", "chuyển người gán")

    # 4) Lỗi theo dòng: gom theo file, dùng số dòng GỐC, ghi lại MỘT lần
    by_file = defaultdict(lambda: defaultdict(set))   # stem -> line_no -> {codes}
    for i in errors:
        if i.line is not None and i.image not in removed and (i.code in DROP_CODES or i.code == "BOX_OUT_OF_IMAGE"):
            by_file[i.image][i.line].add(i.code)

    for stem, per_line in by_file.items():
        p = ds.label_path(stem)
        if not p.exists():
            continue
        orig = p.read_text(encoding="utf-8", errors="replace").splitlines()
        out = []
        for no, ln in enumerate(orig, 1):
            codes = per_line.get(no)
            if not ln.strip():
                continue                                   # dòng trống không mang nhãn
            if not codes:
                out.append(ln)
            elif codes & DROP_CODES:
                log(stem, no, "drop_line", ln.strip(), "(đã xoá)")
            else:                                          # chỉ BOX_OUT_OF_IMAGE
                new = _clip(ln)
                if new is None:
                    log(stem, no, "drop_line", ln.strip(), "(đã xoá: box nằm ngoài ảnh)")
                else:
                    out.append(new)
                    log(stem, no, "clip_box", ln.strip(), new)
        p.write_text("".join(x + "\n" for x in out), encoding="utf-8")
    return fixes
