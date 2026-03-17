from contextlib import asynccontextmanager
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from database import *
import database
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from livekit.api import LiveKitAPI, ListRoomsRequest, AccessToken, VideoGrants, CreateRoomRequest
from livekit.api import DeleteRoomRequest
import logging
from pydantic import BaseModel
import uvicorn
import os
import shutil
from utils import prepare_interview_plan, extract_resume_text
import json
from pathlib import Path

# Load environment variables from .env.local in the current directory
load_dotenv(".env.local")

logger = logging.getLogger("interview-agent")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

# Get LiveKit API key and secret from environment variables
url = os.getenv("LIVEKIT_URL")
api_key = os.getenv("LIVEKIT_API_KEY")
api_secret = os.getenv("LIVEKIT_API_SECRET")

jd="""
        AI Developer
 
        Job Title: AI Developer (Python)

        Years of Experience: 3+ Years (in relevant field)

        Location: Remote
        Position Overview Develop robust Python-based AI applications and end-to-end Machine Learning pipelines. Focus on training, fine-tuning, and deploying open-source models (Hugging Face) and Deep Learning solutions, while leveraging Generative AI and Agents to enhance system capabilities.
        Key Responsibilities
        Python Application Development: Write clean, efficient, and scalable Python code for backend logic and data processing pipelines.
        ML & DL Model Lifecycle: Design, train, and validate Machine Learning and Deep Learning models (Regression, Classification, NLP, Computer Vision) using standard frameworks.
        Open Source Deployment: Select, fine-tune, and deploy open-source models from Hugging Face into production environments.
        Gen AI & Agents: Implement Generative AI features (LLM integration) and Agentic workflows where they add specific value to the product.
        API & Serving: Build high-performance APIs (FastAPI/Flask) to expose ML/DL models and AI agents to front-end systems.
        Optimization: Optimize model inference for latency and resource usage; ensure code quality through testing and CI/CD practices.
        Required Qualifications
        Expertise in Python programming (Data Structures, Algorithms, OOP).
        Strong foundation in Machine Learning (Scikit-learn) and Deep Learning (PyTorch/TensorFlow).
        Hands-on experience deploying Hugging Face Transformers and managing open-source model pipelines.
        Experience building and consuming RESTful APIs (FastAPI/Flask/Django).
        Practical knowledge of Generative AI (RAG, basic Agentic patterns) and LLM APIs.
        Familiarity with containerization (Docker) and cloud deployment (AWS/GCP).
        Preferred Qualifications
        Bachelor’s or Master’s in Computer Science, AI, or related field.
        Experience with model quantization and optimization techniques ( TensorRT).
        Minimum 3 year relevant experience
        
        Skills Required
        Python, Machine Learning, Deep Learning, Hugging Face Transformers, scikit-learn, API Development, FastAPI, Generative AI, RAG, Docker, Git, SQL, Model Deployment, MLOps
    """

# Validate that required environment variables are set
if not url or not api_key or not api_secret:
    raise ValueError("LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET must be set in .env.local")

# ---------------------------------------------------------------------------
# Lifespan — initialise DB on startup
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting up — initialising database …")
    database.init_database()
    logger.info("✅ Database ready")
    yield
    logger.info("🛑 Shutting down")

app = FastAPI(title="AI Led interview", version="1.0.0", root_path="/ai-led-interview")


origins = [
    "http://localhost:3030",
    "http://localhost:3000",
    "https://unicam.discretal.com/ai-led-interview",
]
# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    # allow_origins=["*"],  # For development, in production specify domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for interview data and feedback
INTERVIEW_CACHE = {}
INTERVIEW_FEEDBACK = {}
VIOLATIONS_LOG = {}


# -------------------------------------------------
# MODELS
# -------------------------------------------------
class InterviewFeedback(BaseModel):
    room_name: str
    status: str  # NO_SHOW, STARTED, COMPLETED, PARTICIPANT_LEFT
    message: str
    timestamp: str


class ProctorViolation(BaseModel):
    type: str  # head_movement, face_not_detected, face_covered, tab_switched, window_switched, fullscreen_exited, copy_paste
    message: str
    timestamp: str


