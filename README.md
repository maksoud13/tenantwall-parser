# tenantwall Parser

Python service that parses SQL queries and injects tenant filters.

## Setup

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000