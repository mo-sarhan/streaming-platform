# Streaming Platform

A video streaming backend built with **FastAPI**, **PostgreSQL**, **Celery**, **RabbitMQ**, and **S3-compatible object storage**. Upload an MP4, and the platform transcodes it into multiple HLS renditions in the background so it can be played with adaptive bitrate streaming.

## Features

- Upload MP4 videos through a REST API
- Background transcoding with Celery workers
- Adaptive HLS output (360p / 720p / 1080p, depending on the source resolution)
- Master playlist generation for automatic quality selection
- Video status tracking (`pending` → `processing` → `success` / `failed`)
- Presigned playback URLs and a streaming endpoint for HLS files
- Browser player with manual/automatic quality selection using `hls.js`
- Database migrations with Alembic
- Local development stack via Docker Compose (PostgreSQL, Redis, RabbitMQ, pgAdmin, S3-compatible storage)

## Architecture

```
                 ┌─────────────┐
  Browser ──────▶│  FastAPI    │──────▶ PostgreSQL (metadata)
  (index.html)   │  /videos    │
                 └──────┬──────┘
                        │ enqueue task
                        ▼
                 ┌─────────────┐        ┌──────────────────┐
                 │  RabbitMQ   │───────▶│  Celery worker   │
                 └─────────────┘        │  ffmpeg / ffprobe│
                                        └────────┬─────────┘
                                                 │ upload HLS
                                                 ▼
                                        ┌──────────────────┐
                                        │ S3-compatible    │
                                        │ storage (videos) │
                                        └──────────────────┘
```

## Tech Stack

| Layer | Technology |
| --- | --- |
| API | FastAPI, Uvicorn, Pydantic v2 |
| Database | PostgreSQL 17, SQLAlchemy 2, Alembic |
| Background jobs | Celery, RabbitMQ |
| Media processing | FFmpeg / FFprobe |
| Object storage | S3-compatible API (LocalEmu / LocalStack), boto3 |
| Frontend | HTML + `hls.js` |

## Project Structure

```
chat_system/
├── app/
│   ├── main.py                 # FastAPI app and CORS setup
│   ├── celery_app.py           # Celery configuration
│   ├── core/config.py          # Environment settings
│   ├── db/
│   │   ├── database.py         # SQLAlchemy engine/session
│   │   └── base.py             # Declarative Base + DB health check
│   ├── models/                 # SQLAlchemy models (User, Video)
│   ├── schemas/                # Pydantic request/response schemas
│   ├── routers/videos.py       # Upload and playback endpoints
│   ├── services/
│   │   ├── storage.py          # S3 storage client
│   │   └── transcoder.py       # FFmpeg HLS transcoding
│   └── tasks/video.py          # Celery video processing task
├── alembic/                    # Database migrations
├── docker-compose.yml          # Local infrastructure services
├── index.html                  # Demo video player
├── player.js                   # HLS player logic
├── requirements.txt
└── .env                        # Local configuration (not committed)
```

## Prerequisites

- Python 3.12+
- Docker and Docker Compose
- FFmpeg and FFprobe installed locally (required by the Celery worker)
- AWS CLI (optional, to create the storage bucket)

## Getting Started

### 1. Clone the repository

```bash
git clone git@github.com:mo-sarhan/streaming-platform.git
cd streaming-platform
```

### 2. Create a virtual environment and install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the project root:

```env
DATABASE_URL=postgresql+psycopg://stream_user:stream_password@localhost:5432/stream_db
AWS_ENDPOINT_URL=http://localhost:4566
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
REGION_NAME=us-east-1
CELERY_BROKER_URL=amqp://guest:guest@localhost:5672//
```

| Variable | Description |
| --- | --- |
| `DATABASE_URL` | PostgreSQL connection string |
| `AWS_ENDPOINT_URL` | S3-compatible storage endpoint |
| `AWS_ACCESS_KEY_ID` | Storage access key |
| `AWS_SECRET_ACCESS_KEY` | Storage secret key |
| `REGION_NAME` | Storage region |
| `CELERY_BROKER_URL` | RabbitMQ broker URL |

> **Note:** The current storage client (`app/services/storage.py`) has the endpoint and credentials hardcoded to the local defaults. Update it there as well if you use different values.

### 4. Start the infrastructure

```bash
docker compose up -d
```

This starts:

| Service | Address |
| --- | --- |
| PostgreSQL | `localhost:5432` |
| RabbitMQ | `localhost:5672` (management UI on `localhost:15672`) |
| S3-compatible storage | `localhost:4566` |
| pgAdmin | `localhost:8080` |

### 5. Create the storage bucket

The application expects a bucket named `videos`:

```bash
aws --endpoint-url=http://localhost:4566 s3 mb s3://videos
```

### 6. Run database migrations

```bash
alembic upgrade head
```

### 7. Start the API server

```bash
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`, and interactive docs at `http://127.0.0.1:8000/docs`.

### 8. Start a Celery worker

In a separate terminal:

```bash
celery -A app.celery_app.celery_app worker --loglevel=info
```

### 9. Run the demo player

Serve the frontend on port `5500` (the API's CORS configuration allows this origin):

```bash
python -m http.server 5500
```

Open `http://localhost:5500`. Update `videoId` in `player.js` to the ID of a processed video.

## API Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/` | API root |
| `GET` | `/health/database` | Database connectivity check |
| `POST` | `/videos/upload` | Upload an MP4 (`title` form field + `file`) |
| `GET` | `/videos/{video_id}/play` | Get video info and a presigned master playlist URL |
| `GET` | `/videos/{video_id}/hls/{object_path}` | Stream HLS playlists and segments |

### Upload example

```bash
curl -X POST http://127.0.0.1:8000/videos/upload \
  -F "title=My first video" \
  -F "file=@sample.mp4;type=video/mp4"
```

The upload returns immediately with a `pending` video. Processing happens asynchronously in the Celery worker.

## Video Processing Lifecycle

1. The uploaded file is stored under `originals/{uuid}/original.mp4`.
2. A `Video` row is created with status `pending`.
3. The `process_video` Celery task atomically claims the row and sets it to `processing`.
4. The original is downloaded to a temporary directory.
5. FFmpeg transcodes it into HLS renditions no larger than the source height (360p, 720p, 1080p).
6. A `master.m3u8` playlist is generated and all HLS files are uploaded under `hls/{video_id}/`.
7. The video is marked `success` and its `hls_path` is saved.
8. On failure, partially uploaded HLS files are removed and the video is marked `failed` with a failure message.

## Renditions

| Resolution | Video bitrate | Bandwidth |
| --- | --- | --- |
| 360p | 800k | 900 kbps |
| 720p | 2800k | 3.1 Mbps |
| 1080p | 5000k | 5.5 Mbps |

Segments are 6 seconds long and use independent segments for clean quality switching.

## Database Migrations

Create a new migration after changing models:

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

Roll back one migration:

```bash
alembic downgrade -1
```

## Notes and Limitations

- Authentication is not implemented yet. Uploads are assigned to a temporary user ID (`1`), so a matching user row must exist.
- The demo player has a hardcoded `videoId` and calls `http://127.0.0.1:8000` directly.
- CORS currently allows only `http://localhost:5500`.
- The storage client uses hardcoded local credentials rather than reading `settings`.
- `LocalStorage` in `app/services/storage.py` is currently unused; only `S3Storage` is active.
- Uploads accept MP4 only (`video/mp4`).
