from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv
from pathlib import Path
import json
from datetime import datetime
import logging
import database
import re
import asyncio

logger = logging.getLogger("interview-agent")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

# =====================================================================
# EVALUATION RUBRIC
# =====================================================================
EVALUATION_RUBRIC = {
    "Technical Knowledge": {
        "5": "Deep, accurate knowledge; explains reasoning and internals clearly",
        "4": "Solid understanding; minor gaps; good explanation",
        "3": "Basic understanding; some gaps; adequate explanation",
        "2": "Limited understanding; significant gaps; vague explanation",
        "1": "Poor understanding; major errors",
        "0": "No answer or completely off-topic"
    },
    "Communication": {
        "5": "Articulate, structured, confident; excellent listening",
        "4": "Clear and organized; good engagement",
        "3": "Adequate clarity; some rambling; acceptable engagement",
        "2": "Unclear; poorly structured; weak engagement",
        "1": "Very difficult to follow; poor engagement",
        "0": "No communication"
    },
    "HR Round": {
        "5": "All HR answers clear, honest, complete with exact figures",
        "4": "Most HR answers clear with minor missing details",
        "3": "HR answers given but vague on CTC or notice period",
        "2": "Incomplete HR answers; avoided key questions",
        "1": "Very poor HR responses; evasive or unclear",
        "0": "No HR answers given"
    },
    "Technical Depth": {
        "5": "Goes beyond surface; explains internals, trade-offs, edge cases",
        "4": "Good depth; explains how and why not just what",
        "3": "Moderate depth; answers what but not always how or why",
        "2": "Shallow answers; only surface level knowledge",
        "1": "Very shallow; buzzwords only with no real understanding",
        "0": "No depth demonstrated"
    }
}

# =====================================================================
# EARLY STOP THRESHOLDS
# =====================================================================
EARLY_STOP_RUBRIC = {
    "idk_threshold": 3,
    "avg_words_threshold": 20,
    "completion_threshold": 0.3,
}


