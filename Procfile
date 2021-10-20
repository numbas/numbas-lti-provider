web: daphne numbasltiprovider.asgi:application --port $PORT --bind 0.0.0.0 -v2
huey: python manage.py run_huey -w 8
release: python manage.py migrate
