# RizFM API

RizFM API is a REST API for discovering and streaming online radio stations. The catalogue is built around Ugandan stations, with a few international favourites.

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
| `country` | string | No | — | Filter by country, e.g. `Uganda`, `United Kingdom` |
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

### Filter by country

```bash
curl "https://rizfm.pkasemer.com/api/v1/stations?country=United%20Kingdom"
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
      "country": "Uganda",
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
      "lastChecked": null,
      "streamStatus": "unknown",
      "lastOnlineAt": null,
      "responseTimeMs": null,
      "loudnessLufs": null,
      "loudnessMeasuredAt": null
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
  "country": "Uganda",
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
  "lastChecked": null,
  "streamStatus": "unknown",
  "lastOnlineAt": null,
  "responseTimeMs": null,
  "loudnessLufs": null,
  "loudnessMeasuredAt": null
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
      "country": "Uganda",
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
      "lastChecked": null,
      "streamStatus": "unknown",
      "lastOnlineAt": null,
      "responseTimeMs": null,
      "loudnessLufs": null,
      "loudnessMeasuredAt": null
    }
  ]
}
```

---

# Stream Monitoring

A separate `health-worker` process checks every active station's stream automatically and stores the
result, so the app can warn listeners, or hide a dead station, before they press play. Every station
returns these fields (all `null` / `unknown` until its first check):

| Field | Type | Meaning |
|---|---|---|
| `streamStatus` | `online` \| `degraded` \| `offline` \| `unknown` | The status below. |
| `streamReachable` | boolean/null | Always consistent with `streamStatus`: `true` for `online` and `degraded`, `false` for `offline`, `null` for `unknown`. |
| `lastChecked` | string/null | When the last probe finished, pass or fail (ISO 8601, UTC). |
| `lastOnlineAt` | string/null | The last time a probe passed (ISO 8601, UTC). Lets the app say "offline since yesterday". |
| `responseTimeMs` | number/null | Time to the first audio byte on the last probe. `null` if that probe failed. |

## What "working" means

A URL that answers is not enough. A stream counts as working only when **all** of these are true:

1. The connection succeeds (DNS, TCP and TLS) within 8 seconds.
2. The HTTP status is `200` (up to 5 redirects are followed).
3. The `Content-Type` is audio (`audio/*`, `application/ogg`) or an HLS / playlist type. An HTML or JSON
   answer means the server is up but the stream is not, typical for "station offline" pages. A
   `.pls` or `.m3u` playlist is followed to the stream it points to (one level). A response with no
   useful `Content-Type` is judged by the bytes themselves.
4. **Audio bytes really arrive**: at least 4 KB of the first 16 KB within the same 8 seconds. A stream
   that connects and then sends nothing is dead.

The probe is a plain `GET` (never `HEAD`, which many Icecast, Shoutcast and Streamtheworld servers answer
wrongly), sent with `User-Agent: Mozilla/5.0 (RIZFM health check)` and `Icy-MetaData: 0`, and closed as
soon as enough bytes have arrived. Old Shoutcast servers that answer `ICY 200 OK` are supported, and a
trailing `;` in a URL such as `http://host:8000/;` is kept. Only public `http` and `https` hosts are
probed, including every redirect target.

## Status values

| `streamStatus` | Meaning | `streamReachable` |
|---|---|---|
| `online` | The last check passed. | `true` |
| `degraded` | Reachable but slow (the first audio byte took over 4 seconds), or silent in the daily deep check. It plays, but may be poor. | `true` |
| `offline` | Failed on **3 checks in a row**. | `false` |
| `unknown` | Never checked, or just added, or its `streamUrl` just changed. | `null` |

A single failure never changes the status the app sees: a station goes `offline` only after 3 failures
in a row, and goes back to `online` after 1 success. The **daily deep check** reuses the loudness job's
30-second capture: if it decodes only silence (`-inf` LUFS), the station is `degraded`.

## How often

| State | Re-checked every |
|---|---|
| Healthy (`online`, `degraded`) | 5 minutes |
| Suspect (1 or 2 failures so far) | 1 minute, until it passes or reaches 3 failures |
| Confirmed `offline` | 15 minutes |
| New station, or `streamUrl` changed | Straight away (within seconds) |

