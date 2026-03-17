# AI Interview Platform

A comprehensive AI-powered interview system combining real-time video conferencing, AI interviewer agent, proctoring, and violation tracking.

## 🎯 Project Overview

This project implements an end-to-end AI interviewing platform that:
- **Schedules** interviews with candidates
- **Extracts** resume content and generates interview questions using AI (OpenAI GPT)
- **Conducts** real-time video interviews with an AI agent using LiveKit
- **Monitors** candidate behavior (head tracking, tab switching, copy/paste attempts, fullscreen enforcement)
- **Records** violation logs in JSON format for later review
- **Provides** a web-based UI (Streamlit) for scheduling and Next.js for the interview experience

---

## 📁 Project Structure

```
AI_Interview_Agent/
├── generate_token.py          # FastAPI backend - handles interview scheduling, room creation, token generation
├── agent.py                   # LiveKit AI Agent - conducts the actual interview
├── utils.py                   # Utility functions for resume extraction & interview plan generation
├── streamlit_app.py           # Streamlit web UI for scheduling interviews
├── requirements.txt           # Python dependencies
│
├── meet/                      # Next.js frontend - interview experience
│   ├── app/
│   │   ├── api/              # Next.js API routes
│   │   │   ├── connection-details/     # Endpoint to get LiveKit credentials
│   │   │   ├── save-interview-log/     # Endpoint to save violation logs
│   │   │   └── log-violations/         # (Legacy) endpoint for violation logging
│   │   ├── eye-test/         # Proctoring components
│   │   │   ├── EyeTestClient.tsx       # Dynamic import wrapper for head tracking
│   │   │   ├── EyeTestInner.tsx        # Head movement detection using TensorFlow
│   │   │   ├── BrowserProctor.tsx      # Tab/window/copy-paste/fullscreen enforcement
│   │   │   └── page.tsx                # Standalone demo page
│   │   ├── rooms/[roomName]/ # Interview room
│   │   │   ├── page.tsx                # Room page
│   │   │   └── PageClientImpl.tsx       # Main interview UI (LiveKit + Proctoring)
│   │   └── layout.tsx
│   ├── lib/
│   │   ├── usePerfomanceOptimiser.ts   # Performance optimization for video
│   │   ├── useSetupE2EE.ts             # End-to-end encryption setup
│   │   ├── KeyboardShortcuts.tsx       # Keyboard navigation
│   │   ├── SettingsMenu.tsx            # Camera/mic settings
│   │   └── types.ts                    # TypeScript type definitions
│   ├── package.json
│   └── next.config.js
│
├── interview-logs/            # (Generated) JSON violation logs
│   └── {interviewId}_violations.json
│
├── resumes/                   # (Generated) Uploaded candidate resumes
│   └── {candidate_name}_{filename}
│
└── .env.local                 # Environment variables (NOT in git)
```

---

## 🔧 Technology Stack

### Backend
- **FastAPI** - REST API for interview scheduling and room management
- **LiveKit API** - Real-time communication (video/audio)
- **OpenAI GPT** - Resume analysis and interview question generation
- **Uvicorn** - ASGI server
- **Streamlit** - Lightweight web UI for admin/scheduling

### Frontend (Interview Experience)
- **Next.js 15** - React framework with App Router
- **TypeScript** - Type safety
- **LiveKit Client SDK** - Video conferencing components
- **TensorFlow.js** - Client-side face detection for head tracking
- **MediaPipe** - Face landmark detection for proctoring

### Services
- **LiveKit Cloud** - Video conferencing infrastructure (requires account & API keys)
- **OpenAI API** - LLM for resume analysis and interview questions

---

## 🚀 Getting Started