class ViolationsLog(BaseModel):
    room_name: str
    violations: list[ProctorViolation]


@app.on_event("startup")
def startup_event():
    init_database()

@app.post("/api/job-descriptions")
async def create_jd(
    title: str = Form(...),
    description: str = Form(...)
):
    jd_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    database.create_jd(jd_id, title, description, created_at)

    return {
        "jd_id": jd_id,
        "title": title,
        "created_at": created_at
    }

@app.get("/api/job-descriptions")
async def list_jds():
    jds = database.get_all_jds()
    return {
        "total": len(jds),
        "job_descriptions": jds
    }


@app.post("/api/get-token")
async def prepare_interview(
    participant: str = Form(...),
    email: str = Form(...),
    resume: UploadFile = File(...),
    jd_id: str = Form(...)
):
    """
    Prepare an interview session by:
    1. Extracting resume text
    2. Generating interview questions using AI
    3. Creating a LiveKit room
    4. Generating access token with 24-hour expiry
    """
    now = datetime.now(timezone.utc)

    # Link created at current time
    link_created_at = now
    # Link expires 24 hours from creation
    link_expiry = now + timedelta(hours=24)
    # link_expiry = scheduled_dt + timedelta(hours=24)
    # Save resume file
    os.makedirs("resumes", exist_ok=True)
    file_path = f"resumes/{participant}_{resume.filename}"

    try:
        with open(file_path, "wb") as f:
            shutil.copyfileobj(resume.file, f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save resume: {str(e)}")

    # Extract resume text
    try:
        resume_text = extract_resume_text(file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract resume text: {str(e)}")
    
    jd_data = database.get_jd(jd_id)
    if not jd_data:
        raise HTTPException(status_code=404, detail="JD not found")
    jd = jd_data["description"]
    
    # Generate interview plan using AI
    try:
        plan = await prepare_interview_plan(resume_text, jd)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate interview plan: {str(e)}")
    
    # Add metadata to plan
    plan["candidate_name"] = participant
    plan["email"] = email
    plan["link_expiry"] = link_expiry.isoformat()
    plan["link_created_at"] = link_created_at.isoformat()
    plan["resume_file"] = file_path
    plan["resume_text"] = resume_text  # Add resume text to plan
    
    # Create LiveKit room
    room_name = f"interview-{uuid4().hex}"
    
    # # Save costing info
    # cost_path = Path("evaluations") / f"{room_name}_interview_plan_cost.json"
    # with open(cost_path, "w", encoding="utf-8") as cf:
    #     json.dump(plan.get("costing", {}), cf, indent=2)
    # Ensure evaluations folder exists
    os.makedirs("evaluations", exist_ok=True)

    cost_path = Path("evaluations") / f"{room_name}_interview_plan_cost.json"

    with open(cost_path, "w", encoding="utf-8") as cf:
        json.dump(plan.get("costing", {}), cf, indent=2)
    try:
        async with LiveKitAPI(
            url=url,
            api_key=api_key,
            api_secret=api_secret,
        ) as client:
            room = await client.room.create_room(
                CreateRoomRequest(
                    name=room_name,
                    empty_timeout=1800,  # 30 minutes (increased from 20)
                    departure_timeout=60,
                    max_participants=3,
                    metadata=json.dumps(plan)
                ),
            )
            room_name = room.name
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create LiveKit room: {str(e)}")
    
    # Store in database
    try:
        database.create_interview(
            room_name=room_name,
            participant_name=participant,
            email=email,
            resume_path=file_path,
            questions=plan.get("questions", []),
            link_created_at=link_created_at.isoformat(),
            link_expiry=link_expiry.isoformat(),
        )

        logger.info(f"📝 Interview saved in DB for room {room_name}")
    except Exception as e:
        raise HTTPException(500, f"Interview DB insert failed: {e}")
    
    # Generate participant access token with 24-hour expiry
    token = AccessToken(api_key, api_secret) \
        .with_identity(participant) \
        .with_name(participant) \
        .with_grants(VideoGrants(
            room=room_name,
            room_join=True,
            can_subscribe=True,
            can_publish=True,
            can_publish_data=True,
        )) 
        # .with_ttl(timedelta(hours=24))  # 24 hours in seconds
    
    # Generate join URL
    # join_url = f"https://meet.livekit.io/custom?liveKitUrl={url}&token={token.to_jwt()}"
    # join_url = f"http://localhost:8048/ai-led-interview/api/join-room?room_name={room_name}&participant={participant}"
    join_url = f"https://unicam.discretal.com/ai-led-interview/api/join-room?room_name={room_name}&participant={participant}"

    
    return {
        "message": "Interview link generated successfully",
        "room_name": room_name,
        "participant": participant,
        "email": email,
        "link_created_at": link_created_at.isoformat(),
        "link_expiry": link_expiry.isoformat(),
        "summary": plan.get("summary", ""),
        "question_count": len(plan.get("questions", [])),
        "questions": plan.get("questions", []),
        "join_url": join_url,
        "costing": plan.get("costing", {})
    }

# @app.get("/api/validate-link/{room_name}")
# async def validate_link(room_name: str):
#     import sqlite3
    
#     try:
#         conn = sqlite3.connect("interview_data.db")
#         cursor = conn.cursor()
#         cursor.execute(
#             "SELECT link_expiry, status FROM interviews WHERE room_name = ?",
#             (room_name,)
#         )
#         result = cursor.fetchone()
#         conn.close()
        
#         if not result:
#             raise HTTPException(status_code=404, detail="Interview not found")
        
#         link_expiry_str, status = result[0], result[1]
#         link_expiry = datetime.fromisoformat(link_expiry_str)
#         now = datetime.now(timezone.utc)

#         # ✅ Check status first
#         blocked_statuses = {"COMPLETED", "PARTICIPANT_LEFT", "NO_SHOW", "LINK_EXPIRED"}
#         if status in blocked_statuses:
#             return {
#                 "room_name": room_name,
#                 "is_valid": False,
#                 "status": status,
#                 "message": "This interview link has already been used. Please contact HR."
#             }

#         # ✅ Then check expiry
#         is_valid = now < link_expiry
        
#         return {
#             "room_name": room_name,
#             "is_valid": is_valid,
#             "status": status,
#             "link_expiry": link_expiry_str,
#             "current_time": now.isoformat(),
#             "message": "Link is active" if is_valid else "This interview link has expired. Please contact the support team."
#         }
    
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"❌ Link validation error: {e}")
#         raise HTTPException(status_code=500, detail=f"Link validation failed: {str(e)}")

# @app.get("/api/join-room")
# async def join_room(room_name: str, participant: str):

#     interview = database.get_interview(room_name)

#     if not interview:
#         raise HTTPException(status_code=404, detail="Interview not found")

#     # ✅ CHECK 1 — Block if already used (must be first)
#     blocked_statuses = {"COMPLETED", "PARTICIPANT_LEFT", "NO_SHOW", "LINK_EXPIRED"}
#     current_status = interview.get("status", "SCHEDULED")
    
#     logger.info(f"🔍 Join attempt — room: {room_name} | status: {current_status}")
    
#     if current_status in blocked_statuses:
#         raise HTTPException(
#             status_code=403,
#             detail="This interview link has already been used. Please contact HR."
#         )

#     # ✅ CHECK 2 — Block if expired
#     link_expiry = datetime.fromisoformat(interview["link_expiry"])
#     now = datetime.now(timezone.utc)

#     if now > link_expiry:
#         try:
#             async with LiveKitAPI(
#                 url=url,
#                 api_key=api_key,
#                 api_secret=api_secret,
#             ) as client:
#                 await client.room.delete_room(DeleteRoomRequest(room=room_name))
#         except Exception as e:
#             logger.error(f"Room delete failed: {e}")

#         raise HTTPException(
#             status_code=403,
#             detail="This interview link has expired. Please contact the support team."
#         )
#     # ✅ Generate short-lived token (5 mins only)
#     token = AccessToken(api_key, api_secret) \
#         .with_identity(participant) \
#         .with_name(participant) \
#         .with_grants(VideoGrants(
#             room=room_name,
#             room_join=True,
#             can_subscribe=True,
#             can_publish=True,
#             can_publish_data=True,
#         )) \
#         .with_ttl(timedelta(minutes=10))
#     # the_url = f"http://liveKitUrl={url}/?token={token.to_jwt()}"
#     return {
#         "livekit_url": url,
#         "token": token.to_jwt(),
#         # "url": the_url
#     }

# -------------------------------
# Validate interview link
# -------------------------------
@app.get("/api/validate-link/{room_name}")
async def validate_link(room_name: str):
    try:
        interview = get_interview(room_name)

        if not interview:
            raise HTTPException(status_code=404, detail="Interview not found")

        link_expiry_str = interview["link_expiry"]
        status = interview["status"]
        link_expiry = datetime.fromisoformat(link_expiry_str)
        now = datetime.now(timezone.utc)

        # ✅ Block if already used
        blocked_statuses = {"COMPLETED", "PARTICIPANT_LEFT", "NO_SHOW", "LINK_EXPIRED"}
        if status in blocked_statuses:
            return {
                "room_name": room_name,
                "is_valid": False,
                "status": status,
                "message": "This interview link has already been used. Please contact HR."
            }

        # ✅ Check expiry
        is_valid = now < link_expiry

        return {
            "room_name": room_name,
            "is_valid": is_valid,
            "status": status,
            "link_expiry": link_expiry_str,
            "current_time": now.isoformat(),
            "message": "Link is active" if is_valid else "This interview link has expired. Please contact the support team."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Link validation error: {e}")
        raise HTTPException(status_code=500, detail=f"Link validation failed: {str(e)}")


# -------------------------------
# Join interview room
# -------------------------------
@app.get("/api/join-room")
async def join_room(room_name: str, participant: str):
    interview = get_interview(room_name)

    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    # ✅ Block if already used
    blocked_statuses = {"COMPLETED", "PARTICIPANT_LEFT", "NO_SHOW", "LINK_EXPIRED"}
    current_status = interview.get("status", "SCHEDULED")

    logger.info(f"🔍 Join attempt — room: {room_name} | status: {current_status}")

    if current_status in blocked_statuses:
        raise HTTPException(
            status_code=403,
            detail="This interview link has already been used. Please contact HR."
        )

    # ✅ Block if expired
    link_expiry = datetime.fromisoformat(interview["link_expiry"])
    now = datetime.now(timezone.utc)

    if now > link_expiry:
        try:
            async with LiveKitAPI(
                url=url,
                api_key=api_key,
                api_secret=api_secret,
            ) as client:
                await client.room.delete_room(DeleteRoomRequest(room=room_name))
        except Exception as e:
            logger.error(f"Room delete failed: {e}")

        raise HTTPException(
            status_code=403,
            detail="This interview link has expired. Please contact the support team."
        )

    # ✅ Generate short-lived token (10 mins)
    token = AccessToken(api_key, api_secret) \
        .with_identity(participant) \
        .with_name(participant) \
        .with_grants(VideoGrants(
            room=room_name,
            room_join=True,
            can_subscribe=True,
            can_publish=True,
            can_publish_data=True,
        )) \
        .with_ttl(timedelta(minutes=10))

    return {
        "livekit_url": url,
        "token": token.to_jwt(),
    }


@app.post("/api/interview-feedback")
async def receive_interview_feedback(feedback: InterviewFeedback):
    """
    Receive feedback from the agent about interview status
    Possible statuses:
    - NO_SHOW: Candidate didn't join within 10 minutes
    - STARTED: Interview started successfully
    - COMPLETED: Interview completed
    - PARTICIPANT_LEFT: Candidate left before completion
    """
    
    room_name = feedback.room_name
    
    # Store feedback
    if room_name not in INTERVIEW_FEEDBACK:
        INTERVIEW_FEEDBACK[room_name] = []
    
    INTERVIEW_FEEDBACK[room_name].append({
        "status": feedback.status,
        "message": feedback.message,
        "timestamp": feedback.timestamp
    })
    
    # Get interview data from cache
    interview_data = INTERVIEW_CACHE.get(room_name)
    
    if interview_data:
        print(f"\n{'='*60}")
        print(f"INTERVIEW FEEDBACK - Room: {room_name}")
        print(f"{'='*60}")
        print(f"Candidate: {interview_data['participant']}")
        print(f"Email: {interview_data['email']}")
        print(f"Link Created: {interview_data.get('link_created_at', 'N/A')}")
        print(f"Link Expires: {interview_data.get('link_expiry', 'N/A')}")
        print(f"Status: {feedback.status}")
        print(f"Message: {feedback.message}")
        print(f"Timestamp: {feedback.timestamp}")
        print(f"{'='*60}\n")
        
        # Here you can add additional logic:
        # - Send email notifications
        # - Update database
        # - Trigger webhooks
        # - Generate reports
        
        if feedback.status == "NO_SHOW":
            # Send email notification about no-show
            print(f"⚠️ ALERT: {interview_data['participant']} did not join the interview")
            # TODO: Send email notification
            
        elif feedback.status == "COMPLETED":
            # Send completion confirmation
            print(f"✅ SUCCESS: Interview with {interview_data['participant']} completed")
            # TODO: Send thank you email, schedule next steps
            
        elif feedback.status == "PARTICIPANT_LEFT":
            # Handle early departure
            print(f"⚠️ WARNING: {interview_data['participant']} left interview early")
            # TODO: Send follow-up email
    
    return {
        "message": "Feedback received",
        "room_name": room_name,
        "status": feedback.status
    }


@app.post("/api/log-violations")
async def log_violations(violations_log: ViolationsLog):
    """
    Log proctoring violations from the interview
    Violations include:
    - head_movement: Candidate not looking at screen
    - face_not_detected: Face not visible in video
    - face_covered: Face partially covered
    - tab_switched: Candidate switched tabs
    - window_switched: Candidate switched windows
    - fullscreen_exited: Candidate exited fullscreen
    """
    
    room_name = violations_log.room_name
    
    # Store violations
    if room_name not in VIOLATIONS_LOG:
        VIOLATIONS_LOG[room_name] = []
    
    VIOLATIONS_LOG[room_name].extend([v.dict() for v in violations_log.violations])
    
    # Get interview data
    interview_data = INTERVIEW_CACHE.get(room_name)
    
    if interview_data and violations_log.violations:
        print(f"\n{'='*60}")
        print(f"PROCTORING VIOLATIONS - Room: {room_name}")
        print(f"{'='*60}")
        print(f"Candidate: {interview_data['participant']}")
        print(f"Total Violations: {len(VIOLATIONS_LOG[room_name])}")
        
        violation_types = {}
        for v in violations_log.violations:
            violation_types[v.type] = violation_types.get(v.type, 0) + 1
        
        for v_type, count in violation_types.items():
            print(f"  - {v_type}: {count}")
        
        print(f"{'='*60}\n")
    
    return {
        "message": "Violations logged",
        "room_name": room_name,
        "violation_count": len(violations_log.violations)
    }


@app.get("/api/interview-status/{room_name}")
async def get_interview_status(room_name: str):
    """
    Get the current status of an interview
    """
    
    if room_name not in INTERVIEW_CACHE:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    interview_data = INTERVIEW_CACHE[room_name]
    feedback_history = INTERVIEW_FEEDBACK.get(room_name, [])
    
    current_status = "SCHEDULED"
    if feedback_history:
        current_status = feedback_history[-1]["status"]
    
    return {
        "room_name": room_name,
        "participant": interview_data["participant"],
        "email": interview_data["email"],
        "link_created_at": interview_data.get("link_created_at"),
        "link_expiry": interview_data.get("link_expiry"),
        "current_status": current_status,
        "feedback_history": feedback_history
    }


@app.get("/api/interviews")
async def list_interviews():
    """
    List all interviews
    """
    
    interviews = []
    for room_name, data in INTERVIEW_CACHE.items():
        feedback_history = INTERVIEW_FEEDBACK.get(room_name, [])
        current_status = "SCHEDULED"
        if feedback_history:
            current_status = feedback_history[-1]["status"]
        
        interviews.append({
            "room_name": room_name,
            "participant": data["participant"],
            "email": data["email"],
            "link_created_at": data.get("link_created_at"),
            "link_expiry": data.get("link_expiry"),
            "current_status": current_status,
            "created_at": data.get("created_at")
        })
    
    return {
        "total": len(interviews),
        "interviews": interviews
    }


@app.delete("/api/interview/{room_name}")
async def delete_interview(room_name: str):
    """
    Delete an interview from cache
    """
    
    if room_name in INTERVIEW_CACHE:
        del INTERVIEW_CACHE[room_name]
    
    if room_name in INTERVIEW_FEEDBACK:
        del INTERVIEW_FEEDBACK[room_name]
    
    return {"message": f"Interview {room_name} deleted"}

@app.get("/api/interviews/{room_name}/report")
async def get_report(room_name: str):
    interview = database.get_interview(room_name)

    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    evaluation_text = interview.get("evaluation_text")

    if not evaluation_text:
        raise HTTPException(status_code=404, detail="Evaluation not ready yet")

    try:
        return {
            "room_name": room_name,
            "participant": interview.get("participant_name"),
            "status": interview.get("status"),
            "report": json.loads(evaluation_text)
        }
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Evaluation data corrupted")

@app.get("/api/interviews/{room_name}/transcript")
async def get_transcript(room_name: str):
    interview = database.get_interview(room_name)

    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    transcripts = database.get_transcripts(room_name)

    if not transcripts:
        raise HTTPException(status_code=404, detail="Transcript not available yet")

    return {
        "room_name": room_name,
        "participant": interview.get("participant_name"),
        "total_entries": len(transcripts),
        "transcript": transcripts
    }

@app.get("/api/interviews/{room_name}/hr-responses")
async def get_hr_responses(room_name: str):
    interview = database.get_interview(room_name)

    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    responses = database.get_hr_responses(room_name)

    from interview_agent import STATIC_INITIAL_QUESTIONS

    enriched = []
    for r in responses:
        q_index = r["question_index"]
        question_text = (
            STATIC_INITIAL_QUESTIONS[q_index]
            if q_index < len(STATIC_INITIAL_QUESTIONS)
            else "Follow-up question"
        )
        enriched.append({
            "question_index": q_index,
            "question": question_text,
            "answer": r["answer"],
            "timestamp": r["timestamp"]
        })

    return {
        "room_name": room_name,
        "participant": interview.get("participant_name"),
        "total": len(enriched),
        "hr_responses": enriched
    }

@app.post("/api/save-interview-log")
async def save_interview_log(interview_log: dict):
    """
    Save interview violations log to a JSON file
    """
    try:
        # Create interview-logs directory if it doesn't exist
        os.makedirs("interview-logs", exist_ok=True)
        
        interview_id = interview_log.get("interviewId", "unknown")
        
        # Create filename with interview ID
        log_file = f"interview-logs/{interview_id}_violations.json"
        
        # Save the log as JSON
        with open(log_file, "w") as f:
            json.dump(interview_log, f, indent=2)
        
        print(f"[Interview Log Saved] {log_file}")
        print(f"  Duration: {interview_log.get('duration')}")
        print(f"  Violations: {len(interview_log.get('violations', []))}")
        
        return {
            "message": "Interview log saved successfully",
            "file": log_file,
            "violations_count": len(interview_log.get("violations", []))
        }
    except Exception as e:
        print(f"[Error] Failed to save interview log: {str(e)}")
        return {
            "error": f"Failed to save interview log: {str(e)}"
        }, 500


@app.get("/")
async def root():
    """
    API health check
    """
    return {
        "service": "AI Interview API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "schedule_interview": "/api/get-token",
            "interview_feedback": "/api/interview-feedback",
            "interview_status": "/api/interview-status/{room_name}",
            "list_interviews": "/api/interviews",
            "save_interview_log": "/api/save-interview-log"
        }
    }


# -------------------------------------------------
# MAIN
# -------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(
        "generate_token:app",
        host="0.0.0.0",
        port=8048,
        log_level="info"
    )
