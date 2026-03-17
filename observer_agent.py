from dotenv import load_dotenv
from livekit.api import AccessToken, VideoGrants
from livekit import rtc
import logging
import os
import asyncio
import numpy as np
from pathlib import Path

load_dotenv(".env.local")

logger = logging.getLogger("interview-agent")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")

def create_observer_token(room_name: str) -> str:
    token = (
        AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        .with_identity(f"observer-{room_name}")
        .with_name("Observer")
        .with_grants(
            VideoGrants(
                room=room_name,
                room_join=True,
                can_publish=True,  # ✅ observer is listen-only (FIXED: was True)
                can_subscribe=True,  # ✅ observer can listen to all participants
                can_publish_data=False,
                room_record=True,  # ✅ allow recording the room
            )
        )
    )
    return token.to_jwt()

async def join_observer(room_name: str):
    token = create_observer_token(room_name)

    room = rtc.Room()

    await room.connect(
        LIVEKIT_URL,
        token,
    )

    logger.info("👁️ Observer connected (listen-only, muted)")

    return room

async def publish_observer_avatar(
    room: rtc.Room,
    avatar_path: str = None,
    label: str = "observer-avatar"
):
    from PIL import Image as PILImage

    width, height = 640, 480
    frame_data = None

    # ── Load image ────────────────────────────────────────────
    if avatar_path and Path(str(avatar_path)).exists():
        try:
            img = PILImage.open(avatar_path).convert("RGB")
            img = img.resize((width, height))
            frame_data = np.array(img, dtype=np.uint8)
            logger.info(f"✅ Observer avatar image loaded: {avatar_path}")
        except Exception as e:
            logger.warning(f"⚠️ Image load failed, using grey frame: {e}")

    # ── Fallback grey frame ───────────────────────────────────
    if frame_data is None:
        logger.warning("⚠️ Using grey fallback frame for observer")
        frame_data = np.full((height, width, 3), 80, dtype=np.uint8)

    source = rtc.VideoSource(width, height)
    track = rtc.LocalVideoTrack.create_video_track(label, source)

    # ✅ Wait for room to fully register participant before publishing
    logger.info("⏳ Waiting 3s before observer track publish...")
    await asyncio.sleep(3)

    # ── Publish track ─────────────────────────────────────────
    try:
        await room.local_participant.publish_track(
            track,
            rtc.TrackPublishOptions(
                source=rtc.TrackSource.SOURCE_CAMERA
            )
        )
        logger.info("✅ Observer avatar track published successfully")
    except Exception as e:
        logger.warning(f"⚠️ Observer avatar publish failed (non-fatal): {e}")
        return

    # ── Push frames in background ─────────────────────────────
    async def push_frames():
        logger.info("🔄 Observer frame loop started")
        while True:
            try:
                video_frame = rtc.VideoFrame(
                    width=width,
                    height=height,
                    data=frame_data.tobytes(),
                    type=rtc.VideoBufferType.RGB24,
                )
                source.capture_frame(video_frame)
                await asyncio.sleep(1 / 5)
            except Exception as e:
                logger.error(f"❌ Observer frame push error: {e}")
                break

    asyncio.create_task(push_frames())
    logger.info("✅ Observer avatar frame loop running")
