
import json
from datetime import datetime
from pathlib import Path
import logging
import os

import psycopg2
from psycopg2 import pool, extras

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CONNECTION POOL
# ---------------------------------------------------------------------------
_connection_pool = None


def _get_database_url():
    return os.environ["DATABASE_URL"]

def get_pool():
    global _connection_pool
    if _connection_pool is None or _connection_pool.closed:
        _connection_pool = pool.SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=_get_database_url(),
        )
        logger.info("Database connection pool created")
    return _connection_pool


def get_connection():
    return get_pool().getconn()


def put_connection(conn):
    get_pool().putconn(conn)


# ---------------------------------------------------------------------------
# SCHEMA INITIALIZATION
# ---------------------------------------------------------------------------
def init_database():
    """Initialize PostgreSQL database with required tables."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Interviews table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interviews (
                id SERIAL PRIMARY KEY,
                room_name TEXT UNIQUE NOT NULL,
                participant_name TEXT NOT NULL,
                email TEXT NOT NULL,
                link_created_at TEXT NOT NULL,
                link_expiry TEXT NOT NULL,
                scheduled_time TEXT,
                created_at TEXT NOT NULL,
                status TEXT DEFAULT 'SCHEDULED',
                resume_path TEXT,
                resume_text TEXT,
                questions_json TEXT,
                transcript_path TEXT,
                recording_path TEXT,
                evaluation_path TEXT,
                evaluation_text TEXT,
                observation_path TEXT,
                completed_at TEXT
            )
        """)

        # Interview events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interview_events (
                id SERIAL PRIMARY KEY,
                room_name TEXT NOT NULL,
                event_type TEXT NOT NULL,
                message TEXT,
                timestamp TEXT NOT NULL,
                CONSTRAINT fk_events_room
                    FOREIGN KEY (room_name) REFERENCES interviews(room_name)
            )
        """)

        # Transcripts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transcripts (
                id SERIAL PRIMARY KEY,
                room_name TEXT NOT NULL,
                speaker TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                CONSTRAINT fk_transcripts_room
                    FOREIGN KEY (room_name) REFERENCES interviews(room_name)
            )
        """)

        # Job descriptions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_descriptions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        # HR responses table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hr_responses (
                id SERIAL PRIMARY KEY,
                room_name TEXT NOT NULL,
                question_index INTEGER NOT NULL,
                answer TEXT NOT NULL,
                timestamp TEXT DEFAULT '',
                CONSTRAINT fk_hr_room
                    FOREIGN KEY (room_name) REFERENCES interviews(room_name)
            )
        """)

        conn.commit()
        logger.info("Database initialized")
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to initialize database: {e}")
        raise
    finally:
        cursor.close()
        put_connection(conn)


# ---------------------------------------------------------------------------
# JD TABLE (kept for backward compat — now handled by init_database)
# ---------------------------------------------------------------------------
def init_jd_table():
    """No-op: job_descriptions table is created in init_database()."""
    pass


# ---------------------------------------------------------------------------
# INTERVIEWS
# ---------------------------------------------------------------------------
def create_interview(
    room_name: str,
    participant_name: str,
    email: str,
    link_created_at: str,
    link_expiry: str,
    resume_path: str = None,
    questions: list = None,
):
    conn = get_connection()
    cursor = conn.cursor()

    if questions is None:
        questions = []

    scheduled_time = link_created_at

    try:
        cursor.execute(
            """
            INSERT INTO interviews (
                room_name, participant_name, email,
                link_created_at, link_expiry, scheduled_time,
                created_at, resume_path, questions_json
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                room_name,
                participant_name,
                email,
                link_created_at,
                link_expiry,
                scheduled_time,
                datetime.utcnow().isoformat(),
                resume_path,
                json.dumps(questions),
            ),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to create interview: {e}")
        raise
    finally:
        cursor.close()
        put_connection(conn)


def update_interview_status(room_name, status, completed_at=None):
    """Update interview status."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        if completed_at:
            cursor.execute(
                """
                UPDATE interviews
                SET status = %s, completed_at = %s
                WHERE room_name = %s
                """,
                (status, completed_at, room_name),
            )
        else:
            cursor.execute(
                """
                UPDATE interviews
                SET status = %s
                WHERE room_name = %s
                """,
                (status, room_name),
            )

        conn.commit()
        logger.info(f"Interview status updated: {room_name} -> {status}")
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to update status: {e}")
        return False
    finally:
        cursor.close()
        put_connection(conn)


def add_interview_event(room_name, event_type, message):
    """Add interview event/feedback."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO interview_events
            (room_name, event_type, message, timestamp)
            VALUES (%s, %s, %s, %s)
            """,
            (room_name, event_type, message, datetime.utcnow().isoformat()),
        )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to add event: {e}")
        return False
    finally:
        cursor.close()
        put_connection(conn)


def add_transcript_entry(room_name, speaker, message):
    """Add transcript entry."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO transcripts
            (room_name, speaker, message, timestamp)
            VALUES (%s, %s, %s, %s)
            """,
            (room_name, speaker, message, datetime.utcnow().isoformat()),
        )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to add transcript: {e}")
        return False
    finally:
        cursor.close()
        put_connection(conn)


def get_interview(room_name):
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

    try:
        cursor.execute(
            "SELECT * FROM interviews WHERE room_name = %s",
            (room_name,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        cursor.close()
        put_connection(conn)


def get_interview_link_info(room_name):
    """Get link_expiry and status for a room (used by validate_link)."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT link_expiry, status FROM interviews WHERE room_name = %s",
            (room_name,),
        )
        return cursor.fetchone()
    finally:
        cursor.close()
        put_connection(conn)


