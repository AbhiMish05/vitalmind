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
    name: str = Form("Photo Logged Meal"),
    calories: float = Form(0),
    protein: float = Form(0),
    carbs: float = Form(0),
    fat: float = Form(0)
):
    contents = await file.read()

    used_prediction = False
    prediction_meta = None
    if calories == 0 and protein == 0 and carbs == 0 and fat == 0:
        predicted = predict_nutrition_from_food_photo(contents)
        nutrition = predicted["nutrition"]
        calories = nutrition["calories"]
        protein = nutrition["protein"]
        carbs = nutrition["carbs"]
        fat = nutrition["fat"]
        used_prediction = True
        prediction_meta = {
            "prediction_mode": "visual_estimation",
            "food_profile": predicted["profile"],
            "confidence": predicted["confidence"],
            "visual_metrics": predicted["visual_metrics"]
        }

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
        "meal": meal
    }
    if used_prediction and prediction_meta:
        response.update(prediction_meta)
        response["note"] = "Nutrition estimated automatically from uploaded food photo"

    return response