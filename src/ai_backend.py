"""Self-contained text-prompted detection; imported only by the AI worker.

Uses the same Grounding DINO algorithm as the earlier labeling pipeline, without
importing that pipeline or depending on its location or files.
"""

import inspect
import math

MODEL = "IDEA-Research/grounding-dino-tiny"


def sanitize_boxes(candidates, width, height, threshold, nms_threshold):
    valid = []
    for item in candidates:
        values = [float(value) for value in item["box"]]
        score = float(item["score"])
        if len(values) != 4 or not all(math.isfinite(v) for v in [*values, score]) or score < threshold:
            continue
        x, y, X, Y = values
        box = [max(0, min(width, math.floor(x))), max(0, min(height, math.floor(y))),
               max(0, min(width, math.ceil(X))), max(0, min(height, math.ceil(Y)))]
        if box[2] > box[0] and box[3] > box[1]:
            valid.append(dict(box=box, score=score, prompt_label=item.get("prompt_label", "")))
    kept = []
    for item in sorted(valid, key=lambda row: row["score"], reverse=True):
        a = item["box"]
        for other in kept:
            b = other["box"]
            intersection = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
            union = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - intersection
            if intersection / union > nms_threshold:
                break
        else:
            kept.append(item)
    return kept


class GroundedDetector:
    def __init__(self, config, device):
        import torch
        from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor

        self.torch = torch
        self.device = "cuda:0" if device == "auto" and torch.cuda.is_available() else "cpu" if device == "auto" else device
        self.config = config
        self.processor = AutoProcessor.from_pretrained(MODEL)
        self.model = AutoModelForZeroShotObjectDetection.from_pretrained(MODEL).to(self.device).eval()
        self.revision = getattr(self.model.config, "_commit_hash", None)

    def predict(self, image):
        prompt = ". ".join(p.strip().rstrip(".").lower() for p in self.config["prompts"]) + "."
        inputs = self.processor(images=image, text=prompt, return_tensors="pt").to(self.device)
        with self.torch.inference_mode():
            outputs = self.model(**inputs)
        postprocess = self.processor.post_process_grounded_object_detection
        threshold_key = "box_threshold" if "box_threshold" in inspect.signature(postprocess).parameters else "threshold"
        result = postprocess(outputs, inputs.input_ids, **{threshold_key: self.config["box_threshold"]},
                             text_threshold=self.config["text_threshold"], target_sizes=[(image.height, image.width)])[0]
        labels = result.get("text_labels", result.get("labels", []))
        return [dict(box=box, score=score, prompt_label=str(label))
                for box, score, label in zip(result["boxes"].cpu().tolist(), result["scores"].cpu().tolist(), labels)]