Never more often than once a minute (each probe counts as a listener on the station's server). Checks
are spread out with a fixed 0 to 59 second offset per station, and at most 8 run at once.

## Alerts

Alerts are logged, and sent to `HEALTH_ALERT_WEBHOOK_URL` if set (a JSON `POST` with `text` and `content`
for Slack, Teams or Discord style webhooks, plus `event` and `stationId`):

- when a station goes `offline`, and again when it recovers (with how long it was down),
- a reminder every 24 hours while it stays offline, because its stream URL has probably changed.

Never one per failed probe.

## Health detail (debugging)

Kept out of the public station response: consecutive failures, the last error and the probe history.

```http
GET /api/v1/stations/:id/health
```

```json
{
  "id": "kfm",
  "streamStatus": "online",
  "streamReachable": true,
  "lastChecked": "2026-11-17T09:01:00+00:00",
  "lastOnlineAt": "2026-11-17T09:00:00+00:00",
  "responseTimeMs": 250,
  "consecutiveFailures": 1,
  "lastError": "http_404",
  "offlineSince": null,
  "nextCheckAt": "2026-11-17T09:02:00+00:00",
  "uptime30d": 99.8,
  "httpsOnly": false,
  "history": [
    { "checkedAt": "2026-11-17T09:01:00+00:00", "ok": false, "error": "http_404", "responseMs": null },
    { "checkedAt": "2026-11-17T09:00:00+00:00", "ok": true, "error": null, "responseMs": 250 }
  ]
}
```

`lastError` is one of: `dns`, `connect_timeout`, `connect_error`, `tls`, `http_<status>` (for example
`http_404`), `not_audio` (wrong content type), `no_data` (connected but no audio), `too_many_redirects`,
`bad_url` (not a public http(s) address) or `silence` (the daily deep check).

## Admin table

```http
GET /api/v1/streams/health
```

One row per station, offline first: `id`, `name`, `isActive`, `streamStatus`, `lastOnlineAt`,
`lastError`, `consecutiveFailures`, `uptime30d` (percent of probes that passed in the last 30 days) and
`httpOnly`. **`httpOnly: true` flags a plain `http://` stream.** iPhones block those by default, so they can
pass the server's probe and still fail in the app.

## Running it

```bash
docker compose up -d --build            # starts radio-api, loudness-worker and health-worker
docker compose logs -f health-worker
docker compose exec radio-api flask --app run streams status
docker compose exec radio-api flask --app run streams check --station kfm   # probe now
```

| Variable | Default | Purpose |
|---|---|---|
| `HEALTH_HEALTHY_INTERVAL` | `300` | Seconds between checks of a healthy station (minimum 60) |
| `HEALTH_SUSPECT_INTERVAL` | `60` | Seconds between checks after 1 or 2 failures (minimum 60) |
| `HEALTH_OFFLINE_INTERVAL` | `900` | Seconds between checks of an offline station (minimum 60) |
| `HEALTH_TICK_SECONDS` | `5` | How often the worker looks for stations that are due |
| `HEALTH_ALERT_WEBHOOK_URL` | empty | Chat webhook for offline, recovered and 24-hour reminder alerts |

**Geo-blocked streams:** a US or UK stream may only play in its own country. If the server is in
another region, its probe can fail even though the station works for listeners. Run the workers from a
region close to your listeners (Uganda or nearby).

---

## Check Station Stream

Runs one probe immediately and applies the same rules as the worker. It counts as one of the three
checks, so a single failed manual check does not take a station offline.

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
  "streamStatus": "online",
  "error": null,
  "lastChecked": "2026-11-17T09:30:00+00:00"
}
```

### Failed probe

`reachable` is the result of this one probe. `streamStatus` is the station's overall status, which does
not change until the third failure in a row.

```json
{
  "id": "capital-fm",
  "reachable": false,
  "streamStatus": "online",
  "error": "http_404",
  "lastChecked": "2026-11-17T09:30:00+00:00"
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
    "country": "Uganda",
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
  "country": "Uganda",
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
  "lastChecked": null,
  "streamStatus": "unknown",
  "lastOnlineAt": null,
  "responseTimeMs": null,
  "loudnessLufs": null,
  "loudnessMeasuredAt": null
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
  "country": "Uganda",
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
  "lastChecked": null,
  "streamStatus": "unknown",
  "lastOnlineAt": null,
  "responseTimeMs": null,
  "loudnessLufs": null,
  "loudnessMeasuredAt": null
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

# Loudness

Stations broadcast at very different volumes. The API measures how loud each station is and reports
the number, so the mobile app can turn loud stations down and listeners don't have to touch the
volume slider when they switch.

**The API only reports a number. It never changes the audio.** Listeners connect directly to the
station's own stream.

Every station has two extra fields, returned by both `GET /stations` and `GET /stations/:id`:

| Field | Type | Meaning |
|---|---|---|
| `loudnessLufs` | number/null | Integrated loudness in LUFS (ITU-R BS.1770 / EBU R128), one decimal place. Typical values are between -30 and -6. `null` until measured. |
| `loudnessMeasuredAt` | string/null | When the stored value was last updated (ISO 8601, UTC). |

Both are read-only: `POST` and `PUT` ignore them.

## How it is measured

A separate `loudness-worker` process (see `docker-compose.yml`) does the measuring with ffmpeg:

1. It captures about 30 seconds of the stream and measures integrated loudness with the `ebur128`
   filter. A phone plays a mono stream on both speakers, which is 3.01 LU louder than the single
   channel ffmpeg measures, so mono streams get that 3.01 LU added. (ffmpeg's own `-ac 2` upmix does
   not do this: it lowers each channel by 3 dB and reads the same as plain mono.)
2. A reading is rejected, and the previous value kept, if ffmpeg fails, less than 15 seconds of audio
   was decoded, or the result is silence, above -3 LUFS or below -45 LUFS (these are decode problems).
3. The published value is the **median of the last 5 accepted readings**, because live programming
   (music, talk, adverts) varies by a few dB.
4. Each active station is measured 4 times a day (06:00, 12:00, 18:00 and 23:00 East Africa Time).
   A station is also measured within about a minute when it is added, when its `streamUrl` changes
   (its old readings are discarded), and when it has never been measured.
5. At most 4 stations are measured at once, each with a 45 second hard limit. After 10 failed runs in
   a row a station is flagged for review in the logs, and its last good value stays in place.

Only public `http` and `https` stream URLs are measured. Stations on a geo-restricted stream (some US
and UK ones) stay `null` if the server's region is blocked.

## Loudness details (debugging)

```http
GET /api/v1/stations/:id/loudness
```

```bash
curl https://rizfm.pkasemer.com/api/v1/stations/kfm/loudness
```

```json
{
  "id": "kfm",
  "loudnessLufs": -16.5,
  "loudnessMeasuredAt": "2026-11-17T09:00:41.512340+00:00",
  "pending": false,
  "consecutiveFailures": 0,
  "history": [
    { "lufs": -16.3, "measuredAt": "2026-11-17T09:00:41.512340+00:00" },
    { "lufs": -17.0, "measuredAt": "2026-11-17T03:00:38.101922+00:00" }
  ]
}
```

`history` holds up to 50 accepted readings, newest first. A published value that looks wrong is
usually one bad capture, and shows up here.

## Running it

```bash
docker compose up -d --build            # starts radio-api and loudness-worker
docker compose logs -f loudness-worker  # watch measurements
docker compose exec radio-api flask --app run loudness status
docker compose exec radio-api flask --app run loudness measure --station kfm   # measure now
```

| Variable | Default | Purpose |
|---|---|---|
| `LOUDNESS_SLOTS` | `06:00,12:00,18:00,23:00` | Scheduled run times, East Africa Time (UTC+3) |
| `LOUDNESS_POLL_SECONDS` | `30` | How often the worker looks for stations waiting for a first or new measurement |
| `FFMPEG_BIN` | `ffmpeg` | Path to the ffmpeg binary |
| `LOUDNESS_ALLOW_PRIVATE_HOSTS` | off | Set to `1` only in development to measure a stream on localhost |

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
| `PRIVACY_OPERATOR_NAME` | `RIZFM` | Publisher name shown in the policy |
| `APP_NAME` | `RIZFM` | App name shown in the policy |
| `PUBLIC_BASE_URL` | `https://rizfm.pkasemer.com` | Public origin of this service |

---

# Station Object

The standard station object contains the following fields.

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique station identifier |
| `name` | string | Station name |
| `frequency` | string/null | FM frequency |
| `city` | string/null | Station city |
| `country` | string | Station country. Defaults to `Uganda` |
| `genres` | array | Station genres |
| `languages` | array | Broadcast languages |
| `streamUrl` | string/null | Direct online stream URL |
| `streamType` | string/null | Stream format |
| `bitrate` | integer/null | Stream bitrate in kbps |
| `website` | string/null | Station website |
| `logoUrl` | string/null | Station logo |
| `isFeatured` | boolean | Whether the station is featured |
| `isActive` | boolean | Whether the station is active |
| `streamReachable` | boolean/null | `true` for `online`/`degraded`, `false` for `offline`, `null` for `unknown`. See [Stream Monitoring](#stream-monitoring) |
| `lastChecked` | string/null | When the last stream probe finished (ISO 8601, UTC) |
| `streamStatus` | string | `online`, `degraded`, `offline` or `unknown` |
| `lastOnlineAt` | string/null | The last time a probe passed (ISO 8601, UTC) |
| `responseTimeMs` | number/null | Time to the first audio byte on the last probe |
| `loudnessLufs` | number/null | Integrated loudness in LUFS, one decimal place (for example `-17.4`). `null` until measured. See [Loudness](#loudness) |
| `loudnessMeasuredAt` | string/null | When `loudnessLufs` was last updated (ISO 8601, UTC) |

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