#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
yolo_tool.py — YOLOv8n 目标检测命令行工具
被 Hermes（通过 MCP）或直接命令行调用，输出 JSON 格式的检测结果。

用法:
    python3 yolo_tool.py <图片路径> [--model yolov8n.pt] [--conf 0.25]
    python3 yolo_tool.py camera:0            # 从摄像头捕获一帧并检测
"""
import argparse
import json
import os
import sys

MODEL_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "yolov8n.pt")


def detect(image_path: str, model_path: str = MODEL_DEFAULT, conf: float = 0.25) -> list:
    """运行 YOLOv8n 检测，返回检测结果列表。"""
    from ultralytics import YOLO

    model = YOLO(model_path)

    # 支持摄像头源: camera:0 / camera:1
    if isinstance(image_path, str) and image_path.startswith("camera:"):
        source = int(image_path.split(":", 1)[1])
    else:
        source = image_path

    results = model(source, conf=conf, verbose=False)

    detections = []
    for r in results:
        if r.boxes is None:
            continue
        for box in r.boxes:
            detections.append({
                "class": r.names[int(box.cls)],
                "class_id": int(box.cls),
                "confidence": round(float(box.conf), 4),
                "bbox": [round(float(v), 2) for v in box.xyxy[0].tolist()],  # [x1,y1,x2,y2]
            })
    return detections


def main() -> None:
    parser = argparse.ArgumentParser(description="YOLOv8n 目标检测工具（输出 JSON）")
    parser.add_argument("image", help="图片路径，或 camera:0 表示摄像头源")
    parser.add_argument("--model", default=MODEL_DEFAULT, help="模型路径（默认同目录 yolov8n.pt）")
    parser.add_argument("--conf", type=float, default=0.25, help="置信度阈值（默认 0.25）")
    args = parser.parse_args()

    try:
        detections = detect(args.image, args.model, args.conf)
        print(json.dumps(detections, ensure_ascii=False))
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
