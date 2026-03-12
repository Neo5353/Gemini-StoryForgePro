# 🎬 StoryForge Pro — Script-to-Screen AI Agent

> Paste a script → AI generates comics, manga, storyboards, or cinematic trailers. Powered by Google Gemini & Vertex AI.

**Live Demo:** [https://storyforgepro.cc](https://storyforgepro.cc)

---

## What It Does

StoryForge Pro is a **Creative Storyteller** AI agent that transforms any script into rich, multimodal visual content. It breaks the "text box" paradigm by producing interleaved text and imagery — comics, manga, storyboards, and full cinematic trailers — all from a single script input.

### 🎯 Key Features

- **4 Output Modes:** Comic, Manga, Storyboard, Trailer
- **12+ Visual Styles:** American, Seinen, Shonen, Retro, Indie, European, and more
- **5 Director's Eye Styles** (Trailer mode): Nolan, Cameron, Ritchie, Mani Ratnam, Nelson
- **AI Script Analysis:** Paste any script → Gemini parses it into 4-6 visual scenes with characters, locations, mood, and dialogue
- **Interleaved Generation:** Gemini generates comic/manga pages with panels, speech bubbles, and text — all in a single creative pass
- **Video Trailers:** Veo 3.1 generates scene clips → auto-assembled into a full trailer with ffmpeg
- **Real-time Progress:** WebSocket-powered live generation progress with scene-by-scene updates
- **Story Chat:** Conversational AI editor to develop and refine your story
- **Download & Export:** Download trailers as `.mp4`, print comics/manga/storyboards as PDF

### 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│              Frontend (React + TypeScript)        │
│         Vite • Framer Motion • Zustand            │
│    storyforgepro.cc (Cloudflare SSL + CDN)        │
└──────────────────┬──────────────────────────────┘
                   │ REST API + WebSocket
                   ▼
┌─────────────────────────────────────────────────┐
│              Backend (FastAPI + Python)           │
│                                                   │
│  ┌─────────────┐  ┌──────────────────────────┐   │
│  │  ADK Agent   │  │   Google GenAI SDK        │   │
│  │  Hierarchy   │  │                           │   │
│  │             │  │  Gemini 2.5 Flash (text)  │   │
│  │  HAL        │  │  Gemini 2.5 Flash (image) │   │
│  │  ├── R2D2   │  │  Veo 3.1 (video)          │   │
│  │  ├── WALL-E │  │                           │   │
│  │  └── Editor │  └──────────────────────────┘   │
│  └─────────────┘                                  │
│                                                   │
│  ┌──────────────────┐  ┌─────────────────────┐   │
│  │  Script Parser    │  │  ffmpeg (trailer     │   │
│  │  Scene Analysis   │  │  assembly)           │   │
│  │  Style Engine     │  └─────────────────────┘   │
│  └──────────────────┘                             │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│            Google Cloud Platform                  │
│                                                   │
│  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ Compute Engine│  │     Vertex AI             │  │
│  │ (Docker host) │  │  • Gemini 2.5 Flash       │  │
│  │               │  │  • Gemini 2.5 Flash Image │  │
│  └──────────────┘  │  • Veo 3.1                 │  │
│                     └──────────────────────────┘  │
│  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  MongoDB 7    │  │  Cloud Storage (GCS)      │  │
│  │  (projects)   │  │  (generated assets)       │  │
│  └──────────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

### 🤖 AI Agent Hierarchy (ADK)

StoryForge Pro uses Google's **Agent Development Kit (ADK)** to orchestrate a team of specialized AI agents:

| Agent | Role | Description |
|-------|------|-------------|
| **HAL** | Director | Root orchestrator — coordinates the entire pipeline |
| **R2D2** | Visual Artist | Generates comic pages, manga panels, storyboard frames |
| **WALL-E** | Video Producer | Creates trailer clips via Veo 3.1, assembles with ffmpeg |
| **Editor** | Script Editor | Conversational story development and refinement |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18, TypeScript, Vite, Framer Motion, Zustand |
| **Backend** | Python 3.12, FastAPI, uvicorn, WebSocket |
| **AI Models** | Gemini 2.5 Flash (text), Gemini 2.5 Flash Image (interleaved), Veo 3.1 (video) |
| **AI Framework** | Google GenAI SDK, Google ADK (Agent Development Kit) |
| **Database** | MongoDB 7 |
| **Video** | ffmpeg (trailer assembly, clip processing) |
| **Deployment** | Docker Compose on GCP Compute Engine |
| **SSL/CDN** | Cloudflare |
| **Cloud** | Google Cloud Platform (Vertex AI, Compute Engine) |

---

## Google Cloud Services Used

1. **Vertex AI** — Gemini 2.5 Flash for script parsing and story generation
2. **Vertex AI** — Gemini 2.5 Flash Image for interleaved comic/manga/storyboard generation
3. **Vertex AI** — Veo 3.1 for cinematic video clip generation
4. **Compute Engine** — Docker Compose deployment (e2-medium VM)
5. **Cloud Storage** — Generated asset storage (images, videos)

---

## Quick Start (Local Development)

### Prerequisites
- Python 3.12+
- Node.js 22+
- MongoDB 7 (or Docker)
- GCP project with Vertex AI enabled
- `gcloud` CLI authenticated

### 1. Clone & Setup Backend

```bash
git clone https://github.com/Neo5353/Gemini-StoryForgePro.git
cd Gemini-StoryForgePro/backend

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Create .env
cat > .env << EOF
STORYFORGE_LOCAL=false
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=storyforge
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_GENAI_USE_VERTEXAI=true
GCS_BUCKET=your-gcs-bucket
EOF

# Start backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Setup Frontend

```bash
cd ../frontend

# Create .env
cat > .env << EOF
VITE_API_URL=http://localhost:8000/api
VITE_WS_URL=ws://localhost:8000/ws
EOF

npm install
npx vite --host 0.0.0.0
```

### 3. Start MongoDB

```bash
# Option A: Docker
docker run -d -p 27017:27017 mongo:7

# Option B: Local install
mongod
```

Open `http://localhost:5173` and start creating!

---

## Production Deployment (Docker Compose)

```bash
# On a GCP Compute Engine VM with Docker installed:

git clone https://github.com/Neo5353/Gemini-StoryForgePro.git
cd Gemini-StoryForgePro

# Set environment variables
export GOOGLE_CLOUD_PROJECT=your-gcp-project-id
export GCS_BUCKET=your-gcs-bucket

# Build and run
docker compose up -d --build

# App runs on port 80 (HTTP) and 8080
```

### Docker Services

| Service | Port | Description |
|---------|------|-------------|
| `frontend` | 80, 8080 | nginx serving React app + reverse proxy to backend |
| `backend` | 8000 | FastAPI + WebSocket server |
| `mongo` | 27017 | MongoDB 7 with persistent volume |

---

## How It Works

1. **Paste a Script** → Any format: screenplay, story outline, narrative
2. **AI Analyzes** → Gemini 2.5 Flash parses into 4-6 structured scenes with characters, locations, mood, dialogue
3. **Choose Mode** → Comic, Manga, Storyboard, or Trailer
4. **AI Generates** → 
   - Comics/Manga: Gemini generates full pages with panels, speech bubbles, and art in one interleaved pass
   - Storyboard: Technical frames with shot descriptions and camera angles
   - Trailer: Veo 3.1 generates 8-second clips per scene → ffmpeg assembles into a full trailer
5. **Download** → Export as PDF (comics/manga/storyboard) or MP4 (trailer)

---

## Project Structure

```
Gemini-StoryForgePro/
├── backend/
│   ├── app/
│   │   ├── agents/          # ADK agent hierarchy (HAL, R2D2, WALL-E, Editor)
│   │   ├── config/          # Settings, director styles
│   │   ├── models/          # Pydantic schemas
│   │   ├── routes/          # API endpoints
│   │   ├── services/        # Core services (parser, generation, video, storage)
│   │   └── main.py          # FastAPI app entry
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/      # React components (output, video, editor, etc.)
│   │   ├── pages/           # Home, Projects, Project detail
│   │   ├── services/        # API client, WebSocket
│   │   ├── stores/          # Zustand state management
│   │   └── types/           # TypeScript types
│   ├── Dockerfile
│   └── nginx.conf
├── docker-compose.yml
└── README.md
```

---

## Findings & Learnings

- **Interleaved generation** is the killer feature — Gemini generating text + images in a single pass produces cohesive visual storytelling that separate text-then-image pipelines can't match
- **Rate limits are real** — Vertex AI image generation at ~10 RPM requires careful retry logic with backoff; we use 3 retries with 15s backoff
- **Scene count control** matters — AI models tend to under-generate (1-2 scenes) or over-generate (10+); explicit prompting + post-processing clamping to 4-6 scenes was essential
- **Text in AI images** is still imperfect — aggressive spelling enforcement in prompts reduces but doesn't eliminate text rendering errors; future improvement: overlay text with Pillow
- **All-or-nothing generation** UX — partial/failed pages create a worse experience than retrying; we clear and retry rather than showing incomplete output
- **WebSocket for progress** — real-time generation feedback transforms waiting from frustrating to engaging
- **ADK agent hierarchy** maps naturally to creative workflows — Director → Artists → Editors mirrors real production pipelines

---

## Built For

🏆 [Gemini Live Agent Challenge](https://geminiliveagentchallenge.devpost.com/) — Creative Storyteller Category

**Category:** Creative Storyteller ✍️ — Multimodal Storytelling with Interleaved Output

---

## License

MIT
