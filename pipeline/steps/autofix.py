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

REMOVE_IMAGE_CODES = {"DUP_IMAGE_EXACT", "DUP_IMAGE_PHASH", "LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}
DROP_LINE_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}

def fix(ds, issues, cfg) -> list[dict]:
    fixes: list[dict] = []
    # Chỉ lọc các lỗi bắt buộc (ERROR), không đụng vào WARN
    error_issues = [i for i in issues if i.severity == ERROR]
    # 1. Cập nhật tên lớp trong data.yaml (không nuốt lỗi để tránh ghi đè làm mất các trường khác)
    bad_class_name_issues = [i for i in error_issues if i.code == "BAD_CLASS_NAME"]
    if bad_class_name_issues and ds.yaml_path.exists():
        yaml_data = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
        before_names = str(yaml_data.get("names", []))
        yaml_data["names"] = list(cfg.get("classes", []))
        ds.yaml_path.write_text(yaml.safe_dump(yaml_data, allow_unicode=True), encoding="utf-8")
        fixes.append({
            "image": "data.yaml",
            "line": "",
            "action": "rename_classes",
            "before": before_names,
            "after": str(cfg.get("classes", [])),
        })
    # 2. Xoá ảnh rác (Chỉ ghi nhận fix khi xoá thực sự thành công)
    removed_images: set[str] = set()
    for iss in error_issues:
        if iss.code.startswith("DUP_IMAGE") or iss.code in REMOVE_IMAGE_CODES:
            stem = iss.image
            if stem not in removed_images:
                removed_images.add(stem)
                img_p = ds.image_path(stem)
                if img_p and img_p.exists():
                    img_p.unlink()
                lbl_p = ds.label_path(stem)
                if lbl_p and lbl_p.exists():
                    lbl_p.unlink()
                fixes.append({
                    "image": stem,
                    "line": "",
                    "action": "remove_image",
                    "before": iss.code,
                    "after": "removed",
                })
    # 3. Ghi nhận ảnh thiếu file nhãn (KHÔNG BỊA FILE NHÃN RỖNG)
    for iss in error_issues:
        if iss.code == "MISSING_LABEL_FILE":
            if iss.image not in removed_images:
                fixes.append({
                    "image": iss.image,
                    "line": "",
                    "action": "needs_label",
                    "before": "(không có file)",
                    "after": "chuyển người gán",
                })
    # 4. Gom các lỗi cấp dòng theo từng ảnh (bỏ qua ảnh đã bị xoá)
    line_issues_by_stem: dict[str, list] = defaultdict(list)
    for iss in error_issues:
        if iss.line is not None and iss.image not in removed_images and iss.image not in ("data.yaml", "<dataset>"):
            line_issues_by_stem[iss.image].append(iss)
    for stem, stem_issues in line_issues_by_stem.items():
        lbl_p = ds.label_path(stem)
        if not lbl_p.exists():
            continue
        raw_content = lbl_p.read_text(encoding="utf-8", errors="replace")
        file_lines = raw_content.splitlines()
        # Gom lỗi theo từng số dòng gốc (1-based line number)
        issues_per_line: dict[int, list] = defaultdict(list)
        for iss in stem_issues:
            issues_per_line[iss.line].append(iss)
        new_file_lines: list[str] = []
        for line_no in range(1, len(file_lines) + 1):
            raw_line = file_lines[line_no - 1]
            cur_issues = issues_per_line.get(line_no, [])
            if not cur_issues:
                # Dòng sạch -> giữ nguyên
                new_file_lines.append(raw_line)
                continue
            issue_codes = {i.code for i in cur_issues}
            # Ưu tiên số 1: Xoá dòng luôn thắng cắt box
            if any(c in DROP_LINE_CODES for c in issue_codes):
                fixes.append({
                    "image": stem,
                    "line": line_no,
                    "action": "drop_line",
                    "before": raw_line,
                    "after": "",
                })
                continue
            # Ưu tiên số 2: Nắn box tràn viền về [0.0, 1.0]
            if "BOX_OUT_OF_IMAGE" in issue_codes:
                try:
                    c, cx, cy, w, h = parse_yolo_line(raw_line)
                    x1, y1 = cx - w / 2.0, cy - h / 2.0
                    x2, y2 = cx + w / 2.0, cy + h / 2.0
                    nx1, nx2 = max(0.0, min(1.0, x1)), max(0.0, min(1.0, x2))
                    ny1, ny2 = max(0.0, min(1.0, y1)), max(0.0, min(1.0, y2))
                    nw, nh = nx2 - nx1, ny2 - ny1
                    # Đúng chuẩn toán học: nếu không còn diện tích (<= 0) thì xoá dòng
                    if nw <= 0 or nh <= 0:
                        fixes.append({
                            "image": stem,
                            "line": line_no,
                            "action": "drop_line",
                            "before": raw_line,
                            "after": "",
                        })
                    else:
                        ncx, ncy = (nx1 + nx2) / 2.0, (ny1 + ny2) / 2.0
                        clipped_line = f"{c} {ncx:.6f} {ncy:.6f} {nw:.6f} {nh:.6f}"
                        fixes.append({
                            "image": stem,
                            "line": line_no,
                            "action": "clip_box",
                            "before": raw_line,
                            "after": clipped_line,
                        })
                        new_file_lines.append(clipped_line)
                except Exception:
                    fixes.append({
                        "image": stem,
                        "line": line_no,
                        "action": "drop_line",
                        "before": raw_line,
                        "after": "",
                    })
            else:
                new_file_lines.append(raw_line)
        # Ghi lại file nhãn đã được sửa
        if new_file_lines:
            lbl_p.write_text("\n".join(new_file_lines) + "\n", encoding="utf-8")
        else:
            lbl_p.write_text("", encoding="utf-8")
    return fixes