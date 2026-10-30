import json
import logging
from engine.agents.base import BaseAgent
from engine.state import JobLead, ContactInfo, FitEvaluation, ApplicationPackage
from engine.config import MASTER_PROFILE, CANDIDATE_NAME, CANDIDATE_TITLE
from engine.tools.resume_compiler import build_tailored_pdf, validate_pdf_attachment, get_master_resume_pdf
from engine.tools.email_client import format_email_body_with_links

logger = logging.getLogger("ApplicationCrafterAgent")

class ApplicationCrafterAgent(BaseAgent):
    """
    Crafts hyper-targeted, high-converting outreach assets:
    - 75-95 word cold email citing production metrics and technical achievements
    - Under 280 char LinkedIn connection note
    - Tailored resume bullets and compiled Typst PDF
    """

    def __init__(self):
        super().__init__(name="ApplicationCrafterAgent", role="Technical Outreach & Resume Strategist")

    def craft(self, lead: JobLead, contact: ContactInfo, fit: FitEvaluation) -> ApplicationPackage:
        """Generates the full application package including email, LinkedIn note, bullets, and compiled PDF."""
        candidate = MASTER_PROFILE.get("candidate", {})
        highlights = MASTER_PROFILE.get("experience_highlights", [])
        open_source = MASTER_PROFILE.get("open_source", [])

        recipient_first_name = contact.name.split()[0] if contact.name and contact.name not in ("Founder / CTO", "Hiring Lead") else "there"

        highlights_str = "\n".join([f"- {h}" for h in highlights[:3]])
        oss_str = "\n".join([f"- {o}" for o in open_source[:2]]) if open_source else ""
        oss_section = f"Open Source / Key Projects:\n{oss_str}" if oss_str else ""

        concise_profile = f"""
Candidate: {CANDIDATE_NAME} ({CANDIDATE_TITLE})
Experience: {candidate.get('years_experience', '1-3 Years production experience')}
Core Highlights:
{highlights_str}
{oss_section}
"""

        prompt = f"""You are an engineer writing directly to a technical peer (founder, CTO, or engineering lead).

ENGINEER PROFILE:
{concise_profile}

TARGET OPPORTUNITY & TEAM:
Company: {lead.company}
Role: {lead.role}
Channel: {lead.source_channel}
Job Overview / Tech Context: {lead.description[:1200]}

PITCH STRATEGY:
Selected Technical Angle: {fit.selected_angle}
Fit Reasoning: {fit.fit_reasoning}
Recipient: {contact.name} ({contact.title})

CRITICAL GUIDELINES FOR THE EMAIL (ENGINEER-TO-ENGINEER):
1. TONE: Peer-to-peer, pragmatic, technical, and respectful of another engineer's time.
   Sound like two builders talking shop about systems they design, NOT a candidate presenting a list of qualifications.
2. SUBJECT LINE: Short, natural, lowercase or concise sentence case.
   Examples: "{lead.company.lower()}'s architecture & pipelines", "pipelines & infrastructure at {lead.company}", "quick note on {lead.role.lower()} / systems".
   NEVER use formal titles like "Application for..." or "Job Inquiry...".
3. SALUTATION: "Hi {recipient_first_name}," (or "Hi {lead.company} eng team,").
4. OPENING: 1 sentence noticing a specific technical problem or capability {lead.company} is building or scaling.
5. TECHNICAL BRIDGE: Connect on a real engineering challenge or system from candidate summary. Speak to the engineering tradeoff or architecture rather than reciting credentials.
6. STRICT PROHIBITIONS:
   - DO NOT state years of experience ("I have X years of experience...").
   - DO NOT list resume credentials or bulleted qualifications ("My skills include:").
   - DO NOT use applicant clichés: "I am writing to apply", "I am thrilled to express my interest", "I believe I am an ideal fit", "Please find my resume attached".
   - DO NOT use recruiter CTAs: "Would you be open to a 15-minute chat this week?".
7. CALL TO ACTION: Casual, low-friction, engineer-to-engineer curiosity:
   e.g. "Curious how your team is approaching [system challenge] as you scale. Happy to share what worked (and what broke) or grab 10 mins to talk shop if useful."
8. LENGTH: Keep between 65 and 85 words.
9. Do not include signature links in the body (the system appends them automatically).

INSTRUCTIONS FOR LINKEDIN NOTE:
- Under 250 characters.
- Direct, friendly engineer-to-engineer connection request highlighting mutual technical interest.

INSTRUCTIONS FOR RESUME BULLETS:
- Provide exactly 2 impactful bullet points (each 1-2 lines) tailored to {lead.company} and {fit.selected_angle}.
- Quantify impact, cite modern technologies matching the job requirements.

Return ONLY a valid JSON object with keys:
- company_clean_name: string (clean brand name without Inc./LLC/GmbH)
- cold_email_subject: string (short, engaging, professional subject line)
- cold_email_body: string (65-85 word email body)
- linkedin_note: string (<250 char LinkedIn note)
- tailored_resume_bullets: array of 2 strings
"""

        data = self.generate_json(prompt, system_prompt="You are a senior systems engineer reaching out to a fellow engineer. You write concise, high-signal, peer-to-peer notes.", temperature=0.25)

        clean_company = data.get("company_clean_name", lead.company).strip()
        bullets = data.get("tailored_resume_bullets", [
            "Architected scalable distributed workflows and microservices with persistent context.",
            "Engineered high-throughput event processing pipelines with streaming validation."
        ])

        # Compile PDF resume using Typst compiler tool
        pdf_path = None
        try:
            pdf_path = build_tailored_pdf(
                company=clean_company,
                angle=fit.selected_angle,
                bullets=bullets
            )
            logger.info(f"Successfully compiled PDF resume for {clean_company} at {pdf_path}")
        except Exception as e:
            logger.error(f"Typst compilation failed for {clean_company}: {e}")

        # Guaranteed fallback so an attachment is NEVER missing
        if not pdf_path or not validate_pdf_attachment(pdf_path):
            pdf_path = get_master_resume_pdf()
            logger.info(f"Using master resume fallback at {pdf_path}")

        raw_body = data.get("cold_email_body", "")
        formatted_body = format_email_body_with_links(raw_body)

        return ApplicationPackage(
            lead=lead,
            contact=contact,
            fit=fit,
            company_clean_name=clean_company,
            cold_email_subject=data.get("cold_email_subject", f"{lead.role} at {clean_company} — {CANDIDATE_NAME}"),
            cold_email_body=formatted_body,
            linkedin_note=data.get("linkedin_note", ""),
            tailored_resume_bullets=bullets,
            pdf_resume_path=pdf_path,
            dispatch_status="Draft Ready"
        )
