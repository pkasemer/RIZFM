# Uganda Radio API

A small Dockerized Flask API for a Uganda online-radio directory and player backend.

## Features

- Flask REST API
- SQLite persistence
- Docker / Docker Compose
- CORS
- Seeded Uganda radio stations
- Search and filtering
- Pagination
- Featured stations
- CRUD endpoints
- Stream health checking
- Bulk stream checking
- Persistent database volume
- Gunicorn production server

## Run

```bash
docker compose up -d --build
```

API:

```text
http://localhost:5000
```

Health:

```bash
curl http://localhost:5000/health
```

Stations:

```bash
curl http://localhost:5000/api/v1/stations
```

Featured:

```bash
curl http://localhost:5000/api/v1/stations/featured
```

Search:

```bash
curl "http://localhost:5000/api/v1/stations?search=capital"
```

Filter by city:

```bash
curl "http://localhost:5000/api/v1/stations?city=Kampala"
```

Filter by genre:

```bash
curl "http://localhost:5000/api/v1/stations?genre=Music"
```

Pagination:

```bash
curl "http://localhost:5000/api/v1/stations?page=1&limit=10"
```

Check a stream:

```bash
curl -X POST http://localhost:5000/api/v1/stations/capital-fm/check
```

Check all streams:

```bash
curl -X POST http://localhost:5000/api/v1/stations/check-all
```

## Add station

```bash
curl -X POST http://localhost:5000/api/v1/stations   -H "Content-Type: application/json"   -d '{
    "id": "example-fm",
    "name": "Example FM",
    "frequency": "100.0 FM",
    "city": "Kampala",
    "genres": ["Music"],
    "languages": ["English"],
    "streamUrl": "https://example.com/stream",
    "streamType": "mp3",
    "bitrate": 128,
    "website": "https://example.com",
    "isFeatured": false,
    "isActive": true
  }'
```

## Update station

```bash
curl -X PUT http://localhost:5000/api/v1/stations/example-fm   -H "Content-Type: application/json"   -d '{"isFeatured": true}'
```

## Delete station

```bash
curl -X DELETE http://localhost:5000/api/v1/stations/example-fm
```

## Important

Radio stream URLs can change without notice. The `/check` endpoints provide a simple reachability check, but they do not guarantee that a URL contains valid audio. For production, consider adding a scheduled health-check worker and storing the last successful check.

Some stations use HTTP streams. If your mobile application requires HTTPS-only connections, you may need an HTTPS proxy/transcoding layer for those streams rather than exposing them directly to the client.
