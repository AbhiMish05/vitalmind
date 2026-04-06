from PIL import Image, ImageFilter
import io
from math import exp
from ai_service import predict_nutrition_from_ollama_image


def _image_metrics(image: Image.Image):
    img = image.convert("RGB").resize((256, 256), Image.Resampling.BILINEAR)
    pixels = list(img.getdata())
    total = len(pixels) or 1

    warm = 0
    green = 0
    white = 0
    dark = 0
    sat_sum = 0.0

    for r, g, b in pixels:
        mx = max(r, g, b)
        mn = min(r, g, b)
        sat_sum += (mx - mn) / 255.0

        if r > g + 12 and g > b - 5 and r > 95:
            warm += 1

        if g > r + 18 and g > b + 15 and g > 70:
            green += 1

        if abs(r - g) < 12 and abs(g - b) < 12 and (r + g + b) / 3 > 180:
            white += 1

        if (r + g + b) / 3 < 55:
            dark += 1

    edge = img.filter(ImageFilter.FIND_EDGES).convert("L")
    edge_values = list(edge.getdata())
    edge_density = sum(1 for v in edge_values if v > 40) / len(edge_values)

    return {
        "warm_ratio": warm / total,
        "green_ratio": green / total,
        "white_ratio": white / total,
        "dark_ratio": dark / total,
        "avg_saturation": sat_sum / total,
        "edge_density": edge_density,
    }


def _closeness(value: float, target: float, width: float) -> float:
    # Smooth gaussian-like closeness in [0, 1].
    delta = (value - target) / max(width, 1e-6)
    return exp(-(delta * delta))


def _score_profile(metrics, profile_features):
    score = 0.0
    total_weight = 0.0
    for feature_name, spec in profile_features.items():
        target = spec["target"]
        width = spec["width"]
        weight = spec["weight"]
        score += _closeness(metrics[feature_name], target, width) * weight
        total_weight += weight

    if total_weight == 0:
        return 0.0
    return score / total_weight


def _weighted_macro_average(profile_scores, profiles):
    weight_sum = sum(profile_scores.values()) or 1.0
    result = {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0}

    for profile_name, score in profile_scores.items():
        macros = profiles[profile_name]["nutrition"]
        w = score / weight_sum
        for key in result:
            result[key] += macros[key] * w

    return result


