# VitalMind

Premium nutrition tracking app with a FastAPI backend and a modern frontend dashboard.

## Project Structure

- `backend/`: FastAPI APIs for meal logging, barcode lookup, OCR image scanning, and insights.
- `frontend/`: Premium single-page UI connected to the backend.

## Run Backend

1. Open terminal in `backend/`
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Start API server:

```bash
uvicorn main:app --reload
```

Backend will run at `http://127.0.0.1:8000`.

## Run Frontend

Open `frontend/index.html` in your browser.

The frontend is preconfigured to call `http://127.0.0.1:8000`.