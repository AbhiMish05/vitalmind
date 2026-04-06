from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from store import meals_db

# OPTIONAL: comment this if not using Qwen API
try:
    from ai_service import get_ai_suggestions
    USE_AI = True
except:
    USE_AI = False

router = APIRouter()


class UserProfile(BaseModel):
    bmi: Optional[float] = None
    age: Optional[int] = None
    goal: Optional[str] = None  # weight_loss | weight_gain | stay_fit


@router.post("/")
def get_insights(profile: UserProfile = UserProfile()):

    # 🚫 No data case
    if not meals_db:
        return {
            "health_score": 0,
            "suggestions": [],
            "message": "No meals logged yet"
        }

    # 📊 Calculate totals safely
    total_calories = sum(m.get("calories", 0) for m in meals_db)
    total_protein = sum(m.get("protein", 0) for m in meals_db)
    meal_count = len(meals_db)
    goal = (profile.goal or "stay_fit").strip().lower()

    # 🧠 Health Score Calculation
    score = 100

    calorie_low, calorie_high = 1200, 2200
    if goal == "weight_loss":
        calorie_low, calorie_high = 1200, 1800
    elif goal == "weight_gain":
        calorie_low, calorie_high = 2200, 3200

    if total_protein < 50:
        score -= 20

    if total_calories > calorie_high or total_calories < calorie_low:
        score -= 20

    if meal_count < 2:
        score -= 10

    if profile.bmi is not None:
        if goal == "weight_loss" and profile.bmi < 18.5:
            score -= 15
        if goal == "weight_gain" and profile.bmi > 30:
            score -= 15

    if profile.age is not None and (profile.age < 13 or profile.age > 80):
        score -= 5

    score = max(score, 0)

    # =========================
    # TRY AI (Qwen)
    # =========================
    if USE_AI:
        try:
            context = {
                "total_calories": total_calories,
                "total_protein": total_protein,
                "meal_count": meal_count,
                "goal": goal,
                "bmi": profile.bmi,
                "age": profile.age
            }

            ai_response = get_ai_suggestions(context)

            if ai_response:
                return {
                    "health_score": score,
                    "ai": True,
                    "generated_by": "Qwen API",
                    "response": ai_response,
                    "total_calories": total_calories,
                    "total_protein": total_protein,
                    "meal_count": meal_count,
                    "profile": {
                        "goal": goal,
                        "bmi": profile.bmi,
                        "age": profile.age,
                        "calorie_target_range": [calorie_low, calorie_high]
                    }
                }

        except Exception as e:
            print("AI failed, using fallback:", e)

    # =========================
    # 🧠 RULE-BASED FALLBACK
    # =========================

    suggestions = []

    if profile.age is not None:
        suggestions.append({
            "category": "profile",
            "priority": "low",
            "title": "Age-Aware Planning",
            "insight": f"Your profile age is {profile.age}.",
            "action": "Maintain hydration and sleep quality to support recovery.",
            "reason": "Age can affect recovery rate and metabolism."
        })

    if profile.bmi is not None:
        if profile.bmi < 18.5:
            suggestions.append({
                "category": "profile",
                "priority": "medium",
                "title": "Lower BMI Range Detected",
                "insight": f"Your BMI is {profile.bmi}, which is below 18.5.",
                "action": "Prioritize nutrient-dense meals and consistent protein intake.",
                "reason": "A low BMI may indicate a need for more total energy intake."
            })
        elif profile.bmi > 25:
            suggestions.append({
                "category": "profile",
                "priority": "medium",
                "title": "Higher BMI Range Detected",
                "insight": f"Your BMI is {profile.bmi}, above 25.",
                "action": "Focus on high-protein meals, fiber, and a controlled calorie target.",
                "reason": "A structured intake plan supports body composition improvements."
            })

    if goal == "weight_loss":
        suggestions.append({
            "category": "goal",
            "priority": "high",
            "title": "Weight Loss Goal Active",
            "insight": "Your recommendations are tuned for fat loss.",
            "action": "Aim for a mild calorie deficit and at least 60g+ protein daily.",
            "reason": "Protein supports satiety and helps preserve lean mass during deficit."
        })
    elif goal == "weight_gain":
        suggestions.append({
            "category": "goal",
            "priority": "high",
            "title": "Weight Gain Goal Active",
            "insight": "Your recommendations are tuned for healthy weight gain.",
            "action": "Eat in a calorie surplus and spread protein across 3-5 meals.",
            "reason": "A steady surplus with protein supports quality weight gain."
        })
    else:
        suggestions.append({
            "category": "goal",
            "priority": "low",
            "title": "Stay Fit Goal Active",
            "insight": "Your recommendations are tuned for maintenance and consistency.",
            "action": "Keep calories near maintenance and maintain a regular meal schedule.",
            "reason": "Consistency and balanced intake help maintain health and energy."
        })

    # 🔥 Protein
    if total_protein < 50:
        suggestions.append({
            "category": "nutrition",
            "priority": "high",
            "title": "Protein Intake Below Optimal Range",
            "insight": f"You consumed only {total_protein}g protein today, below the recommended 60g.",
            "action": "Add paneer, eggs, chicken, or lentils in your next meal.",
            "reason": "Protein is essential for muscle recovery, strength, and satiety."
        })

    # 🔥 High Calories
    if total_calories > calorie_high:
        suggestions.append({
            "category": "nutrition",
            "priority": "medium",
            "title": "Calorie Intake Above Target",
            "insight": f"Your total intake is {total_calories} kcal, above your goal range ({calorie_low}-{calorie_high}).",
            "action": "Reduce fried foods, sugary drinks, and late-night snacking.",
            "reason": "Consistently high calorie intake can lead to fat gain."
        })

    # 🔥 Low Calories
    if total_calories < calorie_low:
        suggestions.append({
            "category": "nutrition",
            "priority": "high",
            "title": "Insufficient Calorie Intake",
            "insight": f"Your calorie intake is below your goal range ({calorie_low}-{calorie_high}).",
            "action": "Increase balanced meals with carbs, protein, and healthy fats.",
            "reason": "Low calorie intake may cause fatigue and reduced focus."
        })

    # 🔥 Meal frequency
    if meal_count < 2:
        suggestions.append({
            "category": "habit",
            "priority": "medium",
            "title": "Irregular Meal Pattern",
            "insight": f"You logged only {meal_count} meal(s) today.",
            "action": "Aim for 3 structured meals to maintain energy balance.",
            "reason": "Skipping meals can disrupt metabolism and energy stability."
        })

    # 🔥 Balanced day
    if calorie_low <= total_calories <= calorie_high and total_protein >= 50:
        suggestions.append({
            "category": "habit",
            "priority": "low",
            "title": "Balanced Nutrition Day",
            "insight": "Your calorie and protein intake are within your goal-aligned range.",
            "action": "Maintain this consistency over the week.",
            "reason": "Consistency is key to long-term health and fitness."
        })

    # ✅ Final response
    return {
        "health_score": score,
        "ai": False,
        "generated_by": "VitalMind Rule Engine v1.0",
        "total_calories": total_calories,
        "total_protein": total_protein,
        "meal_count": meal_count,
        "profile": {
            "goal": goal,
            "bmi": profile.bmi,
            "age": profile.age,
            "calorie_target_range": [calorie_low, calorie_high]
        },
        "suggestions": suggestions
    }