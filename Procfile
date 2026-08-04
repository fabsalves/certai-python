release: cd backend && alembic upgrade head
web: cd backend && gunicorn app.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --workers 2 --timeout 120
worker: cd backend && celery -A app.workers.celery_app.celery_app worker -B -Q default,transcription,whatsapp,evaluation --concurrency=2 -l info
