# !/usr/bin/env bash
# File path should be ./bin/post_compile
# (.sh extension added in Gist just to enable shell syntax highlighting.
# https://discussion.heroku.com/t/django-automaticlly-run-syncdb-and-migrations-after-heroku-deploy-with-a-buildpack-or-otherwise/466/7

echo "=> Performing database migrations..."
python manage.py migrate