def predict_nutrition_from_food_photo(image_bytes: bytes):
    # Primary path: send image to Ollama and use its direct nutrition output.
    ollama_result = predict_nutrition_from_ollama_image(image_bytes)
    if ollama_result:
        return ollama_result

    # Fallback path: local visual model when Ollama is unavailable.
    image = Image.open(io.BytesIO(image_bytes))
    metrics = _image_metrics(image)

    warm = metrics["warm_ratio"]
    green = metrics["green_ratio"]
    white = metrics["white_ratio"]
    dark = metrics["dark_ratio"]
    saturation = metrics["avg_saturation"]
    edge = metrics["edge_density"]

    profiles = {
        "salad_or_vegetable_dish": {
            "nutrition": {"calories": 190.0, "protein": 9.0, "carbs": 20.0, "fat": 9.0},
            "features": {
                "green_ratio": {"target": 0.34, "width": 0.22, "weight": 1.5},
                "warm_ratio": {"target": 0.16, "width": 0.18, "weight": 1.0},
                "white_ratio": {"target": 0.12, "width": 0.20, "weight": 0.8},
                "avg_saturation": {"target": 0.25, "width": 0.14, "weight": 1.1},
                "edge_density": {"target": 0.17, "width": 0.09, "weight": 0.7},
            },
        },
        "rice_or_pasta_style_dish": {
            "nutrition": {"calories": 345.0, "protein": 9.0, "carbs": 61.0, "fat": 6.0},
            "features": {
                "white_ratio": {"target": 0.38, "width": 0.22, "weight": 1.4},
                "green_ratio": {"target": 0.08, "width": 0.15, "weight": 0.8},
                "avg_saturation": {"target": 0.13, "width": 0.10, "weight": 1.1},
                "edge_density": {"target": 0.16, "width": 0.09, "weight": 0.8},
            },
        },
        "fried_or_fast_food_style_dish": {
            "nutrition": {"calories": 535.0, "protein": 21.0, "carbs": 42.0, "fat": 31.0},
            "features": {
                "warm_ratio": {"target": 0.46, "width": 0.20, "weight": 1.5},
                "avg_saturation": {"target": 0.34, "width": 0.12, "weight": 1.1},
                "edge_density": {"target": 0.26, "width": 0.10, "weight": 1.2},
                "dark_ratio": {"target": 0.18, "width": 0.14, "weight": 0.8},
            },
        },
        "grilled_or_roasted_dish": {
            "nutrition": {"calories": 315.0, "protein": 29.0, "carbs": 14.0, "fat": 16.0},
            "features": {
                "dark_ratio": {"target": 0.34, "width": 0.20, "weight": 1.3},
                "warm_ratio": {"target": 0.28, "width": 0.16, "weight": 0.9},
                "avg_saturation": {"target": 0.20, "width": 0.12, "weight": 0.8},
                "edge_density": {"target": 0.20, "width": 0.09, "weight": 0.9},
            },
        },
        "mixed_meal": {
            "nutrition": {"calories": 390.0, "protein": 19.0, "carbs": 36.0, "fat": 16.0},
            "features": {
                "warm_ratio": {"target": 0.26, "width": 0.24, "weight": 0.8},
                "green_ratio": {"target": 0.16, "width": 0.22, "weight": 0.8},
                "white_ratio": {"target": 0.22, "width": 0.20, "weight": 0.8},
                "avg_saturation": {"target": 0.22, "width": 0.14, "weight": 0.8},
                "edge_density": {"target": 0.20, "width": 0.10, "weight": 0.8},
            },
        },
    }

    profile_scores = {
        profile_name: _score_profile(metrics, profile_data["features"])
        for profile_name, profile_data in profiles.items()
    }

    sorted_profiles = sorted(profile_scores.items(), key=lambda item: item[1], reverse=True)
    profile = sorted_profiles[0][0]
    top_score = sorted_profiles[0][1]
    second_score = sorted_profiles[1][1] if len(sorted_profiles) > 1 else 0.0
    margin = max(0.0, top_score - second_score)

    nutrition = _weighted_macro_average(profile_scores, profiles)

    # Portion/energy adjustment proxy from texture and color balance.
    portion_factor = 1.0 + (edge - 0.18) * 0.45 + (warm - 0.24) * 0.20 - (green - 0.18) * 0.18
    portion_factor = min(1.25, max(0.82, portion_factor))

    nutrition["calories"] *= portion_factor
    nutrition["protein"] *= (0.94 + (dark * 0.20) + (edge * 0.10))
    nutrition["carbs"] *= (0.94 + (white * 0.24) - (green * 0.15))
    nutrition["fat"] *= (0.92 + (warm * 0.26) + (saturation * 0.12))

    # Keep macros and calories mathematically coherent.
    macro_kcal = (nutrition["protein"] * 4.0) + (nutrition["carbs"] * 4.0) + (nutrition["fat"] * 9.0)
    nutrition["calories"] = (nutrition["calories"] * 0.55) + (macro_kcal * 0.45)

    confidence = "low"
    if top_score > 0.70 and margin > 0.08:
        confidence = "high"
    elif top_score > 0.55:
        confidence = "medium"

    # Final guard rails.
    nutrition["calories"] = min(950.0, max(120.0, nutrition["calories"]))
    nutrition["protein"] = min(70.0, max(4.0, nutrition["protein"]))
    nutrition["carbs"] = min(120.0, max(6.0, nutrition["carbs"]))
    nutrition["fat"] = min(55.0, max(3.0, nutrition["fat"]))

    base_result = {
        "profile": profile,
        "confidence": confidence,
        "nutrition": {k: round(v, 1) for k, v in nutrition.items()},
        "visual_metrics": {
            "warm_ratio": round(warm, 3),
            "green_ratio": round(green, 3),
            "white_ratio": round(white, 3),
            "edge_density": round(edge, 3),
            "portion_factor": round(portion_factor, 3),
            "top_profile_score": round(top_score, 3),
            "score_margin": round(margin, 3),
        },
    }

    base_result["prediction_mode"] = "vision_local_fast"
    return base_result
