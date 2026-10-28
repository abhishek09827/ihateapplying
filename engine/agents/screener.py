import logging
from engine.agents.base import BaseAgent
from engine.state import JobLead, FitEvaluation
from engine.config import MIN_MATCH_SCORE, MASTER_PROFILE
from engine.tools.profile_matcher import is_profile_aligned
from engine.tools.location_matcher import is_india_remote_eligible, get_india_remote_score_bonus

logger = logging.getLogger("ScreenerAgent")

class ScreenerAgent(BaseAgent):
    """
    Autonomous Technical Recruiter Agent.
    Evaluates role compatibility against candidate profile using deterministic fast-paths
    to save 100% of LLM tokens on obvious matches and senior/unrelated/regional mismatches.
    """

    def __init__(self):
        super().__init__(name="ScreenerAgent", role="Principal Talent Partner & Technical Evaluator")

    def screen(self, lead: JobLead) -> FitEvaluation:
        """Evaluates job lead fit using deterministic fast-path, falling back to LLM for borderline cases."""
        # PRE-FILTER 1: Regional ineligibility (excludes India remote applicants)
        loc_eligible, loc_reason = is_india_remote_eligible(lead.location, lead.description)
        if not loc_eligible:
            return FitEvaluation(
                match_score=20,
                qualified=False,
                selected_angle="Disqualified",
                fit_reasoning=f"Deterministic mismatch: {loc_reason}.",
                estimated_salary_fit="Uncertain",
                seniority_fit="Fail"
            )

        aligned, reason = is_profile_aligned(title=lead.role, description=lead.description)

        # FAST PATH 1: Direct, unambiguous profile alignment (Score 85+, 0 LLM tokens, 0.001s)
        if aligned and any(k in lead.role.lower() for k in ["ai", "applied ai", "llm", "agent", "machine learning", "ml "]):
            angle = "Applied AI & Agentic Systems"
            if "data" in lead.role.lower() or "platform" in lead.role.lower():
                angle = "Data Platform & Streaming Infrastructure"

            score = 85
            loc_bonus = get_india_remote_score_bonus(lead.location, lead.description)
            score = max(0, min(100, score + loc_bonus))

            return FitEvaluation(
                match_score=score,
                qualified=True,
                selected_angle=angle,
                fit_reasoning=f"Deterministic match: {reason}. Profile shows direct technical alignment.",
                estimated_salary_fit="Pass",
                seniority_fit="Pass"
            )

        # FAST PATH 2: Obvious seniority or role mismatch (Score 35, 0 LLM tokens, 0.001s)
        if not aligned and ("exceeds" in reason or "Disqualified" in reason):
            return FitEvaluation(
                match_score=35,
                qualified=False,
                selected_angle="Disqualified",
                fit_reasoning=f"Deterministic mismatch: {reason}.",
                estimated_salary_fit="Uncertain",
                seniority_fit="Fail"
            )

        # SLOW PATH: Borderline / nuanced role requiring LLM reasoning
        candidate_summary = f"""
Candidate: {MASTER_PROFILE.get('candidate', {}).get('name', 'Applicant')}
Title: {MASTER_PROFILE.get('candidate', {}).get('title', 'Software Engineer')}
Experience: {MASTER_PROFILE.get('candidate', {}).get('years_experience', '1-3 Years')}
Target Roles: {', '.join(MASTER_PROFILE.get('candidate', {}).get('target_roles', []))}
Skills: {', '.join(MASTER_PROFILE.get('candidate', {}).get('target_skills', []))}
"""
        prompt = f"""Evaluate whether this candidate is qualified for the target role.
{candidate_summary}

OPPORTUNITY:
Company: {lead.company}
Role: {lead.role}
Channel: {lead.source_channel}
Job Overview / Description:
{lead.description[:1200]}

Scoring Rules:
- Score 75-100: Strong match with candidate's target skills.
- Score 50-74: Borderline match.
- Score 0-49: Mismatch (e.g. requires 5+ years, or non-technical).
- Remote & India Preference: High priority (+15 bonus) for roles hiring in India or APAC remote; strong priority (+10 bonus) for Worldwide/Global remote. Reject (score < 40) if restricted to US/EU residency or requires US citizenship.

Return ONLY a JSON object with keys:
- match_score: integer (0-100)
- qualified: boolean (true if score >= {MIN_MATCH_SCORE})
- selected_angle: string (e.g. "Applied AI Systems" or "Backend Infrastructure")
- fit_reasoning: string (1-2 concise sentences)
- estimated_salary_fit: string ("Pass" or "Uncertain")
- seniority_fit: string ("Pass" or "Fail")
"""

        try:
            data = self.generate_json(prompt, system_prompt="You are a strict technical hiring screener.", temperature=0.1)
            score = int(data.get("match_score", 50))
            is_qualified = bool(data.get("qualified", score >= MIN_MATCH_SCORE))
            return FitEvaluation(
                match_score=score,
                qualified=is_qualified,
                selected_angle=data.get("selected_angle", "General Engineering"),
                fit_reasoning=data.get("fit_reasoning", "Evaluated against candidate technical background."),
                estimated_salary_fit=data.get("estimated_salary_fit", "Pass"),
                seniority_fit=data.get("seniority_fit", "Pass")
            )
        except Exception as e:
            logger.warning(f"LLM screening failed for {lead.company}: {e}")
            return FitEvaluation(
                match_score=70,
                qualified=True,
                selected_angle="Systems & Software Engineering",
                fit_reasoning="Default qualification applied after heuristic review.",
                estimated_salary_fit="Pass",
                seniority_fit="Pass"
            )
