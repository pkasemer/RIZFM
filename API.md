# RizFM API

RizFM API is a REST API for discovering and streaming online radio stations in Uganda.

## Base URL

```text
https://rizfm.pkasemer.com
```

API base URL:

```text
https://rizfm.pkasemer.com/api/v1
```

---

# Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Check API health |
| `GET` | `/api/v1/stations` | List radio stations |
| `GET` | `/api/v1/stations/featured` | Get featured stations |
| `GET` | `/api/v1/stations/:id` | Get a station |
| `POST` | `/api/v1/stations` | Create a station |
| `PUT` | `/api/v1/stations/:id` | Update a station |
| `DELETE` | `/api/v1/stations/:id` | Delete a station |
| `POST` | `/api/v1/stations/:id/check` | Check a station stream |
| `POST` | `/api/v1/stations/check-all` | Check all active streams |

---

# Health Check

Check whether the API is running.

## Request

```http
GET /health
```

## Example

```bash
curl https://rizfm.pkasemer.com/health
```

## Response

```json
{
  "status": "ok",
  "service": "uganda-radio-api"
}
```

---

# Stations

## List Stations

Returns a paginated list of radio stations.

### Request

```http
GET /api/v1/stations
```

### Query Parameters

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `page` | integer | No | `1` | Page number |
| `limit` | integer | No | `20` | Number of results per page |
| `search` | string | No | — | Search by station name or city |
| `genre` | string | No | — | Filter by genre |
| `city` | string | No | — | Filter by city |
| `featured` | boolean | No | — | Filter featured stations |
| `active` | boolean | No | — | Filter active stations |

`limit` has a maximum value of `100`.

### Get all stations

```bash
curl https://rizfm.pkasemer.com/api/v1/stations
```

### Search

```bash
curl "https://rizfm.pkasemer.com/api/v1/stations?search=capital"
```

### Filter by city

```bash
curl "https://rizfm.pkasemer.com/api/v1/stations?city=Kampala"
```

### Filter by genre

```bash
curl "https://rizfm.pkasemer.com/api/v1/stations?genre=Music"
```

### Filter featured stations

```bash
curl "https://rizfm.pkasemer.com/api/v1/stations?featured=true"
```

### Filter active stations

```bash
curl "https://rizfm.pkasemer.com/api/v1/stations?active=true"
```

### Pagination

```bash
curl "https://rizfm.pkasemer.com/api/v1/stations?page=1&limit=10"
```

### Combine filters

```bash
curl "https://rizfm.pkasemer.com/api/v1/stations?city=Kampala&genre=Music&featured=true"
```

## Response

```json
{
  "data": [
    {
      "id": "capital-fm",
      "name": "Capital FM Uganda",
      "frequency": "91.3 FM",
      "city": "Kampala",
      "genres": [
        "Pop",
        "Adult Contemporary",
        "Talk"
      ],
      "languages": [
        "English"
      ],
      "streamUrl": "http://capitalfm.cloudrad.io/stream",
      "streamType": "mp3",
      "bitrate": 128,
      "website": "https://capitalradio.co.ug",
      "logoUrl": null,
      "isFeatured": true,
      "isActive": true,
      "streamReachable": null,
      "lastChecked": null
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 15,
    "pages": 1
  }
}
```

---

# Get Station

Returns a single station by its ID.

## Request

```http
GET /api/v1/stations/:id
```

## Example

```bash
curl https://rizfm.pkasemer.com/api/v1/stations/capital-fm
```

## Response

```json
{
  "id": "capital-fm",
  "name": "Capital FM Uganda",
  "frequency": "91.3 FM",
  "city": "Kampala",
  "genres": [
    "Pop",
    "Adult Contemporary",
    "Talk"
  ],
  "languages": [
    "English"
  ],
  "streamUrl": "http://capitalfm.cloudrad.io/stream",
  "streamType": "mp3",
  "bitrate": 128,
  "website": "https://capitalradio.co.ug",
  "logoUrl": null,
  "isFeatured": true,
  "isActive": true,
  "streamReachable": null,
  "lastChecked": null
}
```

## Not Found

```json
{
  "error": "Station not found"
}
```

HTTP status:

```text
404 Not Found
```

---

# Featured Stations

Returns all active stations marked as featured.

## Request

```http
GET /api/v1/stations/featured
```

## Example

```bash
curl https://rizfm.pkasemer.com/api/v1/stations/featured
```

## Response

```json
{
  "data": [
    {
      "id": "capital-fm",
      "name": "Capital FM Uganda",
      "frequency": "91.3 FM",
      "city": "Kampala",
      "genres": [
        "Pop",
        "Adult Contemporary",
        "Talk"
      ],
      "languages": [
        "English"
      ],
      "streamUrl": "http://capitalfm.cloudrad.io/stream",
      "streamType": "mp3",
      "bitrate": 128,
      "website": "https://capitalradio.co.ug",
      "logoUrl": null,
      "isFeatured": true,
      "isActive": true,
      "streamReachable": null,
      "lastChecked": null
    }
  ]
}
```

---

# Stream Monitoring

RizFM provides endpoints for checking whether station streaming URLs are reachable.

> A successful reachability check means that the stream endpoint responded successfully. It does not guarantee that the returned content is valid audio.

---

## Check Station Stream

Checks the stream URL of a specific station.

### Request

```http
POST /api/v1/stations/:id/check
```

### Example

```bash
curl -X POST \
  https://rizfm.pkasemer.com/api/v1/stations/capital-fm/check
```

### Response

```json
{
  "id": "capital-fm",
  "reachable": true,
  "lastChecked": "2026-11-16T19:30:00+00:00"
}
```

### Unreachable Stream

```json
{
  "id": "capital-fm",
  "reachable": false,
  "lastChecked": "2026-11-16T19:30:00+00:00"
}
```

---

# Check All Streams

Checks all active radio station streams.

## Request

```http
POST /api/v1/stations/check-all
```

## Example

```bash
curl -X POST \
  https://rizfm.pkasemer.com/api/v1/stations/check-all
```

## Response

```json
{
  "data": [
    {
      "id": "capital-fm",
      "reachable": true
    },
    {
      "id": "beat-fm",
      "reachable": true
    },
    {
      "id": "kfm",
      "reachable": false
    }
  ],
  "checked": 15
}
```

---

# Station Management

> **Important:** The current API does not have authentication. These endpoints should be protected before exposing the API publicly.

---

## Create Station

Creates a new radio station.

### Request

```http
POST /api/v1/stations
Content-Type: application/json
```

### Required Fields

| Field | Type | Required |
|---|---|---|
| `id` | string | Yes |
| `name` | string | Yes |

### Example

```bash
curl -X POST \
  https://rizfm.pkasemer.com/api/v1/stations \
  -H "Content-Type: application/json" \
  -d '{
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
    "logoUrl": null,
    "isFeatured": false,
    "isActive": true
  }'
```

### Response

```json
{
  "id": "example-fm",
  "name": "Example FM",
  "frequency": "100.0 FM",
  "city": "Kampala",
  "genres": [
    "Music"
  ],
  "languages": [
    "English"
  ],
  "streamUrl": "https://example.com/stream",
  "streamType": "mp3",
  "bitrate": 128,
  "website": "https://example.com",
  "logoUrl": null,
  "isFeatured": false,
  "isActive": true,
  "streamReachable": null,
  "lastChecked": null
}
```

HTTP status:

```text
201 Created
```

---

## Update Station

Updates an existing station.

Only the fields that need to be changed need to be included.

### Request

```http
PUT /api/v1/stations/:id
Content-Type: application/json
```

### Example

```bash
curl -X PUT \
  https://rizfm.pkasemer.com/api/v1/stations/example-fm \
  -H "Content-Type: application/json" \
  -d '{
    "isFeatured": true,
    "streamUrl": "https://new-stream.example.com/live"
  }'
```

### Response

```json
{
  "id": "example-fm",
  "name": "Example FM",
  "frequency": "100.0 FM",
  "city": "Kampala",
  "genres": [
    "Music"
  ],
  "languages": [
    "English"
  ],
  "streamUrl": "https://new-stream.example.com/live",
  "streamType": "mp3",
  "bitrate": 128,
  "website": "https://example.com",
  "logoUrl": null,
  "isFeatured": true,
  "isActive": true,
  "streamReachable": null,
  "lastChecked": null
}
```

---

## Delete Station

Deletes a station.

### Request

```http
DELETE /api/v1/stations/:id
```

### Example

```bash
curl -X DELETE \
  https://rizfm.pkasemer.com/api/v1/stations/example-fm
```

### Response

```json
{
  "message": "Station deleted",
  "id": "example-fm"
}
```

---

# Privacy and Data Deletion

Public pages (HTML, not part of `/api/v1`) used for App Store and Google Play submission:

| Method | Page | Use it for |
|---|---|---|
| `GET` | `/privacy` (alias `/privacy-policy`) | **Privacy Policy URL** in App Store Connect and Google Play Console |
| `GET` | `/delete-data` (alias `/data-deletion`) | **Data deletion URL** in the Google Play Data safety form |

```text
https://rizfm.pkasemer.com/privacy
https://rizfm.pkasemer.com/delete-data
```

The app has no user accounts and the API stores no personal data, so there is no server-side
user data to delete. The pages explain what is stored on the device and how to remove it.

Configure the text with environment variables (see `.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `PRIVACY_CONTACT_EMAIL` | empty | Contact address shown on both pages. **Set this before submitting.** |
| `PRIVACY_OPERATOR_NAME` | `SOFIZ FM` | Publisher name shown in the policy |
| `APP_NAME` | `SOFIZ FM` | App name shown in the policy |
| `PUBLIC_BASE_URL` | `https://rizfm.pkasemer.com` | Public origin of this service |

---

# Station Object

The standard station object contains the following fields.

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique station identifier |
| `name` | string | Station name |
| `frequency` | string/null | FM frequency |
| `city` | string/null | Station location |
| `genres` | array | Station genres |
| `languages` | array | Broadcast languages |
| `streamUrl` | string/null | Direct online stream URL |
| `streamType` | string/null | Stream format |
| `bitrate` | integer/null | Stream bitrate in kbps |
| `website` | string/null | Station website |
| `logoUrl` | string/null | Station logo |
| `isFeatured` | boolean | Whether the station is featured |
| `isActive` | boolean | Whether the station is active |
| `streamReachable` | boolean/null | Last known stream availability |
| `lastChecked` | string/null | Last stream check timestamp |

---

# Using the API in a Radio Player

The intended client flow is:

```text
1. Fetch stations
       ↓
2. Display station list
       ↓
3. User selects station
       ↓
4. Read streamUrl
       ↓
5. Pass streamUrl to audio player
       ↓
6. Start playback
```

Example:

```javascript
const response = await fetch(
  "https://rizfm.pkasemer.com/api/v1/stations"
);

const result = await response.json();

const station = result.data[0];

console.log(station.name);
console.log(station.streamUrl);

// Pass station.streamUrl to your audio player.
```

A mobile application should generally use:

```javascript
station.streamUrl
```

as the source URL for the audio player.

---

# Recommended Client Behaviour

## Loading Stations

On application startup:

```http
GET /api/v1/stations?active=true
```

## Home Screen

For a featured section:

```http
GET /api/v1/stations/featured
```

## Search

For station search:

```http
GET /api/v1/stations?search=capital
```

## Browse by Genre

```http
GET /api/v1/stations?genre=Music
```

## Browse by City

```http
GET /api/v1/stations?city=Kampala
```

## Playing a Station

The client should use:

```text
station.streamUrl
```

and pass it directly to its audio playback library.

---

# Error Responses

Errors are returned as JSON.

## Example

```json
{
  "error": "Station not found"
}
```

## HTTP Status Codes

| Status | Meaning |
|---:|---|
| `200` | Request successful |
| `201` | Resource created |
| `400` | Invalid request |
| `404` | Resource not found |
| `409` | Resource already exists |
| `500` | Internal server error |

---

# Common Errors

## Station Not Found

```http
GET /api/v1/stations/unknown-station
```

Response:

```json
{
  "error": "Station not found"
}
```

Status:

```text
404
```

---

## Duplicate Station

Creating a station using an existing ID:

```http
POST /api/v1/stations
```

Response:

```json
{
  "error": "Station with this id already exists"
}
```

Status:

```text
409
```

---

## Missing Required Fields

Creating a station without `id` or `name`:

```json
{
  "name": "Example FM"
}
```

Response:

```json
{
  "error": "Missing required fields: id"
}
```

Status:

```text
400
```

---

# CORS

The API currently supports Cross-Origin Resource Sharing (CORS).

This allows applications running on different domains to consume the API.

For example:

```text
https://myradioapp.com
```

can make requests to:

```text
https://rizfm.pkasemer.com
```

---

# Authentication

The current API does not require authentication.

The following endpoints should be considered **administrative**:

```text
POST   /api/v1/stations
PUT    /api/v1/stations/:id
DELETE /api/v1/stations/:id
POST   /api/v1/stations/:id/check
POST   /api/v1/stations/check-all
```

Before exposing these endpoints publicly, implement authentication and authorization.

Recommended options include:

- API keys
- JWT authentication
- Admin accounts
- Role-based access control

---

# Stream URLs

Radio station stream URLs can change without notice.

A station may:

- Change its streaming provider
- Change its streaming port
- Change its stream path
- Temporarily go offline
- Move from HTTP to HTTPS
- Replace an MP3 stream with another format

The stream monitoring endpoints can be used to detect unavailable endpoints.

However, a successful HTTP response does not necessarily mean the response contains playable audio.

---

# HTTP vs HTTPS Streams

Some radio stations may provide HTTP streams.

For example:

```text
http://example.com/stream
```

Mobile platforms may restrict insecure HTTP connections.

Where possible, stations should provide HTTPS streams:

```text
https://example.com/stream
```

If an HTTP-only stream needs to be supported, the application may require an appropriate secure proxy or streaming gateway.

---

# API Versioning

The current API version is:

```text
v1
```

All application endpoints use:

```text
/api/v1
```

Example:

```text
https://rizfm.pkasemer.com/api/v1/stations
```

Breaking API changes should be introduced through a new API version rather than changing the existing `v1` contract.

---

# Example Application Flow

A typical RizFM client can work as follows:

```text
                    RizFM API
                        │
                        ▼
              GET /stations
                        │
                        ▼
                 Station List
                        │
             ┌──────────┴──────────┐
             │                     │
             ▼                     ▼
        Capital FM             Beat FM
             │                     │
             ▼                     ▼
        streamUrl              streamUrl
             │                     │
             └──────────┬──────────┘
                        ▼
                   Audio Player
                        │
                        ▼
                     Playing
```

The API provides station discovery and metadata. The actual audio stream is delivered directly by the radio station's streaming server.

---

# Future Features

Potential future API features include:

- Station categories
- Country support
- Station logos
- Recently played stations
- Popular stations
- User favourites
- Recently played history
- Now-playing metadata
- Currently playing song
- Artist and track information
- Station schedules
- Podcasts
- Authentication
- Admin dashboard
- API rate limiting
- Automated stream monitoring
- Stream uptime statistics
- Multiple stream URLs per station
- Automatic fallback streams
- Push notifications for station outages

---

# API Example

A minimal client implementation:

```javascript
async function getStations() {
  const response = await fetch(
    "https://rizfm.pkasemer.com/api/v1/stations?active=true"
  );

  if (!response.ok) {
    throw new Error("Unable to load stations");
  }

  const result = await response.json();

  return result.data;
}

async function getStation(id) {
  const response = await fetch(
    `https://rizfm.pkasemer.com/api/v1/stations/${id}`
  );

  if (!response.ok) {
    throw new Error("Station not found");
  }

  return response.json();
}
```

---

# License

Specify the project's license here.

For example:

```text
Copyright © 2026 RizFM.

All rights reserved.
```