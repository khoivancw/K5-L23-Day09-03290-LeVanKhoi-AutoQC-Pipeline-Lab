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
    issues = []
    #BAD_FORMAT 
    for path in ds.label_files():
        stem = path.stem  # "a.txt" -> "a"
        valid_boxes = []
        for line_no, text in ds.read_label_lines(stem) or []:
            try:
                class_id, cx, cy, w, h = parse_yolo_line(text)
            except ValueError as err:
                issues.append(
                    Issue("label_format", ERROR, "BAD_FORMAT", stem, str(err), line=line_no)
                )
                continue

            #2 BAD_CLASS_ID 
            if class_id < 0 or class_id >= len(ds.classes):
                issues.append(
                    Issue("label_format", ERROR, "BAD_CLASS_ID", stem, f"ID lớp ngoài dải: {class_id}", line=line_no)
                )
                continue 
            # 3. Kiểm tra box rỗng/kích thước <= 0 BOX_ZERO   
            if w <= 0 or h <= 0:
                issues.append(
                    Issue("label_format", ERROR, "BOX_ZERO", stem, f"Box kích thước <= 0 (w={w}, h={h})", line=line_no)
                )
                continue 
            # 4. Kiểm tra box tràn ảnh (BOX_OUT_OF_IMAGE)
            overflow_tol = cfg.get("label_format", {}).get("overflow_tol", 0.001)
            x1, y1 = cx - w / 2.0, cy - h / 2.0
            x2, y2 = cx + w / 2.0, cy + h / 2.0
            overflow = max(0.0, -x1, -y1, x2 - 1.0, y2 - 1.0)

            if overflow > overflow_tol:
                issues.append(
                    Issue(
                        "label_format",
                        ERROR,
                        "BOX_OUT_OF_IMAGE",
                        stem,
                        f"Box tràn ảnh {overflow:.4f} > {overflow_tol}",
                        line=line_no,
                        extra={"overflow": overflow},
                    )
                )
            # 5. Kiểm tra trùng lặp box (DUP_BOX)
            dup_box_iou = cfg.get("label_format", {}).get("dup_box_iou", 0.8)
            current_geom = (cx, cy, w, h)
            for prev_cls, prev_geom in valid_boxes:
                if class_id == prev_cls:
                    if iou_xywh(current_geom, prev_geom) > dup_box_iou:
                        issues.append(
                            Issue(
                                "label_format",
                                ERROR,
                                "DUP_BOX",
                                stem,
                                f"Trùng box với dòng trước (IoU > {dup_box_iou})",
                                line=line_no,
                            )
                        )
                        break

            # Lưu box hiện tại vào danh sách để so sánh với các dòng tiếp theo
            valid_boxes.append((class_id, current_geom))
            # 6. Cảnh báo box quá nhỏ (BOX_TINY)
            min_box_px = cfg.get("label_format", {}).get("min_box_px", 12)
            im_size = ds.image_size(stem)
            if im_size:
                im_w, im_h = im_size
                short_edge_px = min(w * im_w, h * im_h)
                if short_edge_px < min_box_px:
                    issues.append(
                        Issue(
                            "label_format",
                            WARN,
                            "BOX_TINY",
                            stem,
                            f"Box quá nhỏ ({short_edge_px:.1f}px < {min_box_px}px)",
                            line=line_no,
                        )
                    )

            # 7. Cảnh báo box quá to (BOX_HUGE)
            max_box_frac = cfg.get("label_format", {}).get("max_box_frac", 0.85)
            if w * h > max_box_frac:
                issues.append(
                    Issue(
                        "label_format",
                        WARN,
                        "BOX_HUGE",
                        stem,
                        f"Box chiếm diện tích {w * h:.3f} > {max_box_frac}",
                        line=line_no,
                    )
                )
    return issues
