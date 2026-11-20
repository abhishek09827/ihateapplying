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
        projects = MASTER_PROFILE.get("flagship_projects", {})

        recipient_first_name = (
            contact.name.split()[0]
            if contact.name and contact.name not in ("Founder / CTO", "Hiring Lead", "Engineering Decision Maker", "Founder / Engineering Lead")
            else "there"
        )

        catalog_lines = []
        if highlights:
            catalog_lines.append("[EXPERIENCE & PRODUCTION SYSTEMS]")
            for h in highlights:
                catalog_lines.append(f"- {h}")
        if open_source:
            catalog_lines.append("\n[OPEN SOURCE CONTRIBUTIONS]")
            for o in open_source:
                catalog_lines.append(f"- {o}")
        if projects:
            catalog_lines.append("\n[FLAGSHIP PROJECTS & TOOLS]")
            if isinstance(projects, dict):
                for p_name, p_desc in projects.items():
                    catalog_lines.append(f"- {p_desc}")
            elif isinstance(projects, list):
                for p in projects:
                    catalog_lines.append(f"- {p}")

        proof_catalog = "\n".join(catalog_lines)

        concise_profile = f"""
Candidate: {CANDIDATE_NAME} ({CANDIDATE_TITLE})
Background / Experience: {candidate.get('years_experience', 'Production software & systems engineer')}
Target Skills: {', '.join(candidate.get('target_skills', []))}

CANDIDATE PROOF-OF-WORK CATALOG:
{proof_catalog}
"""

        prompt = f"""You are an engineer writing directly to a technical peer or founder (founder, CTO, or engineering lead).
You follow the proven cold outreach principles from 'The Guide to Getting a Job with Cold Email':
1. You can email any company you want to work for, even without a formal job post. Startups always make exceptions for competent engineers who show proof of work.
2. Under 100 words (optimal: 70-90 words). Less is more. Busy founders and engineers discard walls of text.
3. Zero buzzwords (no "executed key initiatives", "drove impact", "thrilled to apply", "unique qualifications"). Use plain, honest, human language. Must pass the 'read out loud' test.
4. Specificity over abstraction: Cite concrete systems built and numbers matching the target company's domain.
5. Always end with a clear, specific, low-friction ask ("Worth a chat?").

CANDIDATE PROFILE:
{concise_profile}

TARGET OPPORTUNITY & TEAM:
Company: {lead.company}
Role: {lead.role}
Domain: {lead.domain}
Source Channel: {lead.source_channel}
Funding / Signal: {lead.funding_info or 'High-Growth Tech Startup'}
Job Overview / Tech Context: {lead.description[:1200]}

PITCH STRATEGY:
Selected Technical Angle: {fit.selected_angle}
Fit Reasoning: {fit.fit_reasoning}
Recipient: {contact.name} ({contact.title})

CRITICAL STRUCTURE REQUIREMENTS FOR THE EMAIL (3-PART FORMAT):
1. SUBJECT LINE: Short, natural, lowercase or concise sentence case.
   Examples: "{lead.company.lower()}'s data pipelines", "scaling streaming at {lead.company.lower()}", "helping build {lead.company.lower()}", "quick note on {lead.company.lower()}'s infra".
   NEVER use formal titles like "Application for..." or "Job Inquiry...".
2. SALUTATION: "Hi {recipient_first_name}," (or "Hi {lead.company} team,").
3. PART 1 — WHO YOU ARE & WHY REACHING OUT (1-2 sentences):
   Introduce yourself plainly as an engineer and mention specifically how you came across what they're building at {lead.company} (e.g. in their specific domain / recent product update / GitHub / funding) and wanted to reach out directly to help build and scale the subsystem.
4. PART 2 — WHY THEY SHOULD CARE (DYNAMICALLY MATCHED TO {lead.company}'s BACKGROUND & REQUIREMENTS):
   - Analyze {lead.company}'s core business domain, tech stack, and role requirements:
     * Match the company's domain (e.g. data streaming, vector search/RAG, agent workflows, devtools, cloud infra) with the MOST RELEVANT achievements and systems from the candidate's proof-of-work catalog.
     * Write "Two things from my background that may be relevant:" followed by EXACTLY 2 bullet points.
     * Select the 2 accomplishments from the catalog that MOST DIRECTLY solve {lead.company}'s engineering challenges.
     * Make the proof points feel genuinely custom-tailored to their technical product.
5. PART 3 — CLEAR, LOW-FRICTION ASK (1 sentence):
   "I think I could help your team build out and scale [specific subsystem/feature relevant to {lead.company}] quickly and would like to learn more. Worth a chat?" (or "Open to 10 mins this week to talk shop?").
6. STRICT PROHIBITIONS:
   - DO NOT state years of experience ("I have 2 years of experience...").
   - DO NOT write walls of text. Keep between 70 and 95 words total before signature.
   - DO NOT use applicant clichés: "I am writing to apply", "I believe I am an ideal fit", "Please find my resume attached".
   - DO NOT include fake flattery ("been a huge fan for years", "I loved your LinkedIn post").
   - Do not include signature links in the body (the system appends them automatically).

INSTRUCTIONS FOR LINKEDIN NOTE:
- Under 250 characters.
- Direct, friendly engineer-to-engineer connection request citing mutual technical domain.

INSTRUCTIONS FOR RESUME BULLETS:
- Exactly 2 high-impact technical bullets tailored to {lead.company} and {fit.selected_angle}.
- Emphasize architecture, concrete metrics, and relevant stack.

Return ONLY a valid JSON object with keys:
- company_clean_name: string
- cold_email_subject: string
- cold_email_body: string
- linkedin_note: string
- tailored_resume_bullets: array of 2 strings
"""

        data = self.generate_json(prompt, system_prompt="You are a senior systems and AI engineer reaching out to a fellow engineer. You write concise, high-signal, peer-to-peer notes.", temperature=0.25)

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
