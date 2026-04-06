from fastapi import APIRouter, UploadFile, File, Form
import os
import re
from ai_service import chat_with_qwen_assistant
from photo_predictor import predict_nutrition_from_food_photo
from free_apis import search_openfoodfacts

router = APIRouter()


def _is_plan_intent(query: str) -> bool:
    q = (query or "").lower()
    triggers = [
        "plan",
        "diet plan",
        "nutrition plan",
        "weight loss",
        "weight gain",
        "meal plan",
        "fat loss",
        "cutting",
        "bulking",
    ]
    return any(token in q for token in triggers)


def _build_plan_response(query: str):
    q = (query or "").lower()
    if "weight gain" in q or "bulking" in q:
        goal = "weight gain"
        plan_text = (
            "Target a 300-450 kcal surplus; eat 3 main meals + 2 snacks; "
            "protein 1.6-2.2 g/kg body weight; include calorie-dense whole foods "
            "like rice, dairy, nuts, and eggs; track weight weekly and adjust intake."
        )
    elif "stay fit" in q or "maintain" in q:
        goal = "maintenance"
        plan_text = (
            "Keep calories near maintenance; prioritize balanced plates (protein + complex carbs + vegetables + healthy fats); "
            "protein 1.4-1.8 g/kg; hydrate well; keep meal timing consistent."
        )
    else:
        goal = "weight loss"
        plan_text = (
            "Use a mild 300-500 kcal deficit; prioritize protein 1.6-2.2 g/kg; "
            "fill half the plate with vegetables; use whole grains and lean proteins; "
            "avoid liquid calories; aim 8-10k daily steps and monitor weekly progress."
        )

    return {
        "is_food": False,
        "food_name": "",
        "response": plan_text,
        "nutrition_estimate": None,
        "model": "local-plan-fallback",
        "goal": goal,
    }


def _local_food_fallback(query: str):
    q = (query or "").lower()

    # Simple local estimates to keep chatbot functional when free APIs fail.
    presets = [
        ("daal chawal", {"calories": 390.0, "protein": 14.0, "carbs": 62.0, "fat": 8.0}),
        ("dal chawal", {"calories": 390.0, "protein": 14.0, "carbs": 62.0, "fat": 8.0}),
        ("chicken biryani", {"calories": 520.0, "protein": 24.0, "carbs": 56.0, "fat": 21.0}),
        ("paneer", {"calories": 340.0, "protein": 18.0, "carbs": 10.0, "fat": 24.0}),
        ("salad", {"calories": 180.0, "protein": 7.0, "carbs": 16.0, "fat": 9.0}),
        ("egg", {"calories": 155.0, "protein": 13.0, "carbs": 1.1, "fat": 11.0}),
        ("banana", {"calories": 105.0, "protein": 1.3, "carbs": 27.0, "fat": 0.4}),
    ]

    for keyword, nutrition in presets:
        if keyword in q:
            return {
                "is_food": True,
                "food_name": keyword,
                "response": "I estimated nutrition for this dish using local nutrition references. This is suitable for quick meal planning.",
                "nutrition_estimate": nutrition,
                "model": "local-fallback"
            }

    # Try generic cleaned name extraction.
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", q)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if cleaned:
        return {
            "is_food": True,
            "food_name": cleaned[:40],
            "response": "I could not find an exact database match, so I provided a practical generic meal estimate.",
            "nutrition_estimate": {"calories": 320.0, "protein": 14.0, "carbs": 38.0, "fat": 12.0},
            "model": "local-fallback"
        }

    return {
        "is_food": None,
        "food_name": "",
        "response": "Could not identify the food from text. Try a clearer food name.",
        "nutrition_estimate": None,
        "model": "local-fallback"
    }


@router.post("/message")
async def chatbot_message(
    message: str = Form(""),
    file: UploadFile = File(None)
):
    image_bytes = None
    if file is not None:
        image_bytes = await file.read()

    # Free API / local fallback path when Qwen key is not configured.
    if not os.getenv("QWEN_API_KEY", ""):
        if image_bytes:
            prediction = predict_nutrition_from_food_photo(image_bytes)
            nutrition = prediction.get("nutrition")
            return {
                "is_food": True,
                "food_name": prediction.get("profile", "food_item"),
                "response": "I analyzed your image and estimated nutrition values from visual food patterns.",
                "nutrition_estimate": nutrition,
                "model": "free-fallback-local"
            }

        query = (message or "").strip()
        if not query:
            return {
                "error": "No input provided",
                "details": "Send a message or upload an image"
            }

        if _is_plan_intent(query):
            return _build_plan_response(query)

        try:
            free_result = search_openfoodfacts(query=query, limit=3)
            first_item = (free_result.get("items") or [None])[0]
            if not first_item:
                return _local_food_fallback(query)

            nutrition = {
                "calories": float(first_item.get("calories") or 0),
                "protein": float(first_item.get("protein") or 0),
                "carbs": float(first_item.get("carbs") or 0),
                "fat": float(first_item.get("fat") or 0),
            }

            return {
                "is_food": True,
                "food_name": (first_item or {}).get("name", "food item"),
                "response": "I found this item in a free nutrition database and summarized its macro profile for you.",
                "nutrition_estimate": nutrition,
                "model": "free-api-openfoodfacts"
            }
        except Exception as e:
            local_estimate = _local_food_fallback(query)
            local_estimate["details"] = f"OpenFoodFacts failed: {str(e)}"
            return local_estimate

    result = chat_with_qwen_assistant(message=message, image_bytes=image_bytes)
    return result
