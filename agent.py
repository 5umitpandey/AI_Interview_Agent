#working code with agents, recording, and backend notification. Next steps: add error handling, polish conversation flow, and implement reviewer agent logic.
import asyncio
from datetime import datetime, timezone
import database
from dotenv import load_dotenv
from interview_agent import InterviewAgent
import json
import logging
from livekit import rtc, api
from livekit.agents import ConversationItemAddedEvent
from livekit.api import LiveKitAPI
from livekit.agents.llm import ChatContext
from livekit.agents import (
    AgentSession,
    JobContext,
    RoomInputOptions,
    RoomOutputOptions,
    WorkerOptions,
    cli,
)
from livekit.api import (
    RoomCompositeEgressRequest,
    EncodingOptionsPreset,
    EncodedFileOutput,
    LiveKitAPI,
    StopEgressRequest,
    DeleteRoomRequest
)
from livekit.plugins import silero
from livekit import rtc
from langfuse import observe
import numpy as np
import os
from observer_agent import *
from pathlib import Path
from PIL import Image
import requests
from reviewer_agent import *
from transcript import SimpleTranscriptWriter
# -------------------------------------------------
# ENV + LOGGING
# -------------------------------------------------
load_dotenv(".env.local")

logger = logging.getLogger("interview-agent")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
#project
# -------------------------------------------------
# CONFIGURATION
# -------------------------------------------------
API_BASE_URL = "http://localhost:8000"
PARTICIPANT_WAIT_TIME = 600  # 10 minutes

# LiveKit credentials
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")

# Create directories
Path("recordings").mkdir(exist_ok=True)
Path("transcripts").mkdir(exist_ok=True)
Path("evaluations").mkdir(exist_ok=True)
# Path("transcripts").mkdir(exist_ok=True)

logger.info("=" * 80)
logger.info("📁 DIRECTORIES CREATED:")
logger.info(f"   - recordings/  exists: {Path('recordings').exists()}")
logger.info(f"   - transcripts/ exists: {Path('transcripts').exists()}")
logger.info("=" * 80)

