.PHONY: install test run sim lint clean

install:
pip install -r requirements.txt

test:
python -m pytest tests/ -v

run:
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

sim:
python -m app.simulator --count 5 --interval 2.0 --duration 120

lint:
python -m py_compile app/*.py app/**/*.py

clean:
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
rm -rf .pytest_cache
