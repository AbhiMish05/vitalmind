from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from food import router as food_router
from insights import router as insights_router
from image_food import router as image_router
from free_apis import router as free_api_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(food_router, prefix="/food")
app.include_router(insights_router, prefix="/insights")
app.include_router(image_router, prefix="/food")
app.include_router(free_api_router, prefix="/free-apis")


@app.get("/")
def root():
    return {"message": "VitalMind Backend Running"}