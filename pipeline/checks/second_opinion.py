"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★ (khó nhất, đáng điểm nhất)

Test:  pytest tests/test_second_opinion.py -q

Máy kiểm quy tắc, người kiểm ý nghĩa (slide). Các lỗi như thiếu nhãn / gán nhầm lớp hợp lệ / box lỏng
KHÔNG bắt được bằng quy tắc cú pháp. Ta nhờ một model mạnh hơn "nhìn lại" và CHỈ CẢNH BÁO (model cũng có thể sai):
những ảnh bị cờ sẽ vào hàng đợi cho NGƯỜI duyệt.

`preds[stem]` = list `[id_lớp, conf, cx, cy, w, h]` của model (lấy qua `get_preds(ds, cfg, "checker")` nếu preds=None).
`L = ds.valid_boxes(stem)` = list `(id_lớp, cx, cy, w, h)` của nhãn (đã bỏ dòng hỏng).
Ngưỡng ở `cfg["second_opinion"]`: conf, min_area_px, fp_conf, iou_missing, iou_match, iou_loose.

Thuật toán gợi ý, với từng ảnh (bỏ qua ảnh không có trong preds hoặc không có file nhãn):
  P = dự đoán có conf >= conf  VÀ diện tích px (w*W * h*H) >= min_area_px
  Với mỗi dự đoán r trong P: lấy các nhãn có IoU(r, nhãn) >= iou_missing  (cands)
   - không có cands                            -> POSSIBLE_MISSING     (model thấy vật mà nhãn không có box)
   - có cands cùng lớp, tốt nhất IoU < iou_loose -> POSSIBLE_LOOSE_BOX  (đúng vật, box lỏng/lệch)
   - không có cands cùng lớp, nhưng cands tốt nhất IoU >= iou_match (khác lớp) -> POSSIBLE_WRONG_CLASS
  Với mỗi dòng nhãn hợp lệ: nếu IoU với MỌI dự đoán (conf >= fp_conf, không lọc diện tích) đều < iou_missing
                                             -> POSSIBLE_FALSE_POS  (box nhãn không khớp vật nào model thấy; Issue.line = số dòng)

Chi tiết các ca biên (test kiểm đúng các ca này)
- `cands` gồm nhãn MỌI lớp có IoU >= iou_missing; "tốt nhất cùng lớp" = cands cùng lớp có IoU lớn nhất; "tốt nhất khác lớp" tương tự với cands khác lớp.
- Thứ tự quyết định cho mỗi dự đoán: (1) cands rỗng -> MISSING. (2) có cands cùng lớp: IoU tốt nhất < iou_loose -> LOOSE_BOX, ngược lại KHÔNG cờ
  (nhãn đúng lớp đã phủ vật này, kể cả khi còn nhãn khác lớp chồng lên). (3) không có cands cùng lớp: nếu IoU tốt nhất khác lớp >= iou_match -> WRONG_CLASS;
  nếu chỉ có khác lớp với IoU trong [iou_missing, iou_match) -> không cờ gì (mơ hồ: để cho FALSE_POS / lần duyệt khác).
- Một dự đoán sinh tối đa MỘT issue (MISSING / LOOSE_BOX / WRONG_CLASS); một ảnh có thể có nhiều issue.
- Thứ tự issue: theo `ds.image_files()` rồi theo thứ tự dự đoán trong `preds[stem]`, cuối cùng là các FALSE_POS theo số dòng; `Issue.image` = stem, `Issue.line` chỉ đặt cho FALSE_POS.

Lưu ý số dòng: dùng `ds.read_label_lines(stem)` (giữ số dòng gốc, kể cả dòng hỏng/trống) để lấy `Issue.line`; `valid_boxes` KHÔNG giữ số dòng.

Tất cả severity WARN; `Issue.extra` nên có {"conf": ...} hoặc {"iou": ...} (hàng đợi duyệt dùng conf để xếp ưu tiên).