def get_all_interviews():
    """Get all interviews."""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

    try:
        cursor.execute("""
            SELECT i.room_name, i.participant_name, i.email,
                   i.scheduled_time, i.status, i.created_at,
                   i.completed_at, i.jd_id,
                   j.title AS jd_title
            FROM interviews i
            LEFT JOIN job_descriptions j ON j.id = i.jd_id
            ORDER BY i.created_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        put_connection(conn)


def get_transcripts(room_name):
    """Get all transcripts for a room."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT speaker, message, timestamp
            FROM transcripts
            WHERE room_name = %s
            ORDER BY timestamp ASC
            """,
            (room_name,),
        )
        rows = cursor.fetchall()
        return [{"speaker": r[0], "message": r[1], "timestamp": r[2]} for r in rows]
    finally:
        cursor.close()
        put_connection(conn)


def save_transcript_file(room_name):
    """Save transcript path to database."""
    transcripts = get_transcripts(room_name)

    if not transcripts:
        return None

    Path("transcripts").mkdir(exist_ok=True)
    file_path = f"transcripts/{room_name}_transcript.txt"

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            UPDATE interviews
            SET transcript_path = %s
            WHERE room_name = %s
            """,
            (file_path, room_name),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to save transcript path: {e}")
    finally:
        cursor.close()
        put_connection(conn)

    logger.info(f"Transcript saved: {file_path}")
    return file_path


def update_recording_path(room_name, recording_path):
    """Update recording path in database."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            UPDATE interviews
            SET recording_path = %s
            WHERE room_name = %s
            """,
            (recording_path, room_name),
        )
        conn.commit()
        logger.info(f"Recording path updated: {room_name}")
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to update recording path: {e}")
        return False
    finally:
        cursor.close()
        put_connection(conn)


def update_evaluation(room_name, evaluation_path, evaluation_text):
    """Update evaluation in database."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            UPDATE interviews
            SET evaluation_path = %s, evaluation_text = %s
            WHERE room_name = %s
            """,
            (evaluation_path, evaluation_text, room_name),
        )
        conn.commit()
        logger.info(f"Evaluation saved for: {room_name}")
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to save evaluation: {e}")
        return False
    finally:
        cursor.close()
        put_connection(conn)


def add_observation(room_name, observation_type, details, timestamp):
    """Add observation entry (legacy — stored in interviews table)."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            UPDATE interviews
            SET observation_path = %s
            WHERE room_name = %s
            """,
            (json.dumps({"type": observation_type, "details": details, "timestamp": timestamp}), room_name),
        )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to add observation: {e}")
        return False
    finally:
        cursor.close()
        put_connection(conn)


def save_hr_response(room_name, question_index, answer):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO hr_responses (room_name, question_index, answer)
            VALUES (%s, %s, %s)
            """,
            (room_name, question_index, answer),
        )
        conn.commit()
        logger.info(f"HR response saved: {room_name} index {question_index}")
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to save HR response: {e}")
        return False
    finally:
        cursor.close()
        put_connection(conn)


def get_hr_responses(room_name: str) -> list:
    """Get HR responses from hr_responses table."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT question_index, answer, timestamp
            FROM hr_responses
            WHERE room_name = %s
            ORDER BY question_index ASC
            """,
            (room_name,),
        )
        rows = cursor.fetchall()
        return [{"question_index": r[0], "answer": r[1], "timestamp": r[2]} for r in rows]
    finally:
        cursor.close()
        put_connection(conn)


def get_hr_responses_from_transcript(room_name: str, static_questions: list) -> list:
    """
    Extract HR Q&A directly from transcript table.
    More reliable than hr_responses table.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT speaker, message, timestamp
            FROM transcripts
            WHERE room_name = %s
            ORDER BY timestamp ASC
            """,
            (room_name,),
        )
        rows = cursor.fetchall()
    finally:
        cursor.close()
        put_connection(conn)

    if not rows:
        return []

    entries = [{"speaker": r[0], "message": r[1], "timestamp": r[2]} for r in rows]

    hr_qa = []

    for i, entry in enumerate(entries):
        if entry["speaker"] != "Agent":
            continue

        agent_msg = entry["message"].lower()

        for q_index, question in enumerate(static_questions):
            key_words = [w.lower() for w in question.split() if len(w) > 3]
            matched = sum(1 for kw in key_words if kw in agent_msg)

            if matched >= 2:
                for j in range(i + 1, min(i + 5, len(entries))):
                    if entries[j]["speaker"] == "User":
                        answer = entries[j]["message"].strip()
                        if len(answer.split()) < 2:
                            continue
                        hr_qa.append({
                            "question_index": q_index,
                            "question": question,
                            "answer": answer,
                            "timestamp": entries[j]["timestamp"],
                        })
                        break
                break

    return hr_qa


# ---------------------------------------------------------------------------
# JOB DESCRIPTIONS
# ---------------------------------------------------------------------------
def create_jd(jd_id: str, title: str, description: str, created_at: str):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO job_descriptions (id, title, description, created_at)
            VALUES (%s, %s, %s, %s)
            """,
            (jd_id, title, description, created_at),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to create JD: {e}")
        raise
    finally:
        cursor.close()
        put_connection(conn)


def get_all_jds():
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT id, title, description, created_at
            FROM job_descriptions
            ORDER BY created_at DESC
        """)
        rows = cursor.fetchall()
        return [
            {"jd_id": r[0], "title": r[1], "description": r[2], "created_at": r[3]}
            for r in rows
        ]
    finally:
        cursor.close()
        put_connection(conn)


def get_jd(jd_id: str):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT id, title, description, created_at FROM job_descriptions WHERE id = %s",
            (jd_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {"jd_id": row[0], "title": row[1], "description": row[2], "created_at": row[3]}
    finally:
        cursor.close()
        put_connection(conn)
 
