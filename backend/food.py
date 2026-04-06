from fastapi import APIRouter, UploadFile, File, Form
from store import meals_db
from pydantic import BaseModel
from photo_predictor import predict_nutrition_from_food_photo

router = APIRouter()

@router.post("/reset")
def reset():
    meals_db.clear()
    return {"message": "All meals cleared"}


class Meal(BaseModel):
    name: str
    calories: float = 0
    protein: float = 0
    carbs: float = 0
    fat: float = 0

@router.post("/log")
def log_meal(meal: Meal):
    meals_db.append(meal.dict())
    return {"message": "Meal added"}


@router.post("/photo-log")
async def log_meal_with_photo(
    file: UploadFile = File(...),
    name: str = Form("Photo Logged Meal")
):
    contents = await file.read()

    predicted = predict_nutrition_from_food_photo(contents)
    nutrition = predicted["nutrition"]
    calories = nutrition["calories"]
    protein = nutrition["protein"]
    carbs = nutrition["carbs"]
    fat = nutrition["fat"]

    # Keep only lightweight photo metadata in memory; image stays on client side.
    meal = {
        "name": name,
        "calories": calories,
        "protein": protein,
        "carbs": carbs,
        "fat": fat,
        "photo_name": file.filename
    }
    meals_db.append(meal)
    response = {
        "message": "Meal with photo added",
        "meal": meal,
        "prediction_mode": predicted.get("prediction_mode", "visual_estimation"),
        "food_profile": predicted.get("profile", "mixed_meal"),
        "confidence": predicted.get("confidence", "medium"),
        "visual_metrics": predicted.get("visual_metrics", {}),
        "note": "Nutrition estimated automatically from uploaded food image"
    }

    return response