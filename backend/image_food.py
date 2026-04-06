from fastapi import APIRouter, UploadFile, File
from PIL import Image, ImageFilter, ImageOps
import pytesseract
import io
import re
from statistics import median
from store import meals_db
from photo_predictor import predict_nutrition_from_food_photo

router = APIRouter()

# ⚠️ SET YOUR TESSERACT PATH (Windows only)
pytesseract.pytesseract.tesseract_cmd = r"D:\Apps\New folder\tesseract.exe"


NUTRIENT_PATTERNS = {
    "calories": [
        r"(?:calories|energy|kcal)\s*[:\-]?\s*(\d{1,4}(?:[\.,]\d{1,2})?)"
    ],
    "protein": [
        r"(?:protein|prot[eo]in)\s*[:\-]?\s*(\d{1,3}(?:[\.,]\d{1,2})?)\s*(?:g|gm|grams?)?"
    ],
    "carbs": [
        r"(?:total\s+carbohydrate|carbohydrate|carbohydrates|carbs?)\s*[:\-]?\s*(\d{1,3}(?:[\.,]\d{1,2})?)\s*(?:g|gm|grams?)?"
    ],
    "fat": [
        r"(?:total\s+fat|fat)\s*[:\-]?\s*(\d{1,3}(?:[\.,]\d{1,2})?)\s*(?:g|gm|grams?)?"
    ]
}


def normalize_number(raw_value: str) -> float:
    return float(raw_value.replace(",", "."))


def preprocess_image_variants(image: Image.Image):
    # Correct orientation from EXIF and upscale to improve OCR quality.
    image = ImageOps.exif_transpose(image).convert("RGB")

    width, height = image.size
    max_side = max(width, height)
    if max_side < 1400:
        scale = 1400 / max_side
        image = image.resize((int(width * scale), int(height * scale)), Image.Resampling.LANCZOS)

    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray)

    sharp = gray.filter(ImageFilter.SHARPEN)
    strong_sharp = sharp.filter(ImageFilter.UnsharpMask(radius=2, percent=180, threshold=3))

    bw_150 = gray.point(lambda p: 255 if p > 150 else 0)
    bw_170 = gray.point(lambda p: 255 if p > 170 else 0)

    return [gray, sharp, strong_sharp, bw_150, bw_170]


def run_ocr_multi_pass(variants):
    texts = []
    configs = [
        "--oem 3 --psm 6",
        "--oem 3 --psm 11",
        "--oem 3 --psm 4"
    ]

    for img in variants:
        for config in configs:
            text = pytesseract.image_to_string(img, config=config)
            cleaned = (text or "").strip()
            if cleaned:
                texts.append(cleaned)

    return texts


def collect_nutrient_candidates(text: str):
    candidates = {
        "calories": [],
        "protein": [],
        "carbs": [],
        "fat": []
    }

    for nutrient, patterns in NUTRIENT_PATTERNS.items():
        for pattern in patterns:
            matches = re.findall(pattern, text, flags=re.IGNORECASE)
            for match in matches:
                try:
                    value = normalize_number(match)
                    if value >= 0:
                        candidates[nutrient].append(value)
                except ValueError:
                    continue

    return candidates


def collect_linewise_candidates(text: str):
    candidates = {
        "calories": [],
        "protein": [],
        "carbs": [],
        "fat": []
    }

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        lower_line = line.lower()
        compact_line = re.sub(r"[^a-z]", "", lower_line)
        numbers = re.findall(r"\d{1,4}(?:[\.,]\d{1,2})?", lower_line)
        if not numbers:
            continue

        parsed_numbers = []
        for value in numbers:
            try:
                parsed_numbers.append(normalize_number(value))
            except ValueError:
                continue

        if not parsed_numbers:
            continue

        if any(token in compact_line for token in ["calories", "energy", "kcal"]):
            candidates["calories"].extend([v for v in parsed_numbers if 0 <= v <= 2500])

        if any(token in compact_line for token in ["protein", "protien"]):
            candidates["protein"].extend([v for v in parsed_numbers if 0 <= v <= 200])

        if any(token in compact_line for token in ["carbohydrate", "carbohydrates", "carbs", "totalcarbohydrate"]):
            candidates["carbs"].extend([v for v in parsed_numbers if 0 <= v <= 300])

        if any(token in compact_line for token in ["totalfat", "fat"]):
            candidates["fat"].extend([v for v in parsed_numbers if 0 <= v <= 200])

    return candidates


def collect_contextual_candidates(text: str):
    candidates = {
        "calories": [],
        "protein": [],
        "carbs": [],
        "fat": []
    }

    nutrient_tokens = {
        "calories": ["calories", "energy", "kcal"],
        "protein": ["protein", "protien"],
        "carbs": ["carbohydrate", "carbohydrates", "carbs", "total carbohydrate"],
        "fat": ["fat", "total fat"]
    }

    lines = [line.strip().lower() for line in text.splitlines() if line.strip()]
    number_pattern = r"\d{1,4}(?:[\.,]\d{1,2})?"

    for idx, line in enumerate(lines):
        context_lines = [line]
        if idx + 1 < len(lines):
            context_lines.append(lines[idx + 1])
        if idx + 2 < len(lines):
            context_lines.append(lines[idx + 2])

        context = " ".join(context_lines)
        numbers = re.findall(number_pattern, context)
        if not numbers:
            continue

        parsed_numbers = []
        for value in numbers:
            try:
                parsed_numbers.append(normalize_number(value))
            except ValueError:
                continue

        if not parsed_numbers:
            continue

        for nutrient, tokens in nutrient_tokens.items():
            if any(token in line for token in tokens):
                candidates[nutrient].extend(parsed_numbers)

    return candidates


