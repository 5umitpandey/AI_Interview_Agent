#testing automatic room disconnect after interview completion and saving transcript to database without file creation
from livekit.agents import (Agent)
from livekit.plugins.openai.realtime import RealtimeModel
from livekit.plugins import openai, silero
import logging

logger = logging.getLogger("interview-agent")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

STATIC_QUESTIONS = [
    "How many years of relevant experience do you have for this role?",
    "Have you resigned from your current job?",
    "What is your current CTC and expected CTC?",
]

INSTRUCTIONS = """
You are an AI interviewer for LEADER GROUP company.

CRITICAL RULES - FOLLOW EXACTLY:

QUESTION SEQUENCE:
Step 1. After candidate introduction, ask: "How many years of relevant experience do you have for this role?"
Step 2. Ask: "Have you resigned from your current job?"
         → If candidate says YES (resigned): ask "What is your notice period and when is your last working day?" then continue to Step 3.
         → If candidate says NO (not resigned / still employed): ask "Why are you looking to leave your current role?" then continue to Step 3.
         → If candidate is a fresher or says not applicable: skip and continue to Step 3.
Step 3. Ask: "What is your current CTC and expected CTC?"
Step 4. Ask all RESUME/JD BASED QUESTIONS in order.
Step 5. WRAP UP: Tell the candidate that all questions are completed, thank them for their time, and inform them that they will be notified with feedback soon. End with exactly this phrase: "INTERVIEW_COMPLETED"

GENERAL RULES:
- Ask ONE question at a time. Wait for a complete answer before moving on.
- After receiving an answer, acknowledge briefly (one short sentence max) then ask the next question.
- Do NOT skip any question unless the conditional logic above says to skip.
- Do NOT provide feedback or suggestions during the interview.
- If candidate says "I don't know" or cannot answer, say "No problem, let's move on." and go to the next question.
- If candidate asks you questions, politely redirect: "Let's keep the focus on your experience for now."
- Do NOT go off-topic. Stay strictly within the question list.

IMPORTANT: The notice period question is ONLY asked if the candidate has already resigned. Never ask it otherwise.
IMPORTANT: When all questions are done, always end your final message with the exact word: INTERVIEW_COMPLETED
"""

class InterviewAgent(Agent):
    def __init__(self, questions: list, candidate_name: str, room_name: str, transcript_writer, on_interview_complete=None):
        self.questions = questions
        self.candidate_name = candidate_name
        self.room_name = room_name
        self.transcript_writer = transcript_writer
        self.current_question_index = 0
        self.introduction_received = False
        self.interview_completed = False
        self.on_interview_complete = on_interview_complete  # async callback

        logger.info("=" * 80)
        logger.info("🤖 AGENT INITIALIZED")
        logger.info(f"   Candidate: {candidate_name}")
        logger.info(f"   Room: {room_name}")
        logger.info(f"   Static Questions: {len(STATIC_QUESTIONS)}")
        logger.info(f"   Resume/JD Questions: {len(questions)}")
        logger.info("=" * 80)

        resume_text = "\n".join([f"{i+1}. {q}" for i, q in enumerate(questions)])

        super().__init__(
            instructions=f"""{INSTRUCTIONS}

RESUME/JD BASED QUESTIONS (ask these in order after static questions):
{resume_text}

Total resume/JD questions: {len(questions)}
Follow the sequence strictly as described above.""",
            llm=RealtimeModel(
                model="gpt-realtime-mini",
                voice="alloy",
                temperature=0.2,
            ),
            vad=silero.VAD.load(),
            allow_interruptions=True
        )

    def get_next_question(self):
        if self.current_question_index < len(self.questions):
            question = self.questions[self.current_question_index]
            self.current_question_index += 1
            logger.info(f"📋 [RESUME/JD] Question {self.current_question_index}/{len(self.questions)}")
            return question
        return None


