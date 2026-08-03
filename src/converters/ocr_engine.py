
import os
import numpy as np
import re
import sys
import warnings
from pathlib import Path


# The CUDA wheels install their DLLs below site-packages/nvidia/*/bin, but
# Windows does not add those directories to the DLL search path automatically.
# Keep the handles alive for the whole process so Paddle can load cuBLAS/cuDNN.
_NVIDIA_DLL_HANDLES = []
if os.name == "nt":
    nvidia_root = Path(sys.prefix) / "Lib" / "site-packages" / "nvidia"
    if nvidia_root.is_dir():
        nvidia_bins = [path for path in nvidia_root.glob("*/bin") if path.is_dir()]
        if nvidia_bins:
            os.environ["PATH"] = os.pathsep.join(map(str, nvidia_bins)) + os.pathsep + os.environ.get("PATH", "")
            for bin_dir in nvidia_bins:
                try:
                    _NVIDIA_DLL_HANDLES.append(os.add_dll_directory(str(bin_dir)))
                except (AttributeError, FileNotFoundError, OSError):
                    pass

# PaddleX imports torch indirectly through ModelScope. On Windows, torch must
# be loaded before paddle; otherwise paddle's bundled OpenMP DLL can be selected
# first and torch/lib/shm.dll then fails with WinError 127. Keep preloading on by
# default, while allowing an explicit opt-out for isolated Paddle-only runtimes.
if os.getenv("DOC_TO_MD_PRELOAD_TORCH", "1").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}:
    try:
        import torch  # noqa: F401
    except Exception as exc:
        warnings.warn(f"Torch preload failed before Paddle import: {exc}")

import paddle
import paddle.device
from PIL import Image, ImageDraw
from src.utils.offline_ocr_assets import prepare_offline_ocr_assets
from src.utils.ocr_corrections import apply_ocr_corrections
from src.utils.ocr_config import resolve_text_det_limit_side_len
from src.utils.korean_spacing import fix_korean_spacing
from src.utils.xy_cut import recursive_xy_cut

# Suppress warnings
warnings.filterwarnings("ignore", category=UserWarning)
import logging
logging.getLogger("ppocr").setLevel(logging.ERROR)

# Import PaddleOCR
# PaddleOCR import moved to __init__


