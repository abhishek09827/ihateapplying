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

        prompt = f"""You are the elite technical career agent for {CANDIDATE_NAME}.
CANDIDATE SUMMARY:
{concise_profile}

TARGET OPPORTUNITY:
Company: {lead.company}
Role: {lead.role}
Channel: {lead.source_channel}
Funding Info: {lead.funding_info or 'VC-backed'}
Job Description / Overview: {lead.description[:1200]}

STRATEGIC DECISION:
Selected Angle: {fit.selected_angle}
Fit Reasoning: {fit.fit_reasoning}
Recipient: {contact.name} ({contact.title})

INSTRUCTIONS FOR COLD EMAIL:
1. Address the recipient naturally (e.g. "Hi {recipient_first_name}," or "Hi {lead.company} team,").
2. Keep length STRICTLY between 75 and 95 words.
3. Open with a 1-sentence hook demonstrating clear understanding of what {lead.company} is building or their recent milestone.
4. Pitch {CANDIDATE_NAME} for the {lead.role} role. CITE:
   - Specific production metrics and technical impact from candidate summary.
   - Genuine alignment with {lead.company}'s mission and technical stack.
5. End with a low-friction CTA: "Would you be open to a 15-minute chat this week? I've attached my tailored resume for reference."
6. NO generic filler sentences ("I hope you are well", "I am thrilled to apply", etc.).
7. Do not include candidate signature links at the end (these are appended automatically by the system).

INSTRUCTIONS FOR LINKEDIN NOTE:
- Under 280 characters.
- Crisp, respectful connection request highlighting relevant fit.

INSTRUCTIONS FOR RESUME BULLETS:
- Provide exactly 2 impactful bullet points (each 1-2 lines) tailored to {lead.company} and {fit.selected_angle}.
- Quantify impact, cite modern technologies matching the job requirements.

Return ONLY a valid JSON object with keys:
- company_clean_name: string (clean brand name without Inc./LLC/GmbH)
- cold_email_subject: string (short, engaging, professional subject line)
- cold_email_body: string (75-95 word email body)
- linkedin_note: string (<280 char LinkedIn note)
- tailored_resume_bullets: array of 2 strings
"""

        data = self.generate_json(prompt, system_prompt="You are an elite executive copywriter and technical recruiter.", temperature=0.25)

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