### Prerequisites
- **Node.js** 18+ (for Next.js)
- **Python** 3.9+ 
- **LiveKit Account** (get API keys from [livekit.io](https://livekit.io))
- **OpenAI API Key** (get from [openai.com](https://openai.com))

### Step 1: Clone & Install Dependencies

```bash
# Backend dependencies
pip install -r requirements.txt

# Frontend dependencies
cd meet
npm install
cd ..
```

### Step 2: Configure Environment Variables

Create `.env.local` in the `ob_agent/` directory:

```env
# LiveKit Configuration
LIVEKIT_URL=wss://your-livekit-url.livekit.cloud
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret

# OpenAI Configuration
OPENAI_API_KEY=sk-your-openai-key-here

# Optional: Langfuse (for monitoring)
LANGFUSE_PUBLIC_KEY=your_langfuse_public_key
LANGFUSE_SECRET_KEY=your_langfuse_secret_key
```

### Step 3: Start the Services

**Terminal 1 - FastAPI Backend (Port 8000)**
```bash
python generate_token.py
```

**Terminal 2 - Next.js Frontend (Port 3000)**
```bash
cd meet
npm run dev
```

**Terminal 3 - Streamlit UI (Port 8501) [Optional]**
```bash
streamlit run streamlit_app.py
```

**Terminal 4 - AI Agent Worker**
```bash
python agent.py
```

---

## 📊 How the System Works

### 1. **Interview Scheduling** (Streamlit UI)
- Candidate submits name, email, resume
- Backend (`generate_token.py`) processes request:
  - ✅ Saves resume to `resumes/` folder
  - ✅ Extracts resume text using pdfplumber/python-docx
  - ✅ Generates interview plan & questions using OpenAI GPT
  - ✅ Creates LiveKit room
  - ✅ Returns room name and token

### 2. **Interview Conduction**
- Candidate joins via Next.js UI at `localhost:3000/rooms/{roomName}`
- **Frontend** (`PageClientImpl.tsx`):
  - Connects to LiveKit room using server token
  - Starts head tracking (`EyeTestInner`) - detects:
    - Face not detected
    - Face partially covered
    - Not looking at screen
    - Head not straight
  - Starts browser monitoring (`BrowserProctor`) - detects:
    - Copy/Paste attempts
    - Tab switching
    - Window switching
    - Fullscreen exit
  - **Tracks violations with timestamps** in state
  - All violations logged to console

- **Backend** (`agent.py`):
  - LiveKit agent joins room
  - Waits for participant
  - Conducts real-time conversation using OpenAI Realtime Model
  - Asks prepared interview questions
  - Follows system instructions (professional interviewer)

### 3. **Violation Tracking**
- **Frontend collects** violations as they occur:
  ```json
  {
    "count": 1,
    "time": "00:03",
    "warning": "face not detected"
  }
  ```
- **De-duplicated** - same violation only logged once per 2 seconds
- **Stored in React state** with timestamps relative to interview start

### 4. **Interview End & Logging**
- When candidate leaves room (room disconnects):
  - Frontend compiles final log:
    ```json
    {
      "interviewId": "interview-abc123xyz",
      "startTime": "2026-02-04T10:30:00Z",
      "endTime": "2026-02-04T10:40:00Z",
      "duration": "10:00",
      "violations": [
        { "count": 1, "time": "00:03", "warning": "face not detected" },
        { "count": 2, "time": "00:05", "warning": "copy/paste" },
        { "count": 3, "time": "00:08", "warning": "tab switched" }
      ]
    }
    ```
  - Sends to backend via `/api/save-interview-log`
  - Backend saves as JSON to `interview-logs/{interviewId}_violations.json`

---

## 📝 Data Flow Diagram

```
┌─────────────┐
│  Candidate  │
└──────┬──────┘
       │
       ▼
┌──────────────────────────────────────┐
│   Streamlit Scheduling UI            │
│   (streamlit_app.py)                 │
│   - Resume upload                    │
│   - Schedule interview               │
└──────────┬─────────────────────────┬─┘
           │                         │
           ▼                         ▼
   ┌──────────────────┐    ┌────────────────┐
   │  Resume File     │    │  FastAPI Calls │
   │  (resumes/)      │    │  /api/get-token│
   └──────────────────┘    └────────┬───────┘
                                    │
                    ┌───────────────▼────────────────┐
                    │   generate_token.py            │
                    │   - Extract resume (utils.py) │
                    │   - Generate plan (OpenAI)     │
                    │   - Create LiveKit room        │
                    │   - Return credentials         │
                    └───────────────┬────────────────┘
                                    │
                    ┌───────────────▼────────────────┐
                    │  Next.js Frontend              │
                    │  /rooms/{roomName}             │
                    │  - LiveKit video               │
                    │  - Head tracking (EyeTest)     │
                    │  - Browser monitoring (Proctor)│
                    │  - Collect violations          │
                    └───────────────┬────────────────┘
                                    │
                    ┌───────────────┼────────────────┐
                    │               │                │
                    ▼               ▼                ▼
            ┌─────────────┐  ┌──────────────┐  ┌──────────────┐
            │ LiveKit API │  │ OpenAI API   │  │ Browser      │
            │ Video/Audio │  │ Conversation │  │ Monitoring   │
            └─────────────┘  └──────────────┘  └──────────────┘
                    │               │                │
                    └───────────────┼────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │   Violation Log (React state) │
                    │   + Interview metadata        │
                    └───────────────┬───────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │  /api/save-interview-log      │
                    │  (Next.js API Route)          │
                    └───────────────┬───────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │  generate_token.py            │
                    │  /api/save-interview-log      │
                    │  Save to file                 │
                    └───────────────┬───────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │  interview-logs/              │
                    │  {interviewId}_violations.json│
                    └───────────────────────────────┘
```

---

## 📂 What Gets Saved Where

| Item | Location | Format | When |
|------|----------|--------|------|
| **Resume** | `resumes/{candidateName}_{filename}` | PDF/DOCX | Uploaded during scheduling |
| **Interview Plan** | In-memory (INTERVIEW_CACHE) | JSON | Generated from resume |
| **Violation Log** | `interview-logs/{interviewId}_violations.json` | JSON | Interview ends |
| **Interview Metadata** | In-memory (INTERVIEW_CACHE) | JSON | Interview scheduled |
| **Feedback** | In-memory (INTERVIEW_FEEDBACK) | JSON | Posted after interview |

---

## 🎬 Main Components

### Backend (`generate_token.py`)
- **Endpoints:**
  - `POST /api/get-token` - Schedule interview, create room, generate token
  - `POST /api/interview-feedback` - Record interview feedback
  - `GET /api/interview-status/{room_name}` - Check interview status
  - `GET /api/interviews` - List all interviews
  - `POST /api/save-interview-log` - Save violation log
  - `DELETE /api/interview/{room_name}` - Delete interview record

### Agent (`agent.py`)
- Connects to LiveKit room
- Waits for participant
- Conducts real-time conversation
- Uses OpenAI Realtime Model for natural dialogue
- Follows interview instructions

### Frontend (`meet/app/rooms/[roomName]/PageClientImpl.tsx`)
- **Violation Tracking State:**
  - `violations` - Array of { count, time, warning }
  - `interviewStartTime` - Ref to interview start timestamp
  - `addViolation()` - Callback to record violations
  
- **Child Components:**
  - `EyeTestClient` → `EyeTestInner` - Head tracking with TensorFlow
  - `BrowserProctor` - Tab/window/copy-paste/fullscreen monitoring

### Proctoring Components
- **EyeTestInner.tsx** - Uses TensorFlow.js + MediaPipe
  - Detects face landmarks
  - Calculates head rotation (yaw) and tilt (pitch)
  - Calls `onViolation()` when thresholds exceeded
  
- **BrowserProctor.tsx** - Browser API monitoring
  - `visibilitychange` - Tab switching
  - `blur` - Window switching
  - `copy/cut/paste` - Clipboard attempts
  - `fullscreenchange` - Fullscreen exit

---

## 🔐 Environment Variables

```env
# REQUIRED - LiveKit
LIVEKIT_URL=wss://your-domain.livekit.cloud
LIVEKIT_API_KEY=APIxxxx
LIVEKIT_API_SECRET=secrets...

# REQUIRED - OpenAI
OPENAI_API_KEY=sk-proj-xxxxx

# OPTIONAL - Monitoring
LANGFUSE_PUBLIC_KEY=pk_xxxx
LANGFUSE_SECRET_KEY=sk_xxxx

# OPTIONAL - Backend URL (for Next.js to call backend)
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

---

## 🛠️ Development Tips

### Testing Interview Violations
1. Start all services (backend, frontend, agent)
2. Go to Streamlit UI: `localhost:8501`
3. Upload resume and schedule interview
4. Join interview in Next.js: `localhost:3000`
5. To trigger violations:
   - **Head tracking:** Move head side-to-side or tilt up/down
   - **Tab switch:** Press Alt+Tab
   - **Copy/Paste:** Try Ctrl+C/V (will be blocked)
   - **Window:** Click outside browser
6. Leave interview
7. Check `interview-logs/` folder for JSON file

### Checking Logs
```bash
# Backend logs (terminal where generate_token.py runs)
# Shows: Room creation, token generation, violations saved

# Frontend console (browser DevTools)
# Shows: Violation tracking console logs
# Format: [Violation N] MM:SS - violation_name
```

### Debugging
- **No head-tracking warnings?**
  - Check browser console for errors
  - Ensure camera permissions granted
  - Verify TensorFlow model loading

- **Violations not saving?**
  - Check if backend `/api/save-interview-log` is called
  - Verify `interview-logs/` directory exists
  - Check backend console for errors

- **Agent not speaking?**
  - Check `agent.py` is running
  - Verify OpenAI API key is valid
  - Check LiveKit logs for agent connection

---

## 📦 Docker Deployment (Optional)

Future enhancement: Add Dockerfile for containerized deployment.

---

## 🔄 API Reference

### Interview Scheduling
```bash
POST http://localhost:8000/api/get-token
Content-Type: multipart/form-data

participant: "John Doe"
email: "john@example.com"
scheduled_time: "2026-02-05T10:00:00Z"
resume: <file>
```

**Response:**
```json
{
  "interviewId": "interview-abc123",
  "serverUrl": "wss://livekit.cloud",
  "participantToken": "token...",
  "plan": { "summary": "...", "questions": [...] }
}
```

### Save Interview Log
```bash
POST http://localhost:8000/api/save-interview-log
Content-Type: application/json

{
  "interviewId": "interview-abc123",
  "startTime": "2026-02-04T10:30:00Z",
  "endTime": "2026-02-04T10:40:00Z",
  "duration": "10:00",
  "violations": [
    { "count": 1, "time": "00:03", "warning": "face not detected" }
  ]
}
```

---

## 🤝 Contributing

Future contributors should:
1. Follow existing code structure
2. Update this README if adding new features
3. Ensure all environment variables are documented
4. Test both frontend and backend

---

## 📞 Support

For issues or questions:
1. Check the Troubleshooting section above
2. Review console logs (browser + terminal)
3. Verify environment variables are set correctly
4. Check LiveKit dashboard for room/participant info
