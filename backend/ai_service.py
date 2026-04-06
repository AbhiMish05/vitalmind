import base64
import hashlib
import json
import os
import re
import time
import requests


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_TEXT_MODEL = os.getenv("OLLAMA_TEXT_MODEL", "llama3")
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "llava")
OLLAMA_TIMEOUT_SEC = float(os.getenv("OLLAMA_TIMEOUT_SEC", "2.8"))
OLLAMA_ENABLE_TEXT = os.getenv("OLLAMA_ENABLE_TEXT", "1") == "1"
OLLAMA_ENABLE_VISION = os.getenv("OLLAMA_ENABLE_VISION", "1") == "1"

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


def _ollama_generate(payload, timeout_sec=None):
  timeout_sec = timeout_sec if timeout_sec is not None else OLLAMA_TIMEOUT_SEC
  response = requests.post(
    f"{OLLAMA_BASE_URL}/api/generate",
    json=payload,
    timeout=timeout_sec,
  )
  response.raise_for_status()
  data = response.json()
  return data.get("response", "")


def get_ai_suggestions(context):
  if not OLLAMA_ENABLE_TEXT:
    return None

  context_json = json.dumps(context, sort_keys=True)
  cache_key = f"insights:{hashlib.sha1(context_json.encode('utf-8')).hexdigest()}"
  cached = _cache_get(cache_key)
  if cached:
    return cached

  prompt = (
    "You are a concise health coach. "
    "Return ONLY valid JSON with this shape: "
    "{\"suggestions\":[{\"title\":\"\",\"insight\":\"\",\"action\":\"\",\"reason\":\"\",\"priority\":\"low|medium|high\"}]}. "
    "Give exactly 3 suggestions and keep each field short. "
    f"User data: {context_json}"
  )

  payload = {
    "model": OLLAMA_TEXT_MODEL,
    "prompt": prompt,
    "stream": False,
    "options": {
      "temperature": 0.2,
      "num_predict": 280,
      "top_p": 0.9
    },
    "keep_alive": "5m"
  }

  try:
    raw = _ollama_generate(payload, timeout_sec=OLLAMA_TIMEOUT_SEC)
    if not raw:
      return None

    _cache_set(cache_key, raw, ttl_seconds=90)
    return raw
  except Exception as e:
    print("Ollama insights error:", e)
    return None


def predict_nutrition_from_ollama_image(image_bytes: bytes):
  if not OLLAMA_ENABLE_VISION:
    return None

  img_hash = hashlib.sha1(image_bytes).hexdigest()
  cache_key = f"vision-direct:{img_hash}"
  cached = _cache_get(cache_key)
  if cached:
    return cached

  b64_image = base64.b64encode(image_bytes).decode("utf-8")
  prompt = (
    "Analyze this food photo and estimate nutrition for one typical serving. "
    "Return ONLY valid JSON with keys: profile, confidence, nutrition. "
    "nutrition must include calories, protein, carbs, fat as numbers. "
    "Do not include markdown or extra text."
  )

  payload = {
    "model": OLLAMA_VISION_MODEL,
    "prompt": prompt,
    "images": [b64_image],
    "stream": False,
    "options": {
      "temperature": 0.05,
      "num_predict": 140,
      "top_p": 0.8
    },
    "keep_alive": "5m"
  }

  try:
    raw = _ollama_generate(payload, timeout_sec=min(4.2, OLLAMA_TIMEOUT_SEC + 1.2))
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
      "prediction_mode": "vision_ollama_direct",
      "visual_metrics": {}
    }

    _cache_set(cache_key, result, ttl_seconds=300)
    return result
  except Exception as e:
    print("Ollama direct vision error:", e)
    return None


def refine_photo_prediction_with_ollama(image_bytes: bytes, base_prediction: dict):
  if not OLLAMA_ENABLE_VISION:
    return None

  img_hash = hashlib.sha1(image_bytes).hexdigest()
  base_hash = hashlib.sha1(json.dumps(base_prediction, sort_keys=True).encode("utf-8")).hexdigest()
  cache_key = f"vision:{img_hash}:{base_hash}"
  cached = _cache_get(cache_key)
  if cached:
    return cached

  b64_image = base64.b64encode(image_bytes).decode("utf-8")
  prompt = (
    "You are a nutrition vision estimator. "
    "Given this food image and baseline estimate, adjust slightly for better realism. "
    "Return ONLY JSON with keys profile, confidence, nutrition. "
    "nutrition must include calories, protein, carbs, fat as numbers. "
    f"Baseline: {json.dumps(base_prediction, sort_keys=True)}"
  )

  payload = {
    "model": OLLAMA_VISION_MODEL,
    "prompt": prompt,
    "images": [b64_image],
    "stream": False,
    "options": {
      "temperature": 0.1,
      "num_predict": 160,
      "top_p": 0.85
    },
    "keep_alive": "5m"
  }

  try:
    raw = _ollama_generate(payload, timeout_sec=min(3.2, OLLAMA_TIMEOUT_SEC + 0.6))
    parsed = _extract_json_object(raw)
    if not parsed or "nutrition" not in parsed:
      return None

    nutrition = parsed.get("nutrition", {})
    refined = {
      "profile": parsed.get("profile", base_prediction.get("profile", "mixed_meal")),
      "confidence": parsed.get("confidence", "medium"),
      "nutrition": {
        "calories": float(nutrition.get("calories", 0)),
        "protein": float(nutrition.get("protein", 0)),
        "carbs": float(nutrition.get("carbs", 0)),
        "fat": float(nutrition.get("fat", 0)),
      },
    }

    _cache_set(cache_key, refined, ttl_seconds=300)
    return refined
  except Exception as e:
    print("Ollama vision error:", e)
    return None