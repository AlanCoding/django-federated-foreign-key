#!/bin/bash
set -e

pip install -e . >/dev/null
pip install -e example_project >/dev/null
pip install -e remote_project >/dev/null

(cd remote_project && \
    DATABASE_NAME=db.sqlite3 ./manage.py migrate --noinput && \
    DATABASE_NAME=db.sqlite3 ./manage.py shell -c "from remote_project.remoteapp.models import Book; Book.objects.create(title='Remote Book 1');" && \
    DATABASE_NAME=db.sqlite3 ./manage.py runserver 8001 &)
REMOTE_PID=$!

sleep 3

(cd example_project && \
    DATABASE_NAME=db.sqlite3 ./manage.py migrate --noinput && \
    DATABASE_NAME=db.sqlite3 ./manage.py shell -c "from example_project.testapp.models import Book; Book.objects.create(title='Local Book 1');" && \
    DATABASE_NAME=db.sqlite3 ./manage.py runserver 8000 &)
LOCAL_PID=$!

echo "Example project available at http://localhost:8000/books/"

wait $LOCAL_PID
kill $REMOTE_PID
