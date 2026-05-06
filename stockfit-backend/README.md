# StockFit Backend (FastAPI Sample)

This backend is scaffolded with a maintainable FastAPI folder structure.

## Folder Structure

```text
stockfit-backend/
├── app/
│   ├── api/
│   │   ├── endpoints/
│   │   │   ├── health.py
│   │   │   └── items.py
│   │   └── router.py
│   ├── core/
│   │   └── config.py
│   ├── db/
│   │   └── fake_db.py
│   ├── models/
│   │   └── item.py
│   ├── schemas/
│   │   └── item.py
│   ├── services/
│   │   └── item_service.py
│   └── main.py
├── tests/
│   └── test_main.py
└── requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload
```

## API Docs

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

## Test

```bash
pytest -q
```
