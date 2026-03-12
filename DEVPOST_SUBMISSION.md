# StoryForge Pro — DevPost Submission Text

## Summary

StoryForge Pro is a Creative Storyteller AI agent that transforms any script into rich visual content — comics, manga, storyboards, and cinematic trailers — all powered by Google Gemini and Vertex AI.

## Inspiration

Traditional script-to-visual workflows require artists, storyboard teams, and video editors. We wanted to democratize visual storytelling: paste a script, pick a style, and let AI do the rest. StoryForge Pro breaks the "text box" paradigm by producing interleaved multimodal output — text, images, and video woven together in a single creative flow.

## What It Does

Users paste any script (screenplay, story outline, or narrative) and StoryForge Pro's AI agent pipeline:
1. **Parses** the script into 4-6 structured scenes using Gemini 2.5 Flash
2. **Generates** visual content based on the chosen mode:
   - **Comic Mode:** Full-page American comic panels with speech bubbles, dialogue, and bold art
   - **Manga Mode:** Seinen/Shonen-style black & white panels with Japanese visual storytelling
   - **Storyboard Mode:** Technical production frames with camera angles and shot descriptions
   - **Trailer Mode:** Cinematic video clips via Veo 3.1, auto-assembled into a complete trailer
3. **Exports** results as downloadable PDFs or MP4 trailers

The app features 12+ visual styles, 5 Director's Eye styles for trailers (Nolan, Cameron, Ritchie, Mani Ratnam, Nelson), real-time WebSocket progress tracking, and a conversational Story Chat for script development.

## How We Built It

**Frontend:** React 18 + TypeScript + Vite with Framer Motion animations and Zustand state management. Real-time generation progress via WebSocket.

**Backend:** FastAPI (Python 3.12) with Google's Agent Development Kit (ADK) orchestrating a hierarchy of specialized agents:
- **HAL** (Director): Root orchestrator coordinating the full pipeline
- **R2D2** (Visual Artist): Generates comics, manga, and storyboard frames
- **WALL-E** (Video Producer): Creates trailer clips and assembles with ffmpeg
- **Editor**: Conversational story refinement

**AI Models (Vertex AI):**
- Gemini 2.5 Flash — script parsing, scene analysis, story chat
- Gemini 2.5 Flash Image — interleaved text + image generation for comics/manga
- Veo 3.1 — cinematic video clip generation for trailers

**Infrastructure:** Docker Compose on GCP Compute Engine, MongoDB for project storage, Cloudflare for SSL/CDN.

## Challenges We Ran Into

- **Rate limits:** Vertex AI image generation caps at ~10 RPM. We implemented 3-retry logic with 15s backoff and user-friendly congestion popups instead of hard failures.
- **Scene count control:** Gemini tends to under-generate (1 scene) or over-generate (10+). Solved with explicit prompting + auto-retry + post-processing clamping to 4-6 scenes.
- **Text accuracy in AI images:** Speech bubbles and titles sometimes have spelling errors. Aggressive prompt engineering with explicit spelling rules reduces but doesn't fully eliminate this.
- **All-or-nothing UX:** Partial generation (some pages failing) creates a worse experience than retrying. We clear and retry rather than showing incomplete output.

## Accomplishments We're Proud Of

- Interleaved generation produces visually cohesive comics where text and imagery feel naturally integrated
- The ADK agent hierarchy mirrors real creative production pipelines (Director → Artists → Editors)
- Real-time WebSocket progress transforms waiting from frustrating to engaging
- 4 distinct output modes from a single script input, each with multiple style options
- Full trailer assembly pipeline: script → scenes → Veo clips → ffmpeg → downloadable MP4

## What We Learned

- Gemini's interleaved output is a game-changer for creative applications — generating text + images in a single pass produces far more cohesive results than separate pipelines
- ADK's agent hierarchy maps naturally to domain-specific workflows
- Prompt engineering for visual accuracy (especially text rendering) is an ongoing challenge with AI image generation
- WebSocket-based progress tracking is essential for long-running AI generation tasks

## What's Next

- Firebase Phone Auth for user management
- Post-processing text overlays via Pillow for pixel-perfect dialogue rendering
- Cloud Run migration for auto-scaling
- Additional output modes: graphic novel, motion comic

## Built With

- Google Gemini 2.5 Flash
- Google Gemini 2.5 Flash Image
- Google Veo 3.1
- Google GenAI SDK
- Google ADK (Agent Development Kit)
- Google Cloud Compute Engine
- Google Cloud Storage
- FastAPI
- React
- TypeScript
- MongoDB
- Docker
- ffmpeg
- Cloudflare
