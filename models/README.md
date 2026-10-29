# Model files

Model weights are intentionally not included in this repository. The training checkpoint `best.pt` is private to the project owner. For hardware inference, export a compatible YOLOv8 segmentation checkpoint to ONNX and place it here as `best.onnx`, or point `CRACKSCOPE_MODEL` at another ONNX file. See [the software guide](../docs/software.md#prepare-an-onnx-model).
