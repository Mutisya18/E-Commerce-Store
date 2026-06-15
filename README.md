# E-Commerce Store

A full-featured e-commerce web application built with Django. Customers can browse products, manage a cart, place orders, and pay via Flutterwave. Store owners manage everything through a built-in dashboard.

## Architecture

The project follows a standard Django monolith with a split-settings pattern (`dev` / `prod`).

```
E-Commerce-Store/
├── store/                  # Django project config (settings, urls, wsgi)
│   └── settings/
│       ├── base.py         # Shared settings
│       ├── dev.py          # SQLite, debug, Codespaces CSRF tweaks
│       └── prod.py         # PostgreSQL, HSTS, Redis cache
├── apps/
│   ├── accounts/           # Custom User model, auth backends, profiles
│   ├── store/              # Storefront: home, product listing, product detail
│   ├── products/           # Product & category models
│   ├── orders/             # Cart, checkout, order management
│   ├── payments/           # Flutterwave payment integration & webhooks
│   ├── dashboard/          # Admin dashboard: orders, products, analytics, reports
│   └── core/               # Shared middleware (journey logging), formatters
├── templates/              # Django HTML templates (per-app folders)
├── static/                 # Source CSS (Tailwind output) and JS
└── staticfiles/            # Collected static files (generated)
```

**Key technologies:**

| Layer | Choice |
|---|---|
| Framework | Django 5.1 |
| Auth | django-allauth |
| Payments | Flutterwave |
| Media storage | Cloudinary |
| Static files | WhiteNoise |
| Frontend | Tailwind CSS + Alpine.js |
| Database (dev) | SQLite |
| Database (prod) | PostgreSQL (`DATABASE_URL`) |
| Cache (prod) | Redis (optional) |

## Running locally

**1. Clone and install dependencies**

```bash
git clone <repo-url>
cd E-Commerce-Store
make install
```

**2. Configure environment**

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```
DJANGO_SECRET_KEY=a-random-secret-key
DJANGO_DEBUG=True
DJANGO_SETTINGS_MODULE=store.settings.dev
```

Cloudinary and Flutterwave keys are only required if you need media uploads or payment flows.

**3. Set up the database and run**

```bash
make setup   # installs deps, generates icon sprite, runs migrations
make run     # starts the dev server at http://127.0.0.1:8000
```

Or step by step:

```bash
make migrate
python manage.py runserver
```

**4. Create a superuser** (for the `/dashboard` admin)

```bash
python manage.py createsuperuser
```

## Production

Set `DJANGO_SETTINGS_MODULE=store.settings.prod` and provide:

- `DATABASE_URL` — PostgreSQL connection string
- `DJANGO_SECRET_KEY` — strong random key
- `ALLOWED_HOSTS` — your domain(s)
- Cloudinary and Flutterwave credentials
- `REDIS_URL` (optional) — enables Redis cache

Collect static files before deploying:

```bash
python manage.py collectstatic --noinput
```

## Security audit

```bash
make audit   # runs pip-audit against requirements.txt
```
