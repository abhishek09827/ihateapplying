import re
import logging
import urllib.parse
from typing import Optional, Tuple
import requests
from bs4 import BeautifulSoup
from engine.agents.base import BaseAgent
from engine.state import JobLead, ContactInfo
from engine.config import SERPER_API_KEY
from engine.tools.email_verifier import verify_and_clean_email, does_domain_exist, is_valid_email_syntax

logger = logging.getLogger("EnrichmentAgent")

class EnrichmentAgent(BaseAgent):
    """
    Discovers authentic decision-maker and recruiting contact details (Name, Title, Email, LinkedIn).
    Prioritizes real canonical domain resolution, targeted Google search via Serper API,
    crawling of /careers, /jobs, /contact, /impressum, and direct job description extraction.
    Strictly forbids synthetic/hallucinated email guessing to eliminate email bounces.
    """

    def __init__(self):
        super().__init__(name="EnrichmentAgent", role="Executive Contact Intelligence Specialist")

    def enrich(self, lead: JobLead) -> ContactInfo:
        """Discovers verified decision-maker and recruiting contacts."""
        # 1. Deterministic Source Hint (HN comment direct email or curated record)
        if lead.direct_email_hint and "@" in lead.direct_email_hint:
            is_valid, clean_hint, reason = verify_and_clean_email(lead.direct_email_hint)
            if is_valid and clean_hint:
                return ContactInfo(
                    name="Hiring Lead / Founder",
                    title="Engineering Leadership",
                    email=clean_hint,
                    linkedin_url=f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote(lead.company + ' Founder CTO')}",
                    enrichment_source="Source Direct Mention (DNS Verified)"
                )

        # 2. Extract explicit emails from job description if present
        desc_email = self._extract_email_from_text(lead.description)
        if desc_email:
            is_valid, clean_desc_email, _ = verify_and_clean_email(desc_email)
            if is_valid and clean_desc_email:
                return ContactInfo(
                    name="Hiring Team",
                    title="Talent Acquisition / Engineering",
                    email=clean_desc_email,
                    linkedin_url=f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote(lead.company + ' Engineering Lead')}",
                    enrichment_source="Job Posting Description (Verified)"
                )

        # 3. Resolve canonical company domain (Clearbit, Serper, Job URL)
        effective_domain = self._resolve_canonical_domain(lead.company, lead.domain, lead.url)

        # 4. Google Search via Serper API with multi-query targeting
        serper_email, serper_name, serper_title, real_dom = self._search_web_with_serper(lead.company, effective_domain)
        if real_dom:
            effective_domain = real_dom

        if serper_email:
            return ContactInfo(
                name=serper_name or "Hiring Team",
                title=serper_title or "Talent Acquisition / Leadership",
                email=serper_email,
                linkedin_url=f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote((serper_name or '') + ' ' + lead.company)}",
                enrichment_source="Google Search Verification (MX Verified)"
            )

        # 5. Deterministic Website Scraping (/careers, /jobs, /contact, /impressum, /about)
        scraped_email, scraped_linkedin, team_text = self._crawl_company_website(effective_domain)

        if scraped_email:
            is_valid, clean_scraped, _ = verify_and_clean_email(scraped_email)
            if is_valid and clean_scraped:
                name_from_li = self._extract_name_from_linkedin(scraped_linkedin) if scraped_linkedin else "Hiring Lead"
                return ContactInfo(
                    name=name_from_li or "Hiring Team",
                    title="Engineering Leadership / Talent",
                    email=clean_scraped,
                    linkedin_url=scraped_linkedin or f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote(lead.company + ' Founder CTO')}",
                    enrichment_source="Website Crawl (MX Verified)"
                )

        # 6. Extract leadership identity for personalized pitch angle (NO SYNTHETIC EMAIL GUESSING)
        extracted_info = {}
        if team_text or len(lead.description) > 100:
            extracted_info = self._infer_leadership_contact(lead, team_text)

        founder_name = extracted_info.get("founder_name") or "Founder / CTO"
        founder_title = extracted_info.get("founder_title") or "Engineering Leadership"

        final_linkedin = scraped_linkedin or extracted_info.get("linkedin_url") or f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote(founder_name + ' ' + lead.company)}"

        # If no verified email could be found, return empty email to prevent bounces
        return ContactInfo(
            name=founder_name,
            title=founder_title,
            email="",
            linkedin_url=final_linkedin,
            enrichment_source="Careers Portal / Manual ATS Apply"
        )

    def _extract_email_from_text(self, text: str) -> Optional[str]:
        """Extracts direct application/recruiting emails from job posting descriptions."""
        if not text:
            return None
        matches = re.findall(r'[a-zA-Z0-9_.+-]+@(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}', text)
        for m in matches:
            m_clean = m.lower().rstrip(".,;")
            if not any(bad in m_clean for bad in ["example", "sentry", "schema", "w3.org", "png", "jpg", "jpeg"]):
                return m_clean
        return None

    def _resolve_canonical_domain(self, company: str, initial_domain: str, job_url: str = "") -> str:
        """Resolves the real canonical company domain using URL redirect, Clearbit, and search."""
        # 1. From job_url if it directly points to company domain
        if job_url:
            try:
                parsed = urllib.parse.urlparse(job_url)
                netloc = parsed.netloc.lower().replace("www.", "")
                if netloc and not any(ats in netloc for ats in ["greenhouse.io", "ashbyhq.com", "lever.co", "remoteok.com", "remotive.com", "jobicy.com", "arbeitnow.com", "weworkremotely.com"]):
                    return netloc
            except Exception:
                pass

        # 2. Clearbit Company Suggest API (Free, high-accuracy domain resolution)
        try:
            r = requests.get(f"https://autocomplete.clearbit.com/v1/companies/suggest?query={urllib.parse.quote(company)}", timeout=3)
            if r.status_code == 200 and r.json():
                for item in r.json():
                    dom = item.get("domain", "").lower()
                    if dom and not dom.endswith((".gov", ".edu")):
                        return dom
        except Exception:
            pass

        # 3. Serper Organic Search for official company domain
        from engine.config import SERPER_API_KEY
        if SERPER_API_KEY:
            try:
                headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
                res = requests.post("https://google.serper.dev/search", headers=headers, json={"q": f'"{company}" official website', "num": 3}, timeout=5)
                if res.status_code == 200:
                    for org in res.json().get("organic", []):
                        link = org.get("link", "")
                        netloc = urllib.parse.urlparse(link).netloc.lower().replace("www.", "")
                        if netloc and not any(b in netloc for b in ["linkedin.com", "wikipedia.org", "glassdoor.com", "indeed.com", "crunchbase.com", "facebook.com", "twitter.com", "x.com", "youtube.com"]):
                            return netloc
            except Exception:
                pass

        return initial_domain or f"{re.sub(r'[^a-zA-Z0-9]', '', company).lower()}.com"

    def _extract_name_from_linkedin(self, url: str) -> Optional[str]:
        """Deduces clean human name from LinkedIn profile slug."""
        match = re.search(r'linkedin\.com/in/([a-zA-Z0-9_-]+)', url)
        if match:
            slug = match.group(1).replace("-", " ").replace("_", " ")
            slug_words = [w.capitalize() for w in slug.split() if not w.isdigit()]
            if slug_words:
                return " ".join(slug_words[:3])
        return None

    def _crawl_company_website(self, domain: str) -> Tuple[Optional[str], Optional[str], str]:
        """Crawls standard company pages (/careers, /jobs, /contact, /impressum, /about) looking for emails."""
        if not domain or not does_domain_exist(domain):
            return None, None, ""

        clean_domain = domain.replace("http://", "").replace("https://", "").strip("/").split("/")[0]
        base_url = f"https://{clean_domain}"
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        paths = ["/careers", "/jobs", "/contact", "/impressum", "/about", ""]
        scraped_emails = set()
        scraped_linkedins = set()
        combined_text = ""

        for path in paths:
            url = base_url + path
            try:
                res = requests.get(url, headers=headers, timeout=4, allow_redirects=True)
                if res.status_code == 200:
                    text = res.text
                    soup = BeautifulSoup(text, "html.parser")
                    clean_text = soup.get_text()[:2500]
                    combined_text += " " + clean_text

                    # Extract mailto links
                    for a in soup.find_all("a", href=True):
                        href = a["href"].strip()
                        if href.startswith("mailto:"):
                            raw_m = href.replace("mailto:", "").split("?")[0].strip().lower()
                            if is_valid_email_syntax(raw_m):
                                is_v, v_clean, _ = verify_and_clean_email(raw_m)
                                if is_v:
                                    scraped_emails.add(v_clean)

                    # Extract emails matching domain
                    emails = re.findall(r'[a-zA-Z0-9_.+-]+@' + re.escape(clean_domain), text)
                    for e in emails:
                        e_low = e.lower().rstrip(".,;")
                        if not any(bad in e_low for bad in ["privacy@", "terms@", "abuse@", "legal@", "security@"]):
                            is_v, v_clean, _ = verify_and_clean_email(e_low)
                            if is_v:
                                scraped_emails.add(v_clean)

                    # Extract personal LinkedIn profiles
                    linkedins = re.findall(r'https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9_-]+', text)
                    for li in linkedins:
                        scraped_linkedins.add(li)

                    if scraped_emails:
                        break
            except Exception:
                continue

        # Prefer recruitment/careers email over general support/info
        best_email = None
        if scraped_emails:
            preferred = [e for e in scraped_emails if any(h in e for h in ["careers@", "jobs@", "talent@", "hiring@", "recruiting@", "hr@"])]
            if preferred:
                best_email = preferred[0]
            else:
                contact_pref = [e for e in scraped_emails if any(h in e for h in ["contact@", "hello@", "info@"])]
                best_email = contact_pref[0] if contact_pref else list(scraped_emails)[0]

        best_linkedin = list(scraped_linkedins)[0] if scraped_linkedins else None
        return best_email, best_linkedin, combined_text

    def _infer_leadership_contact(self, lead: JobLead, scraped_text: str) -> dict:
        """Uses LLM to identify technical leadership for personalization. Strictly does not fabricate emails."""
        prompt = f"""Identify the technical leader, founder, or engineering manager for outreach at {lead.company}.

Company: {lead.company}
Domain: {lead.domain}
Job Role: {lead.role}
Context / Web Snippets:
{lead.description[:1000]}
{scraped_text[:1000]}

Instructions:
1. Identify the name of the Founder, Co-Founder, CTO, or VP of Engineering if mentioned.
2. Provide their title.
3. Provide a LinkedIn search URL or profile if available.
DO NOT fabricate or guess email addresses.

Return ONLY a JSON object with keys:
- founder_name: string (e.g. "Jane Doe" or "Founder / CTO")
- founder_title: string (e.g. "Co-Founder & CEO" or "CTO")
- linkedin_url: string
"""
        try:
            return self.generate_json(prompt, system_prompt="You are an expert executive talent researcher. Never invent emails.", temperature=0.1)
        except Exception as e:
            logger.warning(f"Leadership inference failed: {e}")
            return {}

    def _search_web_with_serper(self, company: str, domain: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        """
        Uses Google Search via Serper API to discover authentic company emails and real domains.
        Returns (email, contact_name, title, real_domain).
        """
        from engine.config import SERPER_API_KEY
        if not SERPER_API_KEY:
            return None, None, None, None

        url = "https://google.serper.dev/search"
        headers = {
            "X-API-KEY": SERPER_API_KEY,
            "Content-Type": "application/json"
        }

        queries = [
            f'"{company}" contact email OR impressum OR careers',
            f'"{company}" ("careers@" OR "jobs@" OR "talent@" OR "recruiting@" OR "hr@" OR "info@" OR "kontakt@")'
        ]

        for q in queries:
            try:
                res = requests.post(url, headers=headers, json={"q": q, "num": 5}, timeout=6)
                if res.status_code != 200:
                    continue

                data = res.json()
                snippets = []
                for item in data.get("organic", []):
                    snippets.append(f"{item.get('title', '')} {item.get('snippet', '')}")

                corpus = " ".join(snippets)

                # Search for direct emails in search snippets
                candidate_emails = re.findall(r'[a-zA-Z0-9_.+-]+@(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}', corpus)
                for cand in candidate_emails:
                    cand_clean = cand.lower().rstrip(".,;")
                    if not any(bad in cand_clean for bad in ["example", "sentry", "schema", "w3.org", "png", "jpg", "google", "serper"]):
                        is_valid, verified, _ = verify_and_clean_email(cand_clean)
                        if is_valid:
                            cand_dom = cand_clean.split("@")[-1]
                            if (domain and domain in cand_dom) or any(h in cand_clean for h in ["careers@", "jobs@", "talent@", "recruiting@", "hr@", "info@", "hiring@", "contact@"]):
                                return verified, "Hiring Team", "Talent Acquisition", cand_dom

                # LLM extraction of strictly visible factual entities
                prompt = f"""Analyze the following Google Search results for the company "{company}".
Google Search Snippets:
{corpus[:2000]}

Find ONLY real, explicitly visible information:
1. Contact email address (ONLY if explicitly mentioned in the text).
2. The real website domain of the company (e.g. "sdu.nl", "f-e.de", "bjak.my", "careship.de").
3. The name and title of the Founder, CEO, CTO, or Talent Lead if mentioned.

Return ONLY a JSON object:
- email: string (exact email found, or empty string if not found)
- real_domain: string (e.g. "sdu.nl" or empty string)
- contact_name: string (name if found, or empty string)
- contact_title: string (title if found, or empty string)
"""
                llm_data = self.generate_json(prompt, system_prompt="You are an expert executive talent researcher. Never invent emails.", temperature=0.0)
                raw_email = llm_data.get("email", "").strip()
                real_dom = llm_data.get("real_domain", "").strip()
                name = llm_data.get("contact_name") or "Hiring Team"
                title = llm_data.get("contact_title") or "Talent Acquisition"

                if raw_email and "@" in raw_email:
                    is_valid, verified, _ = verify_and_clean_email(raw_email)
                    if is_valid:
                        return verified, name, title, real_dom

                if real_dom:
                    return None, name, title, real_dom

            except Exception as e:
                logger.warning(f"Serper search failed for {company}: {e}")

        return None, None, None, None