# =====================================================================
# REVIEWER AGENT
# =====================================================================
class ReviewerAgent:
    def __init__(self):
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set in environment")

        self.llm = ChatOpenAI(
            api_key=api_key,
            model="gpt-4.1-nano",
            temperature=0.2,
        )

    # ------------------------------------------------------------------
    # EARLY STOP — local only, no LLM call
    # ------------------------------------------------------------------
    def detect_early_stop_signals(
        self,
        transcript_text: str,
        question_count: int,
        hr_responses: list
    ) -> dict:
        signals = {
            "should_stop": False,
            "reason": None,
            "confidence": 0.0,
            "indicators": []
        }

        transcript_lower = transcript_text.lower()

        # Signal 1 — too many I don't know
        idk_count = (
            transcript_lower.count("i don't know") +
            transcript_lower.count("not sure") +
            transcript_lower.count("i am not sure")
        )
        if idk_count > EARLY_STOP_RUBRIC["idk_threshold"]:
            signals["indicators"].append(
                f"Frequent uncertainty responses ({idk_count} times)"
            )
            signals["confidence"] += 0.30

        # Signal 2 — very short answers
        user_lines = [l for l in transcript_text.split("\n") if l.startswith("User:")]
        avg_words = sum(len(l.split()) for l in user_lines) / max(len(user_lines), 1)
        if avg_words < EARLY_STOP_RUBRIC["avg_words_threshold"]:
            signals["indicators"].append(
                f"Very short answers (avg {round(avg_words, 1)} words)"
            )
            signals["confidence"] += 0.25

        # Signal 3 — answered less than 30%
        answered = len(hr_responses) + len(user_lines)
        if question_count > 0 and answered < question_count * EARLY_STOP_RUBRIC["completion_threshold"]:
            signals["indicators"].append("Completed less than 30% of planned questions")
            signals["confidence"] += 0.30

        # Signal 4 — skipped or avoided
        off_topic = ["that's personal", "i don't want to answer", "skip", "next question"]
        if any(kw in transcript_lower for kw in off_topic):
            signals["indicators"].append("Candidate skipped or avoided questions")
            signals["confidence"] += 0.15

        signals["should_stop"] = signals["confidence"] >= 0.5
        if signals["should_stop"]:
            signals["reason"] = "; ".join(signals["indicators"])

        return signals

    # ------------------------------------------------------------------
    # BEHAVIORAL SUMMARY — from detection logs file
    # ------------------------------------------------------------------
    def build_behavioral_summary(self, detection_logs: dict) -> dict:
        """
        Read violations from detection logs and produce
        human readable summary.
        Handles both 'warning' key (frontend format) and 'type' key.
        """
        if not detection_logs:
            return {
                "summary": "No behavioral data available",
                "total_violations": 0,
                "breakdown": {}
            }

        violations = detection_logs.get("violations", [])

        if not violations:
            return {
                "summary": "No violations recorded during interview",
                "total_violations": 0,
                "breakdown": {}
            }

        # ✅ FIX: support both 'warning' (frontend) and 'type' (old format)
        type_counts = {}
        for v in violations:
            typ = v.get("warning") or v.get("type") or "unknown"
            typ = typ.strip().lower()
            type_counts[typ] = type_counts.get(typ, 0) + 1

        # Build human readable summary — each warning type separately
        summary_parts = []
        for typ, count in sorted(type_counts.items()):
            readable = typ.strip()
            if count == 1:
                summary_parts.append(f"'{readable}' detected 1 time")
            else:
                summary_parts.append(f"'{readable}' detected {count} times")

        # Overall severity
        total = len(violations)
        if total == 0:
            severity = "No issues"
        elif total <= 5:
            severity = "Minor behavioral concerns"
        elif total <= 15:
            severity = "Moderate behavioral concerns"
        else:
            severity = "Significant behavioral concerns"

        final_summary = ". ".join(summary_parts) + f". Overall: {severity}."

        return {
            "summary": final_summary,
            "total_violations": total,
            "breakdown": type_counts
        }

    # ------------------------------------------------------------------
    # SINGLE LLM CALL — everything in one prompt
    # ------------------------------------------------------------------
    def evaluate(
        self,
        transcript_text: str,
        questions: list,
        candidate_name: str,
        hr_responses: list,
        static_questions: list,
        resume_text: str = None,
        job_description: str = None,
        detection_logs: dict = None,
    ) -> dict:

        total_costing = {
            "model": self.llm.model_name,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "estimated_cost_usd": 0.0
        }

        try:
            # ── Local early stop (no LLM) ─────────────────────────
            early_stop = self.detect_early_stop_signals(
                transcript_text, len(questions), hr_responses
            )

            # ── Behavioral summary from detection logs ─────────────
            behavioral_summary = self.build_behavioral_summary(detection_logs or {})
            logger.info(f"🔍 Behavioral summary built: {behavioral_summary.get('total_violations', 0)} violations")

            # ── Build rubric text ─────────────────────────────────
            rubric_text = "EVALUATION RUBRIC (score 0-5 per criterion):\n"
            for criterion, levels in EVALUATION_RUBRIC.items():
                rubric_text += f"\n{criterion}:\n"
                for level in ["5", "4", "3", "2", "1", "0"]:
                    rubric_text += f"  {level}: {levels[level]}\n"

            # ── Build HR Q&A block ────────────────────────────────
            hr_qa_block = ""
            for r in hr_responses:
                q_index = r.get("question_index", 0)
                question = (
                    static_questions[q_index]
                    if q_index < len(static_questions)
                    else "Follow-up"
                )
                hr_qa_block += (
                    f"Q{q_index + 1}: {question}\n"
                    f"A: {r.get('answer', '')}\n"
                    f"Timestamp: {r.get('timestamp', '')}\n\n"
                )

            # ── Build questions list ──────────────────────────────
            questions_text = "\n".join(
                [f"{i+1}. {q}" for i, q in enumerate(questions)]
            )

            # ── Behavioral block for prompt ───────────────────────
            detection_block = (
                f"BEHAVIORAL SUMMARY:\n"
                f"{behavioral_summary.get('summary', 'No data')}\n\n"
            )

            # ── SINGLE PROMPT ─────────────────────────────────────
            prompt = (
                "You are a senior AI interview evaluator for LEADER GROUP company.\n"
                "Evaluate the complete interview below in ONE response.\n"
                "Be STRICT, OBJECTIVE, and EVIDENCE-BASED.\n"
                "Extract everything DYNAMICALLY from the resume and transcript.\n"
                "Do NOT assume or hallucinate anything not in the data.\n"
                "Return ONLY valid JSON, no markdown, no explanation.\n\n"

                + rubric_text + "\n"

                + "=" * 60 + "\n"
                + f"CANDIDATE NAME: {candidate_name}\n\n"

                + "JOB DESCRIPTION:\n"
                + f"{job_description or 'Not provided'}\n\n"

                + "RESUME:\n"
                + f"{resume_text or 'Not provided'}\n\n"

                + "HR QUESTIONS & ANSWERS:\n"
                + f"{hr_qa_block or 'No HR responses recorded'}\n\n"

                + "TECHNICAL QUESTIONS ASKED:\n"
                + f"{questions_text or 'No technical questions'}\n\n"

                + "FULL INTERVIEW TRANSCRIPT:\n"
                + f"{transcript_text or 'No transcript available'}\n\n"

                + detection_block

                # + "=" * 60 + "\n"
                # + "INSTRUCTIONS:\n"
                # + "1. Resume match: compare resume vs JD requirements dynamically.\n"
                # + "2. HR Evaluation: extract exact values from HR Q&A block above.\n"
                # + "3. Consistency: extract ALL claims from resume, check if candidate discussed them in transcript. Do NOT use hardcoded tech list.\n"
                # + "4. Question evaluations: for EACH technical question find exact candidate answer from transcript.\n"
                # + "5. Rubric scores: based on full transcript evidence only.\n"
                # + "6. Strengths/Weaknesses: based on actual answers vs JD requirements.\n"
                # + "7. Verdict: Hire if overall >= 3.0, Borderline if 2.0-3.0, Reject if < 2.0.\n\n"
                + "=" * 60 + "\n"
                + "INSTRUCTIONS:\n"
                + "1. Resume match: compare resume vs JD requirements dynamically.\n"
                + "2. HR Evaluation: extract exact values from HR Q&A block above.\n"
                + "3. Consistency: extract ALL claims from resume, check if candidate discussed them in transcript. Do NOT assume or use hardcoded tech list.\n"
                + "4. Question evaluations: for EACH technical question find exact candidate answer from transcript.\n"
                + "   - If no answer is given, score = 0 and evidence = null.\n"
                + "5. Rubric scores: based on full transcript evidence only.\n"
                + "   - Technical Knowledge / Depth = 0 if no answer.\n"
                + "   - Communication = 0 if candidate did not speak.\n"
                + "   - HR Round = 0 if no HR answers.\n"
                + "6. Strengths/Weaknesses: based on actual answers vs JD requirements.\n"
                + "7. Verdict: Hire if overall >= 3.0, Borderline if 2.0-3.0, Reject if < 2.0.\n"
                + "8. Under no circumstances give partial credit if candidate did not respond.\n\n"

                + "RETURN THIS EXACT JSON STRUCTURE:\n"
                + "{\n"
                + '  "resume_match_pct": <0-100 integer>,\n'
                + '  "overall_score": <0-5 float, average of rubric scores>,\n'
                + '  "should_early_stop": ' + str(early_stop["should_stop"]).lower() + ',\n'
                + '  "early_stop_reason": ' + json.dumps(early_stop["reason"]) + ',\n'
                + '  "hr_evaluation": {\n'
                + '    "experience_years": "extracted from HR answers or transcript",\n'
                + '    "resigned": true or false,\n'
                + '    "notice_period": "extracted or Not mentioned",\n'
                + '    "last_working_day": "extracted or Not mentioned",\n'
                + '    "current_ctc": "extracted or Not mentioned",\n'
                + '    "expected_ctc": "extracted or Not mentioned",\n'
                + '    "hr_score": <0-5>,\n'
                + '    "hr_notes": "brief HR round summary"\n'
                + '  },\n'
                + '  "hr_questions": [\n'
                + '    {\n'
                + '      "question_index": <index>,\n'
                + '      "question": "exact HR question",\n'
                + '      "answer": "candidate exact answer",\n'
                + '      "timestamp": "from HR Q&A data"\n'
                + '    }\n'
                + '  ],\n'
                + '  "rubric_scores": {\n'
                + '    "technical_knowledge": <0-5>,\n'
                + '    "communication": <0-5>,\n'
                + '    "hr_round": <0-5 same as hr_score>,\n'
                + '    "technical_depth": <0-5>\n'
                + '  },\n'
                + '  "question_evaluations": [\n'
                + '    {\n'
                + '      "question": "exact technical question",\n'
                + '      "score": <0-5>,\n'
                + '      "evidence": "candidate exact answer from transcript",\n'
                + '      "notes": "why this score based on rubric",\n'
                + '      "follow_up": "one advanced follow-up question"\n'
                + '    }\n'
                + '  ],\n'
                + '  "strengths": ["based on actual transcript answers vs JD"],\n'
                + '  "weaknesses": ["based on actual transcript answers vs JD"],\n'
                + '  "consistency_issues": [\n'
                + '    {\n'
                + '      "category": "technology | experience | project | certification | skill",\n'
                + '      "claim": "exact claim from resume",\n'
                + '      "status": "not_discussed | partially_discussed",\n'
                + '      "candidate_response": "what candidate said or null",\n'
                + '      "issue": "clear explanation of the gap"\n'
                + '    }\n'
                + '  ],\n'
                # + '  "confirmed_claims": [\n'
                # + '    {\n'
                # + '      "claim": "resume claim candidate confirmed",\n'
                # + '      "candidate_response": "what candidate said"\n'
                # + '    }\n'
                # + '  ],\n'
                + '  "feature_points": ["key observation from interview"],\n'
                + '  "post_interview_summary": "2-3 sentence overall performance summary",\n'
                + '  "final_verdict": "Hire or Borderline or Reject",\n'
                + '  "hiring_recommendation": "detailed reasoning for verdict"\n'
                + "}\n"
            )

            # ── SINGLE LLM CALL ───────────────────────────────────
            logger.info("🤖 Running single LLM evaluation call")
            response = self.llm.invoke(prompt)
            usage = response.response_metadata.get("token_usage", {})

            total_costing["prompt_tokens"] = usage.get("prompt_tokens", 0)
            total_costing["completion_tokens"] = usage.get("completion_tokens", 0)
            total_costing["total_tokens"] = usage.get("total_tokens", 0)
            total_costing["estimated_cost_usd"] = round(
                (total_costing["prompt_tokens"] * 0.00000015) +
                (total_costing["completion_tokens"] * 0.0000006), 6
            )

            # ── Parse response ────────────────────────────────────
            text = response.content.strip()
            if text.startswith("```json"):
                text = text.replace("```json", "").replace("```", "").strip()
            elif text.startswith("```"):
                text = text.replace("```", "").strip()

            result = json.loads(text)


            # ── Notice period flag for HR ─────────────────────────
            try:
                notice_period = result.get("hr_evaluation", {}).get("notice_period", "")
                if notice_period and notice_period.lower() not in ("not mentioned", "n/a", ""):
                    # Extract number from string like "45 days", "2 months", "60 days"
                    numbers = re.findall(r'\d+', str(notice_period))
                    if numbers:
                        days = int(numbers[0])
                        # Convert months to days
                        if "month" in notice_period.lower():
                            days = days * 1

                        if days > 30:
                            result["notice_period_alert"] = {
                                "flag": True,
                                "days": days,
                                "original": notice_period,
                                "message": f"Candidate notice period is {notice_period} which is above 30 days. HR should plan accordingly."
                            }
                        else:
                            result["notice_period_alert"] = {
                                "flag": False,
                                "days": days,
                                "original": notice_period,
                                "message": f"Candidate notice period is {notice_period} which is within 30 days."
                            }
                    else:
                        result["notice_period_alert"] = {
                            "flag": None,
                            "days": None,
                            "original": notice_period,
                            "message": "Notice period mentioned but could not extract exact days."
                        }
                else:
                    result["notice_period_alert"] = {
                        "flag": None,
                        "days": None,
                        "original": "Not mentioned",
                        "message": "Candidate did not mention notice period."
                    }
            except Exception as e:
                logger.warning(f"Notice period check failed: {e}")
                result["notice_period_alert"] = {
                    "flag": None,
                    "days": None,
                    "original": "Unknown",
                    "message": "Could not determine notice period."
                }
            # ── Recalculate overall score from rubric ─────────────
            rubric = result.get("rubric_scores", {})
            if rubric:
                result["overall_score"] = round(
                    sum(rubric.values()) / max(len(rubric), 1), 2
                )

            # ── Override behavioral with our built summary ─────────
            result["behavioral_observations"] = behavioral_summary

            # ── Ensure required fields exist ──────────────────────
            defaults = {
                "resume_match_pct": 0,
                "overall_score": 0,
                "should_early_stop": early_stop["should_stop"],
                "early_stop_reason": early_stop["reason"],
                "hr_evaluation": {},
                "hr_questions": [],
                "rubric_scores": {
                    "technical_knowledge": 0,
                    "communication": 0,
                    "hr_round": 0,
                    "technical_depth": 0
                },
                "question_evaluations": [],
                "strengths": [],
                "weaknesses": [],
                "consistency_issues": [],
                # "confirmed_claims": [],
                "feature_points": [],
                "behavioral_observations": behavioral_summary,
                "post_interview_summary": "",
                "final_verdict": "Borderline",
                "hiring_recommendation": ""
            }
            for field, default in defaults.items():
                if field not in result:
                    result[field] = default

            result["costing"] = total_costing
            logger.info(
                f"✅ Single LLM call complete — "
                f"tokens: {total_costing['total_tokens']} | "
                f"cost: ${total_costing['estimated_cost_usd']}"
            )
            return result

        except json.JSONDecodeError as je:
            logger.error(f"JSON parse error: {je}")
            return self._error_result(candidate_name, str(je), total_costing, behavioral_summary)
        except Exception as e:
            logger.error(f"Reviewer agent failed: {e}")
            return self._error_result(candidate_name, str(e), total_costing, behavioral_summary if 'behavioral_summary' in locals() else {})

    # ------------------------------------------------------------------
    # ERROR FALLBACK
    # ------------------------------------------------------------------
    def _error_result(
        self,
        candidate_name: str,
        error: str,
        costing: dict,
        behavioral_summary: dict = None
    ) -> dict:
        return {
            "candidate_name": candidate_name,
            "room_name": None,
            "interview_timestamp": None,
            "resume_match_pct": 0,
            "overall_score": 0,
            "should_early_stop": False,
            "early_stop_reason": None,
            "hr_evaluation": {},
            "hr_questions": [],
            "rubric_scores": {
                "technical_knowledge": 0,
                "communication": 0,
                "hr_round": 0,
                "technical_depth": 0
            },
            "question_evaluations": [],
            "strengths": [],
            "weaknesses": [],
            "consistency_issues": [],
            # "confirmed_claims": [],
            "feature_points": [],
            "behavioral_observations": behavioral_summary or {
                "summary": "Evaluation failed",
                "total_violations": 0,
                "breakdown": {}
            },
            "post_interview_summary": "Evaluation failed",
            "final_verdict": "Borderline",
            "hiring_recommendation": "Unable to complete evaluation",
            "costing": costing,
            "error": error
        }