class OCREngine:
    _instance = None
    _reader = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = OCREngine()
        return cls._instance

    def __init__(self):
        if OCREngine._instance is not None:
             raise Exception("This class is a singleton!")

        self._correction_profile = os.getenv("OCR_CORRECTION_PROFILE", "").strip() or None

        print("Initializing PaddleOCR...")
        offline_model_kwargs = prepare_offline_ocr_assets()

        try:
            from paddleocr import PaddleOCR
        except Exception as exc:
            # Raise instead of leaving _reader=None: a silently cached broken
            # singleton would make every OCR call return empty text with no
            # error. get_instance() leaves _instance unset when this raises,
            # so a later call can retry after the environment is fixed.
            raise RuntimeError(
                f"PaddleOCR을 불러오지 못했습니다 (OCR 사용 불가): {exc}"
            ) from exc

        # Common OCR options: disable doc preprocessing and avoid extreme downscale defaults.
        common_kwargs = {
            "lang": "korean",
            "use_doc_orientation_classify": False,
            "use_doc_unwarping": False,
            "use_textline_orientation": False,
            "text_det_limit_side_len": resolve_text_det_limit_side_len(),
            "text_det_limit_type": "max",
        }
        if offline_model_kwargs:
            common_kwargs.update(offline_model_kwargs)

        # --- GPU / CPU fallback chain ---
        self._device_used = "cpu"
        gpu_ok = False
        try:
            gpu_ok = paddle.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0
        except Exception:
            gpu_ok = False

        if gpu_ok:
            try:
                gpu_name = paddle.device.cuda.get_device_name(0)
                print(f"GPU detected: {gpu_name}")
            except Exception:
                pass

            try:
                gpu_reader = PaddleOCR(device="gpu", **common_kwargs)
                if self._smoke_test_reader(gpu_reader):
                    self._reader = gpu_reader
                    self._device_used = "gpu"
                    print("PaddleOCR initialized on GPU.")
                    return
                print("GPU OCR smoke test failed (empty detection). Falling back to CPU.")
            except Exception as e:
                print(f"Failed to initialize PaddleOCR on GPU: {e}")
        else:
            if paddle.is_compiled_with_cuda():
                print("CUDA compiled but no GPU device found. Using CPU.")
            else:
                print("PaddlePaddle CPU-only build detected. Using CPU.")

        print("Initializing PaddleOCR on CPU (MKLDNN Disabled)...")
        self._reader = PaddleOCR(device="cpu", enable_mkldnn=False, **common_kwargs)
        print("PaddleOCR initialized on CPU.")

    def _smoke_test_reader(self, reader):
        """Quick runtime validation to avoid silent empty outputs on unstable backends."""
        try:
            # White canvas with simple ASCII text should always be detectable.
            canvas = Image.new("RGB", (1200, 300), "white")
            draw = ImageDraw.Draw(canvas)
            draw.text((80, 110), "OCR HEALTH CHECK 12345", fill="black")
            test_img = np.array(canvas)
            result = reader.predict(test_img)
            if not result:
                return False
            data = result[0]
            if isinstance(data, dict):
                return len(data.get("dt_polys", [])) > 0
            if isinstance(data, list):
                return len(data) > 0
            return False
        except Exception:
            return False

    def extract_text(self, image, paragraph=False):
        """
        Extracts text from a PIL Image or numpy array.
        Returns a single string of text.
        """
        try:
            if self._reader is None:
                return ""

            # PaddleOCR expects a file path or numpy array (BGR preferred by cv2, but RGB usually works too).
            # If it's a PIL Image, ensure it's RGB.
            if hasattr(image, 'convert'):
                image = image.convert('RGB')
            
            if not isinstance(image, np.ndarray):
                image = np.array(image)
                
            # Ensure 3 channels (PaddleOCR can fail on 2D grayscale arrays with "tuple index out of range" in normalization)
            if image.ndim == 2:
                # Convert Grayscale to BGR/RGB by stacking
                image = np.stack((image,)*3, axis=-1)

            # Run OCR
            # PaddleOCR v3+ recommends predict(); keep ocr() fallback for compatibility.
            if hasattr(self._reader, "predict"):
                result = self._reader.predict(image)
            else:
                result = self._reader.ocr(image)
            
            # Helper to parse result
            parsed_lines = []
            
            if result:
                # Check for Paddlex/PaddleOCR v3 Object Structure
                # It returns a list containing OCRResult objects
                ocr_data = result[0]
                
                # Check if it behaves like a dict (Paddlex OCRResult)
                # It might not support hasattr, so try dict access or conversion
                try:
                    # Try to access as dict first (Paddlex uses plural keys: rec_texts, rec_scores)
                    if 'dt_polys' in ocr_data and ('rec_texts' in ocr_data or 'rec_text' in ocr_data):
                        boxes = ocr_data['dt_polys']
                        
                        # Handle both plural (new) and singular (potential legacy/variant) keys
                        texts = ocr_data['rec_texts'] if 'rec_texts' in ocr_data else ocr_data['rec_text']
                        
                        # Handle scores
                        if 'rec_scores' in ocr_data:
                            scores = ocr_data['rec_scores']
                        elif 'rec_score' in ocr_data:
                            scores = ocr_data['rec_score']
                        else:
                            scores = [1.0] * len(texts)
                        
                        for box, text, score in zip(boxes, texts, scores):
                            # Ensure score is a float (sometimes it's a tensor or list)
                            if isinstance(score, list):
                                score = score[0] if score else 0.0
                            if float(score) >= 0.5:
                                parsed_lines.append({'text': text, 'box': box})
                except Exception as e:
                    # Fallback or ignore if not dict-like
                    pass

                # If parsed_lines is still empty, try attribute access (just in case)
                if not parsed_lines and hasattr(ocr_data, 'dt_polys'):
                    # Check for rec_texts attribute
                    if hasattr(ocr_data, 'rec_texts'):
                        texts = ocr_data.rec_texts
                    elif hasattr(ocr_data, 'rec_text'):
                        texts = ocr_data.rec_text
                    else:
                        texts = None
                    
                    if texts:
                        boxes = ocr_data.dt_polys
                        if hasattr(ocr_data, 'rec_scores'):
                             scores = ocr_data.rec_scores
                        elif hasattr(ocr_data, 'rec_score'):
                             scores = ocr_data.rec_score
                        else:
                             scores = [1.0] * len(texts)
                        
                        for box, text, score in zip(boxes, texts, scores):
                            if isinstance(score, list): score = score[0] if score else 0.0
                            if float(score) >= 0.5:
                                parsed_lines.append({'text': text, 'box': box})
                            
                # Case 2: Legacy List-of-Lists (Old PaddleOCR)
                if not parsed_lines and isinstance(ocr_data, list):
                    for line in ocr_data:
                        # line structure: [box, (text, score)]
                        if len(line) >= 2 and line[1]:
                             text = line[1][0]
                             box = line[0]
                             parsed_lines.append({'text': text, 'box': box})
            
            if not parsed_lines:
                return ""
            
            if paragraph:
                return self._compose_paragraph_text(parsed_lines)
            else:
                ordered_lines = self._build_lines(parsed_lines)
                joined = " ".join([line["text"] for line in ordered_lines if line["text"]])
                return self._post_process_text(joined)
                
        except Exception as e:
            print(f"PaddleOCR Error: {e}")
            import traceback
            traceback.print_exc()
            return ""

    def _box_metrics(self, box):
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        return {
            "x0": float(x0),
            "x1": float(x1),
            "y0": float(y0),
            "y1": float(y1),
            "w": float(max(1.0, x1 - x0)),
            "h": float(max(1.0, y1 - y0)),
            "cy": float((y0 + y1) / 2.0),
        }

    def _is_noise_line(self, text, metrics):
        text = (text or "").strip()
        if not text:
            return True
        # Drop very tall narrow vertical artifacts often detected on book spine/side labels.
        if metrics["h"] > metrics["w"] * 2.0 and len(text) <= 10:
            return True
        return False

    def _build_lines(self, parsed_lines):
        raw_items = []
        for item in parsed_lines:
            box = item.get("box")
            text = (item.get("text") or "").strip()
            if box is None or len(box) == 0 or not text:
                continue
            m = self._box_metrics(box)
            if self._is_noise_line(text, m):
                continue
            raw_items.append({"text": text, "m": m})

        if not raw_items:
            return []

        median_h = float(np.median([it["m"]["h"] for it in raw_items]))
        items = []
        for it in raw_items:
            is_tall = it["m"]["h"] > median_h * 2.2
            is_short_token = len(it["text"]) <= 6
            if is_tall and is_short_token:
                continue
            items.append(it)

        if not items:
            return []

        # Use XY-Cut for reading order (handles multi-column layouts)
        if len(items) >= 2:
            box_arr = np.array(
                [[it["m"]["x0"], it["m"]["y0"], it["m"]["x1"], it["m"]["y1"]]
                 for it in items],
                dtype=int,
            )
            order = []
            recursive_xy_cut(box_arr, np.arange(len(items)), order)
            items = [items[i] for i in order]
        else:
            items.sort(key=lambda x: x["m"]["cy"])

        y_threshold = max(8.0, median_h * 0.6)

        line_groups = []
        for it in items:
            if not line_groups:
                line_groups.append([it])
                continue
            prev_group = line_groups[-1]
            prev_cy = float(np.mean([p["m"]["cy"] for p in prev_group]))
            if abs(it["m"]["cy"] - prev_cy) <= y_threshold:
                prev_group.append(it)
            else:
                line_groups.append([it])

        lines = []
        for group in line_groups:
            group.sort(key=lambda x: x["m"]["x0"])
            line_text = self._join_line_tokens(group)
            if line_text:
                y0 = min(g["m"]["y0"] for g in group)
                y1 = max(g["m"]["y1"] for g in group)
                h = max(1.0, y1 - y0)
                lines.append({"text": line_text, "y0": y0, "y1": y1, "h": h})
        return lines

    def _join_line_tokens(self, tokens):
        if not tokens:
            return ""
        char_width = self._estimate_line_char_width(tokens)
        parts = [tokens[0]["text"]]
        prev = tokens[0]
        for curr in tokens[1:]:
            prev_text = parts[-1]
            curr_text = curr["text"]
            gap = curr["m"]["x0"] - prev["m"]["x1"]
            ref_h = min(prev["m"]["h"], curr["m"]["h"])

            if prev_text.endswith("-") and curr_text:
                parts[-1] = prev_text[:-1] + curr_text
            elif gap <= max(1.5, char_width * 0.20, ref_h * 0.06):
                parts.append(curr_text)
            else:
                parts.append((" " * self._spaces_for_gap(gap, char_width, ref_h)) + curr_text)
            prev = curr
        return "".join(parts).strip()

    def _estimate_line_char_width(self, tokens):
        widths = []
        for token in tokens:
            text_len = len(re.sub(r"\s+", "", token["text"] or ""))
            if text_len > 0:
                widths.append(token["m"]["w"] / text_len)
        if widths:
            return max(1.0, float(np.median(widths)))
        return max(1.0, float(np.median([t["m"]["h"] for t in tokens])) * 0.5)

    def _spaces_for_gap(self, gap, char_width, ref_h):
        # Korean OCR often returns accurate glyphs but under-reports literal
        # spaces. Use geometry to restore wider original gaps between boxes.
        if gap <= 0:
            return 0
        nominal_space = max(1.0, char_width * 0.55, ref_h * 0.18)
        spaces = int(round(gap / nominal_space))
        return max(1, min(12, spaces))

    def _compose_paragraph_text(self, parsed_lines):
        lines = self._build_lines(parsed_lines)
        if not lines:
            return ""

        combined = lines[0]["text"]
        for i in range(1, len(lines)):
            prev = lines[i - 1]
            curr = lines[i]
            vgap = curr["y0"] - prev["y1"]
            threshold = max(10.0, curr["h"] * 0.75)
            if vgap > threshold:
                combined += "\n\n" + curr["text"]
            else:
                if combined.endswith("-"):
                    combined = combined[:-1] + curr["text"]
                else:
                    combined += "\n" + curr["text"]
        return self._post_process_text(combined)

    def _post_process_text(self, text):
        if not text:
            return ""
        text = text.replace("\r\n", "\n")
        # Fix line-break hyphenation (e.g., Consu-\nmer -> Consumer)
        text = re.sub(r"([A-Za-z])-\n([A-Za-z])", r"\1\2", text)
        # Join lines within the same paragraph (single \n -> space).
        # Preserve paragraph breaks (double \n).
        text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
        # Remove unnecessary spaces before punctuation.
        text = re.sub(r"\s+([,.;:!?])", r"\1", text)
        # Remove spaces right after opening brackets and before closing brackets.
        text = re.sub(r"([(\[{<])\s+", r"\1", text)
        text = re.sub(r"\s+([)\]}>])", r"\1", text)
        # Normalize tabs/newlines while preserving geometry-derived spacing.
        text = text.replace("\t", " ")
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Apply Korean spacing correction (insert missing spaces, remove wrong ones)
        protected_spaces = {}

        def _protect_space_run(match):
            key = f"__OCR_SPACE_RUN_{len(protected_spaces)}__"
            protected_spaces[key] = match.group(0)
            return key

        text = re.sub(r" {2,}", _protect_space_run, text)
        text = fix_korean_spacing(text)
        for key, value in protected_spaces.items():
            text = text.replace(key, value)
        text = apply_ocr_corrections(text, profile=self._correction_profile)
        return text.strip()

# Global helper
def get_ocr_text(image, paragraph=False):
    engine = OCREngine.get_instance()
    return engine.extract_text(image, paragraph=paragraph)