Gợi ý
- `iou_xywh` có sẵn. Dòng nhãn hỏng không được làm script chết (dùng `ds.valid_boxes` và `parse_yolo_line` trong try).
- Kết quả phụ thuộc mạnh vào ngưỡng: calibrate chúng ở Bước 3 thay vì đoán.
"""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401
from ..model_cache import get_preds  # noqa: F401


def run(ds, cfg, preds=None) -> list[Issue]:
    if preds is None:
        preds = get_preds(ds, cfg, "checker")
    # Đọc trực tiếp từ config để không bị giá trị mặc định (fallback) đánh lừa khi calibration
    so_cfg = cfg["second_opinion"]
    conf_thresh = so_cfg["conf"]
    min_area_px = so_cfg["min_area_px"]
    fp_conf = so_cfg["fp_conf"]
    iou_missing = so_cfg["iou_missing"]
    iou_match = so_cfg["iou_match"]
    iou_loose = so_cfg["iou_loose"]
    issues: list[Issue] = []
    for img_path in ds.image_files():
        stem = img_path.stem
        # Bỏ qua ảnh không có trong preds hoặc không có file nhãn
        if stem not in preds or not ds.label_path(stem).exists():
            continue
        im_size = ds.image_size(stem)
        if not im_size:
            continue
        im_w, im_h = im_size
        # 1. Đọc các nhãn hợp lệ kèm số dòng gốc
        valid_labels: list[tuple[int, int, tuple[float, float, float, float]]] = []
        for line_no, raw_line in ds.read_label_lines(stem) or []:
            try:
                c, cx, cy, w, h = parse_yolo_line(raw_line)
            except ValueError:
                continue
            if 0 <= c < len(ds.classes):
                valid_labels.append((line_no, c, (cx, cy, w, h)))
        raw_preds = preds.get(stem, [])
        # 2. Chiều 1: Từ dự đoán của model soi sang nhãn
        # Lọc dự đoán tin cậy cao và diện tích đủ lớn
        P = [
            p for p in raw_preds
            if p[1] >= conf_thresh and (p[4] * im_w * p[5] * im_h) >= min_area_px
        ]
        for p in P:
            r_cls = int(p[0])
            r_conf = float(p[1])
            r_box = (float(p[2]), float(p[3]), float(p[4]), float(p[5]))
            # Tìm các nhãn có IoU >= iou_missing
            cands = [
                lbl for lbl in valid_labels
                if iou_xywh(r_box, lbl[2]) >= iou_missing
            ]
            # (1) Không có nhãn nào -> Nghi bỏ sót
            if not cands:
                issues.append(
                    Issue(
                        "second_opinion",
                        WARN,
                        "POSSIBLE_MISSING",
                        stem,
                        f"Model phát hiện vật lớp {r_cls} nhưng nhãn thiếu box",
                        line=None,
                        extra={"conf": r_conf},
                    )
                )
                continue
            # (2) Có nhãn cùng lớp
            same_cands = [c for c in cands if c[1] == r_cls]
            if same_cands:
                best_same_iou = max(iou_xywh(r_box, c[2]) for c in same_cands)
                if best_same_iou < iou_loose:
                    issues.append(
                        Issue(
                            "second_opinion",
                            WARN,
                            "POSSIBLE_LOOSE_BOX",
                            stem,
                            f"Box lỏng/lệch (IoU={best_same_iou:.3f} < {iou_loose})",
                            line=None,
                            extra={"conf": r_conf, "iou": best_same_iou},
                        )
                    )
                continue
            # (3) Không có cùng lớp -> Xét khác lớp
            diff_cands = [c for c in cands if c[1] != r_cls]
            if diff_cands:
                best_diff_iou = max(iou_xywh(r_box, c[2]) for c in diff_cands)
                if best_diff_iou >= iou_match:
                    issues.append(
                        Issue(
                            "second_opinion",
                            WARN,
                            "POSSIBLE_WRONG_CLASS",
                            stem,
                            f"Nghi ngờ sai lớp (IoU={best_diff_iou:.3f} >= {iou_match})",
                            line=None,
                            extra={"conf": r_conf, "iou": best_diff_iou},
                        )
                    )
        # 3. Chiều 2: Từ nhãn soi sang dự đoán (bắt False Positive)
        fp_preds = [p for p in raw_preds if p[1] >= fp_conf]
        for line_no, lbl_cls, lbl_box in valid_labels:
            matched = False
            for p in fp_preds:
                p_box = (float(p[2]), float(p[3]), float(p[4]), float(p[5]))
                if iou_xywh(lbl_box, p_box) >= iou_missing:
                    matched = True
                    break
            if not matched:
                issues.append(
                    Issue(
                        "second_opinion",
                        WARN,
                        "POSSIBLE_FALSE_POS",
                        stem,
                        f"Dòng {line_no}: Nhãn không khớp với dự đoán nào của model",
                        line=line_no,
                        extra={},
                    )
                )
    return issues
