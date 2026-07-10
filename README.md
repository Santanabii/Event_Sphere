# EventSphere Backend



Django REST Framework backend powering EventSphere — a hybrid event ticketing
platform combining official ticket sales, M-Pesa payments, QR gate check-in, a
peer-to-peer resale marketplace, and live organiser analytics.

## Tech stack

- **Django + Django REST Framework** — core API
- **Django Channels** — WebSocket support for the live organiser analytics dashboard
- **PostgreSQL** — primary database (managed instance on Render)
- **django-daraja** — M-Pesa STK Push integration
- **SendGrid** — transactional email (ticket delivery)
- **ReportLab** — PDF ticket generation
- **JWT auth** 
- **QR codes** 

## Apps

Five Django apps, matching the endpoint groups below:

```
users/          authentication, profiles, roles (attendee / organiser / staff)
events/         event + ticket tier CRUD
tickets/        purchases, M-Pesa payment flow, QR scanning
marketplace/    peer-to-peer resale listings
analytics/      organiser dashboard stats + live WebSocket feed
```

## API endpoints

These are confirmed directly from the frontend's API client — not guessed.

### Auth — `/api/users/`
| Method | Path | Description |
|---|---|---|
| POST | `/api/users/register/` | Create account (role: attendee / organiser / staff) |
| POST | `/api/users/login/` | Returns JWT access + refresh tokens |
| POST | `/api/users/logout/` | Invalidates refresh token |
| GET | `/api/users/profile/` | Current user's profile |
| POST | `/api/users/token/refresh/` | Exchange refresh token for new access token |

### Events — `/api/events/`
| Method | Path | Description |
|---|---|---|
| GET | `/api/events/` | List events |
| POST | `/api/events/` | Create event (organiser) |
| GET | `/api/events/{id}/` | Event detail |
| PUT | `/api/events/{id}/` | Update event |
| DELETE | `/api/events/{id}/` | Delete event |
| GET | `/api/events/{id}/tiers/` | List ticket tiers for an event |
| POST | `/api/events/{id}/tiers/` | Create a ticket tier |
| PUT | `/api/events/{id}/tiers/{tier_id}/` | Update a tier |
| DELETE | `/api/events/{id}/tiers/{tier_id}/` | Delete a tier |

### Tickets — `/api/tickets/`
| Method | Path | Description |
|---|---|---|
| POST | `/api/tickets/purchase/` | Initiate purchase → triggers M-Pesa STK Push |
| GET | `/api/tickets/status/{checkout_id}/` | Poll payment status |
| GET | `/api/tickets/my-tickets/` | Current user's tickets |
| GET | `/api/tickets/my-tickets/{id}/` | Single ticket detail |
| POST | `/api/tickets/scan/` | Validate a QR token at the gate (staff) |

### Marketplace — `/api/marketplace/`
| Method | Path | Description |
|---|---|---|
| GET | `/api/marketplace/listings/` | Browse active resale listings |
| POST | `/api/marketplace/listings/create/` | List a ticket for resale |
| GET | `/api/marketplace/listings/my/` | Current user's own listings |
| POST | `/api/marketplace/listings/{id}/purchase/` | Buy a resale listing → M-Pesa STK Push |
| POST | `/api/marketplace/listings/{id}/cancel/` | Cancel own listing |
| GET | `/api/marketplace/payment-status/{checkout_id}/` | Poll resale payment status |

### Analytics — `/api/analytics/`
| Method | Path | Description |
|---|---|---|
| GET | `/api/analytics/events/{event_id}/` | Sales/revenue/check-in stats for one event |
| WS | `/ws/analytics/{event_id}/` | Live-updating version of the above (Channels) |

## Environment variables

⚠️ Names below follow standard conventions for these packages — confirm against
your actual `settings.py`.

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | `False` in production |
| `DATABASE_URL` | Postgres connection string (Render provides this automatically) |
| `ALLOWED_HOSTS` | Comma-separated list, must include your Render domain |
| `CORS_ALLOWED_ORIGINS` | Must include your deployed Vercel frontend URL + `localhost:5173` for local dev |
| `DARAJA_CONSUMER_KEY` / `DARAJA_CONSUMER_SECRET` | M-Pesa Daraja API credentials |
| `DARAJA_SHORTCODE` / `DARAJA_PASSKEY` | M-Pesa STK Push config |
| `DARAJA_CALLBACK_URL` | Public URL Safaricom calls back to (must be reachable — use ngrok locally) |
| `SENDGRID_API_KEY` | Ticket delivery email |
| `REDIS_URL` | Required if Channels uses `channels_redis` as its layer backend |

## Local setup

⚠️ Standard Django flow — confirm these match your actual project structure:

```bash
python -m venv venv
source venv/bin/activate        # Windows (Git Bash): source venv/Scripts/activate
pip install -r requirements.txt

cp .env.example .env             # fill in the variables above
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

For M-Pesa callbacks to reach your local machine, you'll need **ngrok** (or similar)
tunneling to `localhost:8000`, with `DARAJA_CALLBACK_URL` pointed at the ngrok URL.

## Running with WebSockets locally

Since Channels needs an ASGI server, `python manage.py runserver` alone may not
fully serve WebSocket connections depending on your `asgi.py`/routing setup.
⚠️ If your analytics WebSocket doesn't connect locally, check whether you need
`daphne` explicitly:

```bash
daphne -b 0.0.0.0 -p 8000 your_project_name.asgi:application
```

## Deployment (Render)

1. Push to GitHub, create a **Web Service** on Render pointing at the repo
2. Add a managed **PostgreSQL** instance (Render sets `DATABASE_URL` automatically)
3. Set all environment variables from the table above
4. **Start command** — must run an ASGI server if Channels/WebSockets are in use:
   ```bash
   daphne -b 0.0.0.0 -p $PORT your_project_name.asgi:application
   ```
   
5. Confirm `ALLOWED_HOSTS` and `CORS_ALLOWED_ORIGINS` include the exact deployed
   frontend domain (and any custom domain, once added)

## Known integration points with the frontend

- Frontend expects `access` and `refresh` fields in the login response body
- Frontend derives its WebSocket URL by swapping `http→ws` / `https→wss` on the
  API base URL — so the backend's WebSocket route must be reachable at the same
  host as the REST API
- 401 responses trigger an automatic token-refresh retry on the frontend — make
  sure expired/invalid tokens consistently return `401`, not `403` or `400`
