import os
import re
import typst
import logging
from pathlib import Path
from typing import List, Optional
from engine.config import (
    TEMPLATE_PATH,
    GENERATED_RESUMES_DIR,
    MASTER_PROFILE,
    CANDIDATE_NAME,
    CANDIDATE_TITLE,
    CANDIDATE_PHONE,
    CANDIDATE_EMAIL,
    PORTFOLIO_URL,
    GITHUB_URL,
    LINKEDIN_URL
)

logger = logging.getLogger("ResumeCompiler")

def sanitize_typst_text(text: str) -> str:
    """Escapes literal characters (<, @) that trigger Typst syntax errors when in content mode."""
    if not text:
        return ""
    # Escape bare < (e.g. <2ms, <100ms)
    s = re.sub(r'<(?=[0-9a-zA-Z\s])(?![a-zA-Z0-9_\-:]+>)', r'\<', text)
    # Escape bare @ when followed by alphanumeric domain (e.g. user@domain)
    s = re.sub(r'@(?=[a-zA-Z0-9])', r'\@', s)
    return s

def get_candidate_contact_line() -> str:
    """Builds a formatted contact header line for Typst."""
    parts = []
    if CANDIDATE_PHONE:
        parts.append(CANDIDATE_PHONE)
    if CANDIDATE_EMAIL:
        clean_email_label = CANDIDATE_EMAIL.replace("@", r"\@")
        parts.append(f'#link("mailto:{CANDIDATE_EMAIL}")[{clean_email_label}]')
    if LINKEDIN_URL:
        clean_li = LINKEDIN_URL.replace("https://", "").replace("http://", "").rstrip("/")
        parts.append(f'#link("{LINKEDIN_URL}")[{clean_li}]')
    if GITHUB_URL:
        clean_gh = GITHUB_URL.replace("https://", "").replace("http://", "").rstrip("/")
        parts.append(f'#link("{GITHUB_URL}")[{clean_gh}]')
    if PORTFOLIO_URL:
        clean_pf = PORTFOLIO_URL.replace("https://", "").replace("http://", "").rstrip("/")
        parts.append(f'#link("{PORTFOLIO_URL}")[{clean_pf}]')

    return " | ".join(parts)

def build_experience_typst() -> str:
    """Formats candidate experience highlights into Typst markup."""
    highlights = MASTER_PROFILE.get("experience_highlights", [])
    if not highlights:
        return "Proven track record delivering reliable software and systems in production."
    return sanitize_typst_text("\n".join([f"- {h}" for h in highlights]))

def build_projects_typst() -> str:
    """Formats flagship projects into Typst markup."""
    projects = MASTER_PROFILE.get("flagship_projects", {})
    if not projects:
        return "- Scalable backend applications and automated multi-agent systems."
    lines = []
    for name, desc in projects.items():
        lines.append(f"- *{name}:* {desc}")
    return sanitize_typst_text("\n".join(lines))

def build_skills_typst() -> str:
    """Formats technical skills into Typst markup."""
    skills = MASTER_PROFILE.get("candidate", {}).get("target_skills", [
        "Python", "FastAPI", "Kafka", "Docker", "Kubernetes", "PostgreSQL"
    ])
    return sanitize_typst_text(", ".join(skills))

def build_education_typst() -> str:
    """Formats candidate education into Typst markup."""
    edu = MASTER_PROFILE.get("candidate", {}).get("education", "B.S. in Computer Science")
    return sanitize_typst_text(f"- {edu}")

def build_tailored_pdf(
    company: str,
    angle: str,
    bullets: List[str],
    output_dir: Optional[Path] = None
) -> str:
    """
    Compiles a hyper-targeted Typst PDF resume tailored to the target company.
    Injects candidate profile data and company-specific bullet points.
    """
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Resume template not found at {TEMPLATE_PATH}")

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()

    formatted_bullets = sanitize_typst_text("\n".join([f"- {b}" for b in bullets]))
    contact_line = get_candidate_contact_line()
    exp_markup = build_experience_typst()
    proj_markup = build_projects_typst()
    skills_markup = build_skills_typst()
    edu_markup = build_education_typst()

    clean_comp = re.sub(r'[^a-zA-Z0-9]', '', company) or "Company"
    clean_name = re.sub(r'[^a-zA-Z0-9]', '_', CANDIDATE_NAME) or "Candidate"

    filled = (
        template
        .replace("{{CANDIDATE_NAME}}", CANDIDATE_NAME)
        .replace("{{CANDIDATE_TITLE}}", CANDIDATE_TITLE)
        .replace("{{CANDIDATE_CONTACT_LINE}}", contact_line)
        .replace("{{COMPANY_NAME}}", company.upper())
        .replace("{{ANGLE_TITLE}}", angle)
        .replace("{{TAILORED_BULLETS}}", formatted_bullets)
        .replace("{{EXPERIENCE_SECTION}}", exp_markup)
        .replace("{{PROJECTS_SECTION}}", proj_markup)
        .replace("{{SKILLS_SECTION}}", skills_markup)
        .replace("{{EDUCATION_SECTION}}", edu_markup)
    )

    out_dir = output_dir or GENERATED_RESUMES_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    typ_path = out_dir / f"resume_{clean_comp}.typ"
    pdf_path = out_dir / f"{clean_name}_{clean_comp}.pdf"

    with open(typ_path, "w", encoding="utf-8") as f:
        f.write(filled)

    typst.compile(str(typ_path), output=str(pdf_path))
    return str(pdf_path)

def validate_pdf_attachment(pdf_path: Optional[str]) -> bool:
    """Verifies that the compiled PDF exists and is a non-empty, readable document."""
    if not pdf_path:
        return False
    p = Path(pdf_path)
    if not p.exists() or not p.is_file():
        return False
    # Validate minimum file size (> 1KB)
    return p.stat().st_size > 1024

def get_master_resume_pdf() -> str:
    """Builds a verified fallback master resume PDF if tailored compilation is skipped."""
    master_pdf = GENERATED_RESUMES_DIR / f"{re.sub(r'[^a-zA-Z0-9]', '_', CANDIDATE_NAME)}_Master.pdf"
    if master_pdf.exists() and validate_pdf_attachment(str(master_pdf)):
        return str(master_pdf)

    return build_tailored_pdf(
        company="Global Enterprise",
        angle="Applied Engineering Systems",
        bullets=[
            "Architected scalable distributed workflows and microservices with persistent context.",
            "Engineered high-throughput event processing pipelines with streaming validation."
        ]
    )


def compile_tailored_resume(
    company_clean: str,
    role_title: str = "Software Engineering",
    tailored_bullets: Optional[List[str]] = None,
    output_dir: Optional[Path] = None
) -> str:
    """Convenience wrapper for compiling a tailored PDF resume."""
    bullets = tailored_bullets or [f"Targeted technical contributions and system design for {company_clean}"]
    return build_tailored_pdf(
        company=company_clean,
        angle=role_title,
        bullets=bullets,
        output_dir=output_dir
    )

