web: daphne numbasltiprovider.asgi:channel_layer --port $PORT --bind 0.0.0.0 -v2
worker: python manage.py runworker -v2
release: python manage.py migrate