# ======================================================================
# FILE HELPERS
# ======================================================================
def load_detection_logs(room_name: str) -> dict:
    search_patterns = [
        (Path("interview-logs"), f"{room_name}_violations.json"),
        (Path("interview-logs"), f"{room_name}*violations*.json"),
        (Path("interview-logs"), f"{room_name}*.json"),
        (Path("observations"), f"{room_name}*.json"),
    ]

    for search_dir, pattern in search_patterns:
        if not search_dir.exists():
            continue
        for file_path in search_dir.glob(pattern):
            try:
                content = json.loads(file_path.read_text(encoding="utf-8"))
                # ✅ Also match by interviewId inside the file
                if content.get("interviewId", "") == room_name or file_path.stem.startswith(room_name):
                    logger.info(f"✅ Detection logs loaded: {file_path}")
                    return content
            except Exception as e:
                logger.warning(f"Failed to read {file_path}: {e}")

    # ✅ Fallback: scan all files and match by interviewId field inside JSON
    for search_dir in [Path("interview-logs"), Path("observations")]:
        if not search_dir.exists():
            continue
        for file_path in search_dir.glob("*.json"):
            try:
                content = json.loads(file_path.read_text(encoding="utf-8"))
                if content.get("interviewId", "") == room_name:
                    logger.info(f"✅ Detection logs matched by interviewId: {file_path}")
                    return content
            except Exception:
                continue

    logger.warning(f"⚠️ No detection logs found for room: {room_name}")
    return {}


