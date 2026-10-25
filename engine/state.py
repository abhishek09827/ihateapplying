from typing import List, Optional
from pydantic import BaseModel, Field

class JobLead(BaseModel):
    company: str
    domain: str
    role: str
    source_channel: str
    is_remote: bool = True
    location: str = "Remote"
    url: str
    description: str
    salary_raw: Optional[str] = None
    funding_info: Optional[str] = None
    direct_email_hint: Optional[str] = None
    published_at: Optional[str] = None
    timestamp: float = 0.0

class ContactInfo(BaseModel):
    name: str = "Founder / Hiring Lead"
    title: str = "Engineering Decision Maker"
    email: str = ""
    linkedin_url: str = ""
    enrichment_source: str = "Automated Discovery"

class FitEvaluation(BaseModel):
    match_score: int = Field(ge=0, le=100)
    qualified: bool
    selected_angle: str
    fit_reasoning: str
    estimated_salary_fit: str = "Pass"
    seniority_fit: str = "Pass"

class ApplicationPackage(BaseModel):
    lead: JobLead
    contact: ContactInfo
    fit: FitEvaluation
    company_clean_name: str
    cold_email_subject: str
    cold_email_body: str
    linkedin_note: str
    tailored_resume_bullets: List[str]
    pdf_resume_path: Optional[str] = None
    dispatch_status: str = "Pending"
    notion_page_id: Optional[str] = None
    error: Optional[str] = None

class PipelineReport(BaseModel):
    total_leads_fetched: int = 0
    remote_jobs_count: int = 0
    funded_startups_count: int = 0
    screened_out_count: int = 0
    qualified_count: int = 0
    contactable_count: int = 0
    missing_email_count: int = 0
    dispatched_count: int = 0
    notion_synced_count: int = 0
    errors: List[str] = []