# -------------------------------------------------
# BACKEND NOTIFICATION
# -------------------------------------------------
async def notify_backend(room_name: str, status: str, message: str):
    """Send feedback to backend about interview status"""
    try:
        payload = {
            "room_name": room_name,
            "status": status,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        response = requests.post(
            f"{API_BASE_URL}/api/interview-feedback",
            json=payload,
            timeout=5
        )
        
        if response.status_code == 200:
            logger.info(f"✅ Backend notified: {status}")
        else:
            logger.warning(f"⚠️ Backend notification failed: {response.status_code}")
            
    except Exception as e:
        logger.error(f"❌ Backend notification error: {e}")


# async def start_room_recording(room_name: str):
#     logger.info("🎥 Starting room recording")

#     try:
#         async with LiveKitAPI(
#             url=LIVEKIT_URL.replace("ws://", "http://"),
#             api_key=LIVEKIT_API_KEY,
#             api_secret=LIVEKIT_API_SECRET,
#         ) as lkapi:

#             req = RoomCompositeEgressRequest(
#                 room_name=room_name,
#                 layout="speaker",
#                 audio_only=False,
#                 video_only=False,
#                 preset=EncodingOptionsPreset.H264_1080P_30,
#                 file_outputs=[
#                     EncodedFileOutput(
#                         filepath=f"/recordings/{room_name}.mp4"
#                     )
#                 ],
#             )

#             res = await lkapi.egress.start_room_composite_egress(req)
#             logger.info(f"✅ Recording started: {res.egress_id}")
#             return res.egress_id

#     except Exception as e:
#         logger.error(f"❌ Failed to start recording: {e}")
#         return None


# -------------------------------------------------
# PARTICIPANT MONITORING
# -------------------------------------------------
async def wait_for_participant(ctx: JobContext, timeout_seconds: int = PARTICIPANT_WAIT_TIME):
    """Wait for participant to join within timeout period"""
    start_time = datetime.now()
    
    logger.info(f"👀 Waiting for participant (timeout: {timeout_seconds}s)")
    
    while True:
        participants = [p for p in ctx.room.remote_participants.values()]
        
        if participants:
            logger.info(f"✅ Participant joined: {participants[0].identity}")
            return True
        
        elapsed = (datetime.now() - start_time).total_seconds()
        if elapsed >= timeout_seconds:
            logger.warning(f"⏰ Timeout: No participant after {timeout_seconds}s")
            return False
        
        await asyncio.sleep(2)

async def publish_avatar_video(ctx, avatar_path: str):
    logger.info("🧑‍💼 Publishing AI avatar video track")

    # Load image
    img = Image.open(avatar_path).convert("RGB")
    width, height = img.size
    frame = np.array(img)

    source = rtc.VideoSource(width, height)
    track = rtc.LocalVideoTrack.create_video_track(
        "ai-avatar",
        source
    )

    await ctx.room.local_participant.publish_track(
        track,
        rtc.TrackPublishOptions(
            source=rtc.TrackSource.SOURCE_CAMERA
        )
    )

    # Push same frame repeatedly (acts like static video)
    async def push_frames():
        while True:
            video_frame = rtc.VideoFrame(
                width=width,
                height=height,
                data=frame.tobytes(),
                type=rtc.VideoBufferType.RGB24,
            )
            source.capture_frame(video_frame)
            await asyncio.sleep(1 / 10)  # 10 FPS is enough

    asyncio.create_task(push_frames())

    logger.info("✅ AI avatar video published")

# from livekit.api import StopEgressRequest
# from livekit.api.twirp_client import TwirpError

# async def safe_stop_egress(egress_id: str):
#     try:
#         async with LiveKitAPI(
#             url=LIVEKIT_URL.replace("ws://", "http://"),
#             api_key=LIVEKIT_API_KEY,
#             api_secret=LIVEKIT_API_SECRET,
#         ) as lkapi:
#             await lkapi.egress.stop_egress(
#                 StopEgressRequest(egress_id=egress_id)
#             )
#         logger.info("🛑 Recording stopped cleanly")

#     except TwirpError as e:
#         # This is NORMAL when egress already failed or completed
#         if "EGRESS_FAILED" in str(e) or "failed_precondition" in str(e):
#             logger.warning(
#                 f"⚠️ Egress already stopped/failed, ignoring: {egress_id}"
#             )
#         else:
#             raise


# Interview state management
class InterviewState:
    def __init__(self):
        self.conversation_count = 0
        self.interview_active = True
        self.popup_queue = []

@observe
async def entrypoint(ctx: JobContext):
    egress_id = None
    observer_room = None

    logger.info("🚀 AGENT STARTING")

    await ctx.connect()
    logger.info("✅ Connected to room")

    await ctx.room.local_participant.set_name("LEADER GROUP – AI Interviewer")

    database.init_database()

    # Parse room metadata
    if not ctx.room.metadata:
        logger.warning("⚠️ Room metadata is empty — interview not started")
        await notify_backend(
            ctx.room.name,
            "ENDED",
            "Room metadata missing"
        )
        return

    try:
        plan = json.loads(ctx.room.metadata)
        logger.info(f"PLAN:- {plan}")
    except json.JSONDecodeError:
        raise RuntimeError("❌ Invalid metadata JSON")

    candidate_name = plan.get("candidate_name", "Candidate")
    questions = plan.get("questions", [])
    logger.info(f"questions: {questions}")
    room_name = ctx.room.name

    link_created_at = datetime.fromisoformat(plan["link_created_at"])
    link_expiry = datetime.fromisoformat(plan["link_expiry"])
    now = datetime.now(timezone.utc)

    # Check if link has expired (more than 24 hours from creation)
    if now > link_expiry:
        logger.warning("❌ Interview link expired")
        await notify_backend(
            room_name,
            "LINK_EXPIRED",
            f"Link expired at {link_expiry.isoformat()}"
        )
        # 🔥 Delete the room from LiveKit
        try:
            async with LiveKitAPI(
                url=LIVEKIT_URL.replace("ws://", "http://"),
                api_key=LIVEKIT_API_KEY,
                api_secret=LIVEKIT_API_SECRET,
            ) as lkapi:
                await lkapi.room.delete_room(
                    DeleteRoomRequest(room=room_name)
                )
            logger.info("🗑️ Room deleted due to expired link")
        except Exception as e:
            logger.error(f"Room delete failed: {e}")

        return

    logger.info(f"✅ Interview link valid. Created at {link_created_at.isoformat()}, expires at {link_expiry.isoformat()}")


    logger.info(f"📋 Candidate: {candidate_name}")
    logger.info(f"📋 Room: {room_name}")
    logger.info(f"📋 Questions: {len(questions)}")

    transcript = SimpleTranscriptWriter(room_name)

    BASE_DIR = Path(__file__).resolve().parent
    await publish_avatar_video(
        ctx,
        avatar_path=BASE_DIR / "asserts" / "AI.png"
    )

    # await publish_avatar_video(ctx, avatar_path=BASE_DIR / "asserts" / "Aiinterviewer.webp")

    logger.info("🕓 Waiting for participant to join the room...")
    participant_joined = await wait_for_participant(
        ctx, PARTICIPANT_WAIT_TIME
    )

    if not participant_joined:
        logger.warning("❌ No participant joined within wait time. Exiting agent.")
        await notify_backend(room_name, "NO_SHOW", "Candidate did not join within timeout")
        transcript.close()
        return

    logger.info("✅ Participant joined. Proceeding with interview setup.")
    
    # Lock candidate identity
    participants = list(ctx.room.remote_participants.values())
    candidate_identity = participants[0].identity
    logger.info(f"🎯 Candidate identity locked: {candidate_identity}")

    try:
        await publish_observer_avatar(
            observer_room,
            avatar_path=BASE_DIR / "asserts" / "humanai.png"
        )
    except Exception as e:
        logger.warning(f"⚠️ Observer avatar skipped: {e}")
    observer_room = await join_observer(room_name)
    # await publish_observer_avatar(observer_room)   # ← add this line
    logger.info("✅ Observer joined successfully")

    logger.info("🎬 Starting interview now")
    await notify_backend(room_name, "STARTED", "Interview started")

    # ─────────────────────────────────────────────
    # Interview state + exit signal
    # ─────────────────────────────────────────────
    state = InterviewState()
    interview_done = asyncio.Event()

    # ─────────────────────────────────────────────
    # Participant disconnect handler (CORE FIX)
    # ─────────────────────────────────────────────
    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(participant: rtc.RemoteParticipant):
        logger.info(f"👋 Disconnected: {participant.identity}")

        if participant.identity == candidate_identity:
            logger.info("🚨 Candidate left — ending interview")
            database.update_interview_status(room_name, "PARTICIPANT_LEFT", datetime.now(timezone.utc).isoformat())
            state.interview_active = False
            interview_done.set()
            

    # ─────────────────────────────────────────────
    # Start recording
    # ─────────────────────────────────────────────
    # egress_id = await start_room_recording(room_name)
    # if egress_id:
    #     logger.info(f"🎬 Recording started (egress_id={egress_id})")

    agent = InterviewAgent(
        questions,
        candidate_name,
        room_name,
        transcript
    )

    session = AgentSession()

    try:
        # ─────────────────────────────────────────────
        # Start interviewer agent
        # ─────────────────────────────────────────────
        await session.start(
            agent=agent,
            room=ctx.room,
            room_input_options=RoomInputOptions(
                audio_enabled=True,
                delete_room_on_close=False,
                close_on_disconnect=False,
                audio_sample_rate=16000,
                # audio_channels=1,
                # # increase buffering
                # audio_buffer_ms=100  # try 80–120ms 
            ),
            room_output_options=RoomOutputOptions(
                audio_enabled=True,
                transcription_enabled=True,
                audio_publish_options=rtc.TrackPublishOptions(
                    source=rtc.TrackSource.SOURCE_MICROPHONE
                ),
            ),
        )

        logger.info("✅ Interviewer agent joined")

        # ─────────────────────────────────────────────
        # Conversation tracking
        # ─────────────────────────────────────────────
        # # Events for coordinating conversation flow
        # introduction_event = asyncio.Event()
        # hr_event = asyncio.Event()
        # # mutable holder for last HR answer text
        # hr_last_answer = {"text": None}

        async def disconnect_all_and_close():
            logger.info("🔚 Interview complete — disconnecting all participants")
            database.update_interview_status(
                room_name,
                "COMPLETED",
                datetime.now(timezone.utc).isoformat()
            )
            try:
                async with LiveKitAPI(
                    url=LIVEKIT_URL.replace("ws://", "http://"),
                    api_key=LIVEKIT_API_KEY,
                    api_secret=LIVEKIT_API_SECRET,
                ) as lkapi:
                    for participant in list(ctx.room.remote_participants.values()):
                        try:
                            await lkapi.room.delete_room(DeleteRoomRequest(
                            room=room_name,
                            ))
                            logger.info(f"✅ Removed participant: {participant.identity}")
                        except Exception as e:
                            logger.warning(f"⚠️ Could not remove {participant.identity}: {e}")
            except Exception as e:
                logger.error(f"❌ Error during room disconnect: {e}")
            finally:
                # database.update_interview_status(room_name, "COMPLETED", datetime.now(timezone.utc).isoformat())
                state.interview_active = False
                interview_done.set()

        # ─────────────────────────────────────────────
        # Conversation tracking + completion detection
        # ─────────────────────────────────────────────
        @session.on("conversation_item_added")
        def on_conversation_item_added(event):
            role = event.item.role
            interrupted = event.item.interrupted

            for content in event.item.content:
                if isinstance(content, str) and content.strip():
                    speaker = "Agent" if role == "assistant" else "User"
                    clean_content = content.strip()

                    # Detect interview completion signal
                    if role == "assistant" and "INTERVIEW_COMPLETED" in clean_content:
                        logger.info("🏁 INTERVIEW_COMPLETED signal detected")
                        # Remove the signal word from transcript
                        clean_content = clean_content.replace("INTERVIEW_COMPLETED", "").strip()
                        if not state.interview_active:
                            return
                        # Give agent 3 seconds to finish speaking then disconnect
                        import asyncio
                        asyncio.get_event_loop().call_later(
                            1, lambda: asyncio.ensure_future(disconnect_all_and_close())
                        )

                    if not interrupted and clean_content:
                        transcript.write(speaker, clean_content)

        # ─────────────────────────────────────────────
        # Greeting
        # ─────────────────────────────────────────────
        greeting = (
            "Hi, I am the AI interviewer from LEADER GROUP company. "
            "I have reviewed your resume. "
            "Before we begin, please introduce yourself and tell me "
            "about your relevant projects and experience."
        )

        transcript.write("Agent", greeting)

        await session.generate_reply(
            instructions=f"Say this greeting EXACTLY: '{greeting}'",
            allow_interruptions=True,
           
        )

        # ─────────────────────────────────────────────
        # HR ROUND START — ask each HR question and wait for reply
        # ─────────────────────────────────────────────
        logger.info("🧑‍💼 Starting HR round")

    
        logger.info("✅ Monitoring interview session")
        await interview_done.wait()


        ####################################################################################################

    finally:
        # ─────────────────────────────────────────────
        # CLEANUP (always runs)
        # ─────────────────────────────────────────────
        logger.info("🧹 Cleanup started")

        transcript.close()

        # if egress_id:
        #     # async with LiveKitAPI(
        #     #     url=LIVEKIT_URL.replace("ws://", "http://"),
        #     #     api_key=LIVEKIT_API_KEY,
        #     #     api_secret=LIVEKIT_API_SECRET,
        #     # ) as lkapi:
        #     #     await lkapi.egress.stop_egress(
        #     #         StopEgressRequest(egress_id=egress_id)
        #     #     )
        #     # logger.info("🛑 Recording stopped")
        #     await safe_stop_egress(egress_id)

        try:
            await session.aclose()
            logger.info("✅ Interview agent session closed")
        except Exception as e:
            logger.error(f"Session close error: {e}")

        if observer_room:
            try:
                await observer_room.disconnect()
                logger.info("👁️ Observer disconnected")
            except Exception as e:
                logger.error(f"Observer disconnect error: {e}")
  
        await notify_backend(
            room_name,
            "PARTICIPANT_LEFT",
            "Candidate disconnected"
        )

        logger.info("🧠 Running reviewer agent")
        await run_reviewer_agent(room_name, plan)

        logger.info("🏁 Interview ended")

# -------------------------------------------------
# MAIN
# -------------------------------------------------
if __name__ == "__main__":
    logger.info("🚀 AI INTERVIEW AGENT")
    
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
        )
    )
###########################################################################################################