def save_evaluation_to_file(evaluation: dict, room_name: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    evaluations_dir = Path("evaluations")
    evaluations_dir.mkdir(exist_ok=True)

    # JSON
    json_path = evaluations_dir / f"{room_name}_evaluation.json"
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(evaluation, jf, indent=2, ensure_ascii=False)
    logger.info(f"✅ Evaluation JSON saved: {json_path}")

    # TXT Report
    txt_path = evaluations_dir / f"{room_name}_evaluation_report.txt"
    try:
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("=" * 100 + "\n")
            f.write("INTERVIEW EVALUATION REPORT\n")
            f.write("=" * 100 + "\n\n")
            f.write(f"Timestamp        : {timestamp}\n")
            f.write(f"Candidate Name   : {evaluation.get('candidate_name', 'Unknown')}\n")
            f.write(f"Room             : {room_name}\n\n")

            # VERDICT
            f.write("-" * 100 + "\n")
            f.write("HIRING VERDICT\n")
            f.write("-" * 100 + "\n")
            f.write(f"Final Verdict    : {evaluation.get('final_verdict', 'N/A').upper()}\n")
            f.write(f"Overall Score    : {evaluation.get('overall_score', 0)}/5.0\n")
            f.write(f"Resume Match %   : {evaluation.get('resume_match_pct', 0)}%\n\n")
            f.write(f"Recommendation   :\n{evaluation.get('hiring_recommendation', 'N/A')}\n\n")

            # EARLY STOP
            if evaluation.get("should_early_stop"):
                f.write("-" * 100 + "\n")
                f.write("EARLY STOP TRIGGERED\n")
                f.write("-" * 100 + "\n")
                f.write(f"Reason: {evaluation.get('early_stop_reason', 'N/A')}\n\n")

            # HR EVALUATION
            f.write("-" * 100 + "\n")
            f.write("HR EVALUATION\n")
            f.write("-" * 100 + "\n")
            hr = evaluation.get("hr_evaluation", {})
            for k, v in hr.items():
                f.write(f"{k.replace('_', ' ').title():25}: {v}\n")
            f.write("\n")

            # HR Q&A
            f.write("-" * 100 + "\n")
            f.write("HR QUESTIONS & ANSWERS\n")
            f.write("-" * 100 + "\n")
            for q in evaluation.get("hr_questions", []):
                f.write(f"Q{q.get('question_index', 0) + 1}. {q.get('question', '')}\n")
                f.write(f"    Answer   : {q.get('answer', '')}\n")
                f.write(f"    Timestamp: {q.get('timestamp', '')}\n\n")

            # RUBRIC SCORES
            f.write("-" * 100 + "\n")
            f.write("RUBRIC SCORES (0-5)\n")
            f.write("-" * 100 + "\n")
            for k, v in evaluation.get("rubric_scores", {}).items():
                f.write(f"{k.replace('_', ' ').title():30}: {v}/5\n")
            f.write("\n")

            # QUESTION EVALUATIONS
            f.write("-" * 100 + "\n")
            f.write("QUESTION-WISE EVALUATION\n")
            f.write("-" * 100 + "\n")
            for i, q in enumerate(evaluation.get("question_evaluations", []), 1):
                f.write(f"\nQ{i}. {q.get('question', 'N/A')}\n")
                f.write(f"    Score    : {q.get('score', 0)}/5\n")
                f.write(f"    Evidence : {q.get('evidence', 'N/A')}\n")
                f.write(f"    Notes    : {q.get('notes', 'N/A')}\n")
                f.write(f"    Follow-up: {q.get('follow_up', 'N/A')}\n")
            f.write("\n")

            # STRENGTHS
            f.write("-" * 100 + "\n")
            f.write("STRENGTHS\n")
            f.write("-" * 100 + "\n")
            for s in evaluation.get("strengths", []):
                f.write(f"+ {s}\n")
            f.write("\n")

            # WEAKNESSES
            f.write("-" * 100 + "\n")
            f.write("WEAKNESSES\n")
            f.write("-" * 100 + "\n")
            for w in evaluation.get("weaknesses", []):
                f.write(f"- {w}\n")
            f.write("\n")

            # CONSISTENCY ISSUES
            f.write("-" * 100 + "\n")
            f.write("CONSISTENCY ISSUES\n")
            f.write("-" * 100 + "\n")
            for c in evaluation.get("consistency_issues", []):
                f.write(f"Category : {c.get('category', '')}\n")
                f.write(f"Claim    : {c.get('claim', '')}\n")
                f.write(f"Status   : {c.get('status', '')}\n")
                f.write(f"Response : {c.get('candidate_response', 'N/A')}\n")
                f.write(f"Issue    : {c.get('issue', '')}\n\n")

            # # CONFIRMED CLAIMS
            # f.write("-" * 100 + "\n")
            # f.write("CONFIRMED CLAIMS\n")
            # f.write("-" * 100 + "\n")
            # for c in evaluation.get("confirmed_claims", []):
            #     f.write(f"✓ Claim   : {c.get('claim', '')}\n")
            #     f.write(f"  Response: {c.get('candidate_response', '')}\n\n")

            # BEHAVIORAL OBSERVATIONS
            f.write("-" * 100 + "\n")
            f.write("BEHAVIORAL OBSERVATIONS\n")
            f.write("-" * 100 + "\n")
            beh = evaluation.get("behavioral_observations", {})
            f.write(f"Summary   : {beh.get('summary', 'N/A')}\n")
            if beh.get("breakdown"):
                f.write("Breakdown :\n")
                for typ, count in beh.get("breakdown", {}).items():
                    f.write(f"  - {typ.replace('_', ' ').title()}: {count} time(s)\n")
            f.write("\n")

            # POST INTERVIEW SUMMARY
            f.write("-" * 100 + "\n")
            f.write("POST INTERVIEW SUMMARY\n")
            f.write("-" * 100 + "\n")
            f.write(f"{evaluation.get('post_interview_summary', 'N/A')}\n\n")

            # KEY TAKEAWAYS
            f.write("-" * 100 + "\n")
            f.write("KEY TAKEAWAYS\n")
            f.write("-" * 100 + "\n")
            for p in evaluation.get("feature_points", []):
                f.write(f"• {p}\n")
            f.write("\n")

            # COSTING
            f.write("-" * 100 + "\n")
            f.write("COSTING\n")
            f.write("-" * 100 + "\n")
            costing = evaluation.get("costing", {})
            f.write(f"Model          : {costing.get('model', '')}\n")
            f.write(f"Prompt Tokens  : {costing.get('prompt_tokens', 0)}\n")
            f.write(f"Completion     : {costing.get('completion_tokens', 0)}\n")
            f.write(f"Total Tokens   : {costing.get('total_tokens', 0)}\n")
            f.write(f"Estimated Cost : ${costing.get('estimated_cost_usd', 0)}\n\n")

            f.write("=" * 100 + "\n")
            f.write("END OF REPORT\n")
            f.write("=" * 100 + "\n")

        logger.info(f"✅ Report saved: {txt_path}")
    except Exception as e:
        logger.error(f"Failed to save report: {e}")

    try:
        database.update_evaluation(room_name, str(json_path), json.dumps(evaluation))
        logger.info(f"✅ Evaluation DB updated: {room_name}")
    except Exception as e:
        logger.error(f"Failed to update DB: {e}")


# ======================================================================
# ENTRY POINT
# ======================================================================
async def run_reviewer_agent(room_name: str, plan: dict):
    try:
        # Wait for transcript to finish writing
        # await asyncio.sleep(5)

        interview_data = database.get_interview(room_name)
        if not interview_data:
            logger.warning(f"No interview data for {room_name}")
            return None

        logger.info(f"🧠 Starting evaluation for {room_name}")

        from interview_agent import STATIC_QUESTIONS

        # ── Load all inputs from DB ───────────────────────────────
        transcripts = database.get_transcripts(room_name)
        transcript_text = "\n".join(
            [f"{t['speaker']}: {t['message']}" for t in transcripts]
        )

        # ── HR responses from transcript (reliable) ───────────────
        hr_responses = database.get_hr_responses_from_transcript(
            room_name, STATIC_QUESTIONS
        )
        logger.info(f"   HR responses from transcript: {len(hr_responses)}")

        # Fallback to DB table if transcript extraction failed
        if not hr_responses:
            logger.warning("⚠️ Transcript HR extraction failed, falling back to DB table")
            hr_responses = database.get_hr_responses_from_transcript(room_name, STATIC_QUESTIONS)

        resume_text = interview_data.get("resume_text", "")
        questions = plan.get("questions", [])

        # ── Load real JD from DB ──────────────────────────────────
        jd_id = plan.get("jd_id")
        jd_data = database.get_jd(jd_id) if jd_id else None
        job_description = jd_data["description"] if jd_data else plan.get("summary", "")

        # ── Load detection logs ───────────────────────────────────
        detection_logs = load_detection_logs(room_name)

        logger.info(f"   Transcript entries : {len(transcripts)}")
        logger.info(f"   HR responses       : {len(hr_responses)}")
        logger.info(f"   Technical questions: {len(questions)}")
        logger.info(f"   Detection logs     : {bool(detection_logs)}")

        # ── Single LLM call ───────────────────────────────────────
        reviewer = ReviewerAgent()
        evaluation = reviewer.evaluate(
            transcript_text=transcript_text,
            questions=questions,
            candidate_name=interview_data["participant_name"],
            hr_responses=hr_responses,
            static_questions=STATIC_QUESTIONS,
            resume_text=resume_text,
            job_description=job_description,
            detection_logs=detection_logs,
        )

        # ── Fill metadata ─────────────────────────────────────────
        evaluation["room_name"] = room_name
        evaluation["interview_timestamp"] = interview_data.get(
            "scheduled_time", datetime.now().isoformat()
        )

        # ── Feature points fallback ───────────────────────────────
        if not evaluation.get("feature_points"):
            pts = [f"Strong: {s}" for s in evaluation.get("strengths", [])]
            pts += [f"Improve: {w}" for w in evaluation.get("weaknesses", [])]
            evaluation["feature_points"] = pts or ["See detailed evaluation"]

        # ── Save ──────────────────────────────────────────────────
        save_evaluation_to_file(evaluation, room_name)
        database.update_interview_status(
            room_name, "COMPLETED", datetime.utcnow().isoformat()
        )

        logger.info(
            f"✅ Evaluation complete — "
            f"Verdict: {evaluation.get('final_verdict')} | "
            f"Score: {evaluation.get('overall_score')}/5 | "
            f"Tokens: {evaluation.get('costing', {}).get('total_tokens', 0)} | "
            f"Cost: ${evaluation.get('costing', {}).get('estimated_cost_usd', 0)}"
        )
        return evaluation

    except Exception as e:
        logger.error(f"Reviewer agent failed: {e}")
        return None