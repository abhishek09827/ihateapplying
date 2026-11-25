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

        prompt = f"""You are {CANDIDATE_NAME}, a software engineer typing a direct, casual, personalized note in Gmail to a founder or fellow engineer at {lead.company}.

YOUR GOAL: Write an email that reads 100% like a real human engineer wrote it from scratch specifically for {lead.company}, so it never trips spam filters or feels like AI/automated outreach.

CANDIDATE BACKGROUND CATALOG (pick ONLY what genuinely fits {lead.company}):
{concise_profile}

TARGET COMPANY & CONTEXT:
Company: {lead.company}
Role: {lead.role}
Domain: {lead.domain}
Channel: {lead.source_channel}
Funding / Signal: {lead.funding_info or 'Tech Startup'}
Company / Role Context: {lead.description[:1200]}

TECHNICAL ANGLE & RECIPIENT:
Selected Technical Angle: {fit.selected_angle}
Fit Reasoning: {fit.fit_reasoning}
Recipient: {contact.name} ({contact.title})

HUMAN STYLE & ANTI-AI / ANTI-SPAM RULES (CRITICAL):
1. SUBJECT LINE: 3-6 words, plain lowercase or natural sentence case, like a real engineer's Gmail subject (e.g. "kafka pipelines at {lead.company.lower()}", "quick question about {lead.company.lower()}"). NO colons, NO em-dashes, NO pipes, NO "Application for...".
2. SALUTATION: Natural greeting like "Hi {recipient_first_name}," or "Hey {recipient_first_name}," (use "Hey {lead.company} team," if no first name).
3. PROSE ONLY — NO BULLET POINTS:
   - Write 2 to 3 very short, conversational paragraphs (60 to 90 words total before signoff).
   - DO NOT use bullet lists (`-` or `•`) inside the email body.
   - DO NOT write "Two things from my background that may be relevant:" or any formulaic template heading.
4. DYNAMICALLY PERSONALIZED TO {lead.company}:
   - Paragraph 1: Jump straight into something specific about what {lead.company} is building or hiring for right now based on the Company/Role Context above (e.g. "Saw you're scaling streaming ingestion at {lead.company}.", "Been digging into {lead.company}'s retrieval pipeline lately.", "Noticed {lead.company}'s work on..."). NEVER open with "I've been following {lead.company}'s work" or "I'm reaching out because".
   - Paragraph 2: Analyze {lead.company}'s domain and requirements, select ONLY the 1-2 most relevant projects/contributions from the Candidate Proof-of-Work Catalog, and weave them into natural spoken English with concrete numbers (like talking to a teammate over Slack, not reading a resume). Use contractions ("I've", "I'm", "you're") and vary sentence lengths.
   - Paragraph 3: End with a brief, genuine, low-pressure question specific to them (e.g. asking if they're looking for help on that part of the stack, or open to a short chat). Vary the closing naturally across emails.
5. STRICT PROHIBITIONS (ANY OF THESE WILL FAIL SPAM/AI CHECKS):
   - NEVER use em-dashes (`—`), semicolons, or emojis.
   - NEVER mention attaching a resume ("I've attached", "tailored resume attached", "please find attached").
   - NEVER mention years or durations of experience ("I have X years", "spent the last year").
   - NEVER use AI/corporate words or formulaic openers: "I've been following", "I'm reaching out because", "delve", "leverage", "utilize", "spearhead", "sustaining", "re-architected", "transactional consistency", "cutting-edge", "robust", "seamless", "streamline", "ecosystem", "impressed by", "came across", "thrilled", "ideal fit", "I hope you are well", "huge fan".
   - DO NOT include signature or URLs at the end (handled separately).

INSTRUCTIONS FOR LINKEDIN NOTE:
- Under 250 characters, plain casual note from one engineer to another referencing their product/domain. No em-dashes or AI buzzwords.

INSTRUCTIONS FOR RESUME BULLETS:
- Exactly 2 concise technical bullets tailored to {lead.company} and {fit.selected_angle} for the attached PDF.

Return ONLY a valid JSON object with keys:
- company_clean_name: string
- cold_email_subject: string
- cold_email_body: string
- linkedin_note: string
- tailored_resume_bullets: array of 2 strings
"""

        data = self.generate_json(
            prompt,
            system_prompt="You are a real software engineer writing short, plain-spoken personal emails in Gmail. You never use em-dashes, bullet lists in outreach emails, corporate buzzwords, or templated phrases.",
            temperature=0.55
        )

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
        raw_subject = data.get("cold_email_subject", f"{clean_company.lower()} engineering")
        clean_subject = raw_subject.strip().replace(" — ", " - ").replace("—", "-")

        return ApplicationPackage(
            lead=lead,
            contact=contact,
            fit=fit,
            company_clean_name=clean_company,
            cold_email_subject=clean_subject,
            cold_email_body=formatted_body,
            linkedin_note=data.get("linkedin_note", ""),
            tailored_resume_bullets=bullets,
            pdf_resume_path=pdf_path,
            dispatch_status="Draft Ready"
        )
