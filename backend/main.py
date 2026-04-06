from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from food import router as food_router
from insights import router as insights_router
from image_food import router as image_router
from free_apis import router as free_api_router
from chatbot import router as chatbot_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(food_router, prefix="/api/food")
app.include_router(insights_router, prefix="/api/insights")
app.include_router(image_router, prefix="/api/food")
app.include_router(free_api_router, prefix="/api/free-apis")
app.include_router(chatbot_router, prefix="/api/chatbot")


@app.get("/api")
def root():
    return {"message": "VitalMind API Running"}