def choose_value(values, fallback=0):
    if not values:
        return fallback

    # Ignore zero-heavy noise (common in %DV lines) unless nothing else exists.
    non_zero_values = [v for v in values if v > 0]
    if not non_zero_values:
        return fallback

    # Median is more stable than first-match for noisy OCR output.
    return round(median(non_zero_values), 1)


def extract_nutrients(texts):
    merged = {
        "calories": [],
        "protein": [],
        "carbs": [],
        "fat": []
    }

    for text in texts:
        candidates = collect_nutrient_candidates(text)
        linewise_candidates = collect_linewise_candidates(text)
        contextual_candidates = collect_contextual_candidates(text)
        for key in merged:
            merged[key].extend(candidates[key])
            merged[key].extend(linewise_candidates[key])
            merged[key].extend(contextual_candidates[key])

    # Apply lightweight plausible-range filters to remove clear OCR noise.
    merged["calories"] = [v for v in merged["calories"] if 20 <= v <= 1500]
    merged["protein"] = [v for v in merged["protein"] if 0 < v <= 150]
    merged["carbs"] = [v for v in merged["carbs"] if 0 < v <= 250]
    merged["fat"] = [v for v in merged["fat"] if 0 < v <= 150]

    calories = choose_value(merged["calories"], 0)
    protein = choose_value(merged["protein"], 0)
    carbs = choose_value(merged["carbs"], 0)
    fat = choose_value(merged["fat"], 0)

    found_count = sum(1 for value in [calories, protein, carbs, fat] if value > 0)
    if found_count >= 4:
        confidence = "high"
    elif found_count >= 2:
        confidence = "medium"
    else:
        confidence = "low"

    return calories, protein, carbs, fat, confidence


def blend_with_visual_prediction(ocr_values, predicted_nutrition):
    calories, protein, carbs, fat = ocr_values

    blended = {
        "calories": calories if calories > 0 else predicted_nutrition["calories"],
        "protein": protein if protein > 0 else predicted_nutrition["protein"],
        "carbs": carbs if carbs > 0 else predicted_nutrition["carbs"],
        "fat": fat if fat > 0 else predicted_nutrition["fat"],
    }

    macro_kcal = (blended["protein"] * 4.0) + (blended["carbs"] * 4.0) + (blended["fat"] * 9.0)
    if blended["calories"] <= 0:
        blended["calories"] = macro_kcal
    else:
        # Keep OCR calories while reducing extreme mismatch with macro sum.
        blended["calories"] = (blended["calories"] * 0.65) + (macro_kcal * 0.35)

    for key in blended:
        blended[key] = round(blended[key], 1)

    return blended


@router.post("/image")
async def analyze_image(file: UploadFile = File(...)):

    try:
        # Read image bytes and build OCR-friendly variants.
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
        variants = preprocess_image_variants(image)
        ocr_texts = run_ocr_multi_pass(variants)

        if not ocr_texts:
            return {
                "error": "Failed to process image",
                "details": "No readable text detected"
            }

        calories, protein, carbs, fat, confidence = extract_nutrients(ocr_texts)
        ocr_missing_all = (calories == 0 and protein == 0 and carbs == 0 and fat == 0)
        predicted = predict_nutrition_from_food_photo(contents)
        predicted_nutrition = predicted["nutrition"]

        # Blend OCR + visual prediction to avoid missing nutrients and improve consistency.
        blended = blend_with_visual_prediction(
            (calories, protein, carbs, fat),
            predicted_nutrition
        )
        calories = blended["calories"]
        protein = blended["protein"]
        carbs = blended["carbs"]
        fat = blended["fat"]

        # If OCR cannot extract values at all, use pure visual prediction mode.
        if ocr_missing_all:
            nutrition = predicted_nutrition

            meal = {
                "name": "Scanned Food",
                "calories": nutrition["calories"],
                "protein": nutrition["protein"],
                "carbs": nutrition["carbs"],
                "fat": nutrition["fat"]
            }

            meals_db.append(meal)

            return {
                "message": "Nutrition predicted from food image",
                "confidence": predicted["confidence"],
                "prediction_mode": "visual_estimation",
                "meal": meal,
                "note": "Estimated from dish photo when label OCR was unavailable",
                "food_profile": predicted["profile"],
                "visual_metrics": predicted["visual_metrics"]
            }

        meal = {
            "name": "Scanned Food",
            "calories": calories,
            "protein": protein,
            "carbs": carbs,
            "fat": fat
        }

        meals_db.append(meal)

        return {
            "message": "Nutrition extracted successfully",
            "confidence": confidence,
            "prediction_mode": "hybrid_ocr_vision",
            "meal": meal,
            "note": "Values estimated using OCR and visually completed for missing nutrients",
            "ocr_passes": len(ocr_texts)
        }

    except Exception as e:
        return {
            "error": "Failed to process image",
            "details": str(e)
        }