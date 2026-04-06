import base64
import hashlib
import json
import os
import re
import time
import requests


QWEN_API_BASE_URL = os.getenv("QWEN_API_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")
QWEN_TEXT_MODEL = os.getenv("QWEN_TEXT_MODEL", "qwen/qwen3-32b")
QWEN_VISION_MODEL = os.getenv("QWEN_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
QWEN_TIMEOUT_SEC = float(os.getenv("QWEN_TIMEOUT_SEC", "5.5"))
QWEN_ENABLE_TEXT = os.getenv("QWEN_ENABLE_TEXT", "1") == "1"
QWEN_ENABLE_VISION = os.getenv("QWEN_ENABLE_VISION", "1") == "1"

_CACHE = {}


def _cache_get(key):
    item = _CACHE.get(key)
    if not item:
        return None

    expires_at, value = item
    if time.time() > expires_at:
        _CACHE.pop(key, None)
        return None

    return value


def _cache_set(key, value, ttl_seconds=120):
    _CACHE[key] = (time.time() + ttl_seconds, value)


def _extract_json_object(text: str):
    text = (text or "").strip()
    if not text:
        return None

    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except Exception:
        return None


def _normalize_nutrition(nutrition):
    try:
        calories = float(nutrition.get("calories", 0))
        protein = float(nutrition.get("protein", 0))
        carbs = float(nutrition.get("carbs", 0))
        fat = float(nutrition.get("fat", 0))
    except Exception:
        return None

    if calories <= 0 and protein <= 0 and carbs <= 0 and fat <= 0:
        return None

    calories = min(1200.0, max(80.0, calories))
    protein = min(90.0, max(1.0, protein))
    carbs = min(170.0, max(1.0, carbs))
    fat = min(80.0, max(1.0, fat))

    return {
        "calories": round(calories, 1),
        "protein": round(protein, 1),
        "carbs": round(carbs, 1),
        "fat": round(fat, 1),
    }


def _coerce_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned in {"true", "yes", "y", "food", "is_food"}:
            return True
        if cleaned in {"false", "no", "n", "not_food", "non_food"}:
            return False
    return None


def _qwen_chat_completion(messages, model, timeout_sec=None, max_tokens=240, temperature=0.2):
    if not QWEN_API_KEY:
        return None

    timeout_sec = timeout_sec if timeout_sec is not None else QWEN_TIMEOUT_SEC
    response = requests.post(
        f"{QWEN_API_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {QWEN_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        },
        timeout=timeout_sec,
    )
    response.raise_for_status()
    data = response.json()
    choices = data.get("choices", [])
    if not choices:
        return None
    return choices[0].get("message", {}).get("content", "")


def get_ai_suggestions(context):
    if not QWEN_ENABLE_TEXT:
        return None

    context_json = json.dumps(context, sort_keys=True)
    cache_key = f"insights:{hashlib.sha1(context_json.encode('utf-8')).hexdigest()}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    messages = [
        {
            "role": "system",
            "content": (
                "You are a concise health coach. "
                "Return only JSON with key suggestions. "
                "Suggestions must be an array of exactly 3 objects with: "
                "title, insight, action, reason, priority(low|medium|high)."
            ),
        },
        {
            "role": "user",
            "content": f"User data: {context_json}",
        },
    ]

    try:
        raw = _qwen_chat_completion(
            messages=messages,
            model=QWEN_TEXT_MODEL,
            timeout_sec=QWEN_TIMEOUT_SEC,
            max_tokens=260,
            temperature=0.2,
        )
        if not raw:
            return None

        _cache_set(cache_key, raw, ttl_seconds=120)
        return raw
    except Exception as e:
        print("Qwen insights error:", e)
        return None


def predict_nutrition_from_qwen_image(image_bytes: bytes):
    if not QWEN_ENABLE_VISION:
        return None

    img_hash = hashlib.sha1(image_bytes).hexdigest()
    cache_key = f"vision-direct:{img_hash}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:image/jpeg;base64,{b64_image}"

    messages = [
        {
            "role": "system",
            "content": (
                "You estimate nutrition from food photos. "
                "Return only JSON with keys: profile, confidence, nutrition. "
                "nutrition must contain calories, protein, carbs, fat as numbers for one typical serving."
            ),
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Estimate nutrition from this food image."},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        },
    ]

    try:
        raw = _qwen_chat_completion(
            messages=messages,
            model=QWEN_VISION_MODEL,
            timeout_sec=QWEN_TIMEOUT_SEC,
            max_tokens=180,
            temperature=0.1,
        )
        parsed = _extract_json_object(raw)
        if not parsed:
            return None

        nutrition = _normalize_nutrition(parsed.get("nutrition", {}))
        if not nutrition:
            return None

        result = {
            "profile": parsed.get("profile", "mixed_meal"),
            "confidence": parsed.get("confidence", "medium"),
            "nutrition": nutrition,
            "prediction_mode": "vision_qwen_direct",
            "visual_metrics": {},
        }

        _cache_set(cache_key, result, ttl_seconds=300)
        return result
    except Exception as e:
        print("Qwen vision error:", e)
        return None


def chat_with_qwen_assistant(message: str, image_bytes: bytes = None):
    if not QWEN_API_KEY:
        return {
            "error": "Qwen API key missing",
            "details": "Set QWEN_API_KEY environment variable"
        }

    safe_message = (message or "").strip()
    cache_seed = safe_message
    if image_bytes:
        cache_seed += ":" + hashlib.sha1(image_bytes).hexdigest()
    cache_key = f"chat:{hashlib.sha1(cache_seed.encode('utf-8')).hexdigest()}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    system_prompt = (
        "You are VitalMind AI Expert Nutritionist, an elite nutrition AI. "
        "Provide highly accurate, efficient, and exceptionally human-readable nutrition guidance. "
        "Use short actionable paragraphs and clear language. "
        "If image is present, first decide if it is food. "
        "Return only JSON with keys: "
        "is_food (true/false), food_name (string), response (string with formatting), "
        "nutrition_estimate (object with calories,protein,carbs,fat OR null). "
    )

    user_payload = [{"type": "text", "text": safe_message or "Analyze this image."}]
    model = QWEN_TEXT_MODEL

    if image_bytes and QWEN_ENABLE_VISION:
        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        user_payload.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}})
        model = QWEN_VISION_MODEL

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_payload if len(user_payload) > 1 else (safe_message or "Help me with nutrition")}
    ]

    try:
        raw = _qwen_chat_completion(
            messages=messages,
            model=model,
            timeout_sec=QWEN_TIMEOUT_SEC,
            max_tokens=600,
            temperature=0.15,
        )
        parsed = _extract_json_object(raw)
        if not parsed:
            return {
                "is_food": None,
                "food_name": "",
                "response": "I could not parse the AI response. Please try again.",
                "nutrition_estimate": None
            }

        is_food = _coerce_bool(parsed.get("is_food", None))

        nutrition = parsed.get("nutrition_estimate")
        normalized_nutrition = None
        if isinstance(nutrition, dict):
            normalized_nutrition = _normalize_nutrition(nutrition)

        # Enforce product behavior:
        # - If uploaded image is food, always return nutrition output.
        # - If uploaded image is not food, never return nutrition output.
        if image_bytes and is_food is True and normalized_nutrition is None:
            fallback_prediction = predict_nutrition_from_qwen_image(image_bytes)
            if fallback_prediction and isinstance(fallback_prediction.get("nutrition"), dict):
                normalized_nutrition = fallback_prediction["nutrition"]

        if image_bytes and is_food is False:
            normalized_nutrition = None

        if image_bytes and is_food is None and normalized_nutrition is not None:
            is_food = True

        result = {
            "is_food": is_food,
            "food_name": parsed.get("food_name", ""),
            "response": parsed.get("response", ""),
            "nutrition_estimate": normalized_nutrition,
            "model": model
        }
        _cache_set(cache_key, result, ttl_seconds=120)
        return result
    except Exception as e:
        return {
            "error": "Qwen chat failed",
            "details": str(e)
        }