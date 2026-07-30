# Meetups

Event-based groups: create an event, invite people, track RSVPs, share photos,
sync deadlines to a calendar, and chat in real time, all in one place.

## Features

- **Event groups**, one admin per event, optional capacity limit, private
  (invite-only) or open (public) visibility.
- **RSVP**, Going / Maybe / Not going, tracked per member.
- **Invites**, by email, whether or not the person has an account yet; a
  shareable invite link for private events.
- **Before/after-event actions**, deadline-based to-dos with their own
  `.ics` export and deadline reminder emails.
- **Calendar sync**, export any event (or action deadline) as `.ics`;
  reminder/deadline emails include the same file as an attachment.
- **Planning calls** and an **attendance tracker** (self or admin check-in).
- **Photo & link sharing** per event.
- **Real-time chat** per event over Django Channels WebSockets, with a
  rule-based bot (`/help`, `/attendees`, `/schedule`, `/actions`).
- **Location**, address + "Open in Google Maps" link, browser-geolocation
  "use my location" button, and an optional embedded Google Map.
- **Dashboard**, your events, or (if you're not part of any) a prompt to
  browse open events.

## Stack

Django 5 + Django REST Framework (API) + Django Channels/Daphne (WebSocket
chat) + APScheduler (in-process scheduled reminder emails, no Celery/Redis
needed) + Tailwind CSS (compiled, wood/brown theme) + vanilla JS.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

npm install
npm run build:css        # compiles static_src/input.css -> static/css/tailwind.css

cp .env.example .env     # edit as needed (all defaults work for local dev)

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Visit `http://127.0.0.1:8000`. The dev server (via the `daphne` app) serves
both HTTP and WebSocket traffic, so chat works out of the box.

While iterating on styles, run `npm run watch:css` in a second terminal.

### Environment variables (`.env`)

See `.env.example`. Notable ones:

- `EMAIL_BACKEND`, defaults to the console backend in debug mode, so
  invite/reminder/deadline emails print to the terminal instead of sending.
- `GOOGLE_MAPS_API_KEY`, optional. Without it, event pages still show an
  "Open in Google Maps" link; with it, an embedded map also renders.
- `REMINDER_POLL_MINUTES`, how often the in-process scheduler checks for
  reminder/deadline emails to send (default 5).

### Tests

```bash
python manage.py test
```
