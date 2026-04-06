from fastapi import APIRouter, Query
import requests
import time
import re

router = APIRouter()

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


def _cache_set(key, value, ttl_seconds=180):
    _CACHE[key] = (time.time() + ttl_seconds, value)


def search_openfoodfacts(query: str, limit: int = 5):
    cleaned_query = re.sub(r"[^a-zA-Z0-9\s]", " ", (query or "").lower())
    stopwords = {"is", "are", "the", "a", "an", "for", "to", "my", "healthy", "health", "healty", "please", "can", "you", "tell", "me", "about"}
    tokens = [token for token in cleaned_query.split() if token and token not in stopwords]
    normalized_query = " ".join(tokens[:6]) or cleaned_query.strip() or query

    cache_key = f"off:{normalized_query}:{limit}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    response = requests.get(
        "https://world.openfoodfacts.org/cgi/search.pl",
        params={
            "search_terms": normalized_query,
            "search_simple": 1,
            "action": "process",
            "json": 1,
            "page_size": limit
        },
        headers={
            "User-Agent": "VitalMind/1.0 (nutrition-assistant)",
            "Accept": "application/json"
        },
        timeout=4.0
    )
    response.raise_for_status()
    payload = response.json()

    products = []
    for product in payload.get("products", []):
        nutriments = product.get("nutriments", {})
        products.append({
            "name": product.get("product_name") or product.get("generic_name") or "Unknown",
            "brand": product.get("brands", ""),
            "calories": nutriments.get("energy-kcal_100g", 0),
            "protein": nutriments.get("proteins_100g", 0),
            "carbs": nutriments.get("carbohydrates_100g", 0),
            "fat": nutriments.get("fat_100g", 0)
        })

    result = {
        "source": "OpenFoodFacts",
        "query": normalized_query,
        "count": len(products),
        "items": products
    }
    _cache_set(cache_key, result, ttl_seconds=300)
    return result


@router.get("/providers")
def list_free_api_providers():
    return {
        "providers": [
            {
                "name": "OpenFoodFacts",
                "purpose": "Food product lookup and nutriments",
                "endpoint": "https://world.openfoodfacts.org/cgi/search.pl"
            },
            {
                "name": "TheMealDB",
                "purpose": "Free meal metadata and images",
                "endpoint": "https://www.themealdb.com/api/json/v1/1/random.php"
            }
        ]
    }


@router.get("/meal/random")
def get_random_free_meal():
    cache_key = "meal_random"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    try:
        response = requests.get(
            "https://www.themealdb.com/api/json/v1/1/random.php",
            timeout=3.5
        )
        response.raise_for_status()
        payload = response.json()
        meal = (payload.get("meals") or [{}])[0]

        result = {
            "source": "TheMealDB",
            "meal": {
                "name": meal.get("strMeal", "Unknown"),
                "category": meal.get("strCategory", "Unknown"),
                "area": meal.get("strArea", "Unknown"),
                "thumbnail": meal.get("strMealThumb", ""),
                "tags": meal.get("strTags", "")
            }
        }
        _cache_set(cache_key, result, ttl_seconds=120)
        return result
    except Exception as e:
        return {
            "error": "Free meal API unavailable",
            "details": str(e)
        }


@router.get("/food/search")
def search_free_food_api(
    query: str = Query(..., min_length=2, description="Food name to search"),
    limit: int = Query(5, ge=1, le=15)
):
    try:
        return search_openfoodfacts(query=query, limit=limit)
    except Exception as e:
        return {
            "error": "Free food API unavailable",
            "details": str(e)
        }
