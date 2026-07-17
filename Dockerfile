FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml .
RUN pip install .
COPY . .
# collectstatic imports settings (needs a key) and builds the whitenoise manifest that
# DEBUG=false serving depends on. Use a throwaway key for the build step only — it is not
# persisted as an ENV, so it can't become a runtime default. No `|| true`: a real failure
# here means broken static in prod and must fail the build.
RUN DJANGO_SECRET_KEY=build-time-only python manage.py collectstatic --noinput
EXPOSE 8000
CMD ["gunicorn", "config.wsgi", "-b", "0.0.0.0:8000", "--workers", "2"]
