# Backend (FastAPI)

## Team Setup

1. Move into backend:

```bash
cd backend
```

2. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Install dependencies:

```bash
python -m pip install --upgrade pip
pip install fastapi "uvicorn[standard]" python-dotenv
```

4. Create local env from template:

```bash
cp .env.example .env
```

## Run

```bash
uvicorn main:app --reload
```

## Collaboration Notes

- Never commit `.env` or `.venv/`.
- Commit dependency updates with your feature work.
- Use feature branches and open PRs to merge into `main`.
