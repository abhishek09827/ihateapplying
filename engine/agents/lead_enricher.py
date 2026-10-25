import re
import logging
import urllib.parse
from typing import Optional, Tuple
import requests
from bs4 import BeautifulSoup
from engine.agents.base import BaseAgent
from engine.state import JobLead, ContactInfo
from engine.config import SERPER_API_KEY
from engine.tools.email_verifier import verify_and_clean_email, does_domain_exist

logger = logging.getLogger("EnrichmentAgent")

class EnrichmentAgent(BaseAgent):
    """
    Enriches leads with decision-maker contact details (Name, Title, Email, LinkedIn).
    Uses Google Search (Serper API) + LLM entity extraction, website crawling,
    and enforces strict DNS deliverability checks so emails never bounce.
    """

    def __init__(self):
        super().__init__(name="EnrichmentAgent", role="Executive Contact Intelligence Specialist")

    def enrich(self, lead: JobLead) -> ContactInfo:
        """Discovers decision-maker contact details. Prioritizes search and deterministic extraction."""
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

        effective_domain = lead.domain

        # 2. Google Search via Serper API + LLM Extraction (Finds true domain & contact email)
        serper_email, serper_name, serper_title, real_dom = self._search_web_with_serper(lead.company, lead.domain)
        if real_dom:
            effective_domain = real_dom

        if serper_email:
            return ContactInfo(
                name=serper_name or "Hiring Lead",
                title=serper_title or "Talent Acquisition / Leadership",
                email=serper_email,
                linkedin_url=f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote((serper_name or '') + ' ' + lead.company)}",
                enrichment_source="Google Search + LLM Intelligence (DNS Verified)"
            )

        # 3. Deterministic Website Scraping (/about, /team, /company, /contact, /impressum)
        scraped_email, scraped_linkedin, team_text = self._crawl_company_website(effective_domain)

        if scraped_email and scraped_linkedin:
            is_valid, clean_scraped, _ = verify_and_clean_email(scraped_email)
            if is_valid and clean_scraped:
                name_from_li = self._extract_name_from_linkedin(scraped_linkedin) or "Founder / CTO"
                return ContactInfo(
                    name=name_from_li,
                    title="Co-Founder / Engineering Lead",
                    email=clean_scraped,
                    linkedin_url=scraped_linkedin,
                    enrichment_source="Website Team Scraping (DNS Verified)"
                )

        # 4. Targeted LLM Extraction (Only if scrape left ambiguous gaps)
        extracted_info = {}
        if team_text or len(lead.description) > 100:
            extracted_info = self._infer_leadership_contact(lead, team_text)

        founder_name = extracted_info.get("founder_name") or "Founder / CTO"
        founder_title = extracted_info.get("founder_title") or "Technical Decision Maker"

        candidate_email = ""
        if scraped_email:
            candidate_email = scraped_email
        elif extracted_info.get("suggested_email"):
            candidate_email = extracted_info.get("suggested_email")

        # 5. Strict DNS Verification Check
        final_email = ""
        if candidate_email:
            is_valid, verified_email, reason = verify_and_clean_email(candidate_email)
            final_email = verified_email if is_valid else ""

        final_linkedin = ""
        if scraped_linkedin:
            final_linkedin = scraped_linkedin
        elif extracted_info.get("linkedin_url"):
            final_linkedin = extracted_info.get("linkedin_url")
        else:
            q = f"{founder_name} {lead.company}".strip()
            final_linkedin = f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote(q)}"

        return ContactInfo(
            name=founder_name,
            title=founder_title,
            email=final_email,
            linkedin_url=final_linkedin,
            enrichment_source="Hybrid Intelligence (DNS Verified)" if final_email else "LinkedIn Only (No Verified Email)"
        )

    def _extract_name_from_linkedin(self, url: str) -> Optional[str]:
        match = re.search(r'linkedin\.com/in/([a-zA-Z0-9_-]+)', url)
        if match:
            slug = match.group(1).replace("-", " ").replace("_", " ")
            slug_words = [w.capitalize() for w in slug.split() if not w.isdigit()]
            if slug_words:
                return " ".join(slug_words[:3])
        return None

    def _crawl_company_website(self, domain: str) -> Tuple[Optional[str], Optional[str], str]:
        if not domain:
            return None, None, ""

        clean_domain = domain.replace("http://", "").replace("https://", "").strip("/").split("/")[0]
        if not does_domain_exist(clean_domain):
            return None, None, ""

        base_url = f"https://{clean_domain}"
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        paths = ["/about", "/team", "/company", "/contact", "/impressum", ""]
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

                    emails = re.findall(r'[a-zA-Z0-9_.+-]+@' + re.escape(clean_domain), text)
                    for e in emails:
                        e_low = e.lower()
                        if not e_low.startswith(("privacy@", "terms@", "abuse@", "legal@")):
                            scraped_emails.add(e_low)

                    linkedins = re.findall(r'https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9_-]+', text)
                    for li in linkedins:
                        scraped_linkedins.add(li)

                    if scraped_emails or scraped_linkedins:
                        break
            except Exception:
                continue

        best_email = None
        if scraped_emails:
            preferred = [e for e in scraped_emails if not e.startswith(("info@", "sales@", "support@", "hello@"))]
            best_email = preferred[0] if preferred else list(scraped_emails)[0]

        best_linkedin = list(scraped_linkedins)[0] if scraped_linkedins else None
        return best_email, best_linkedin, combined_text

    def _infer_leadership_contact(self, lead: JobLead, scraped_text: str) -> dict:
        prompt = f"""Identify the most likely technical leader or founder for outreach at {lead.company}.

Company: {lead.company}
Domain: {lead.domain}
Job Role: {lead.role}
Context / Web Snippets:
{lead.description[:1000]}
{scraped_text[:1000]}

Instructions:
1. Identify the name of the Founder, Co-Founder, CTO, or VP of Engineering.
2. If the exact name is mentioned in the text, use it.
3. Suggest the most probable direct email address (e.g. firstname@domain or founders@domain).
4. Provide a LinkedIn search URL or profile if available.

Return ONLY a JSON object with keys:
- founder_name: string (e.g. "Jane Doe" or "Founder / CTO")
- founder_title: string (e.g. "Co-Founder & CEO" or "CTO")
- suggested_email: string (e.g. "jane@company.com" or "founders@company.com")
- linkedin_url: string
"""
        try:
            return self.generate_json(prompt, system_prompt="You are an expert executive talent researcher.", temperature=0.2)
        except Exception as e:
            logger.warning(f"Leadership inference failed: {e}")
            return {}

    def _search_web_with_serper(self, company: str, domain: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        if not SERPER_API_KEY:
            return None, None, None, None

        url = "https://google.serper.dev/search"
        headers = {
            "X-API-KEY": SERPER_API_KEY,
            "Content-Type": "application/json"
        }
        payload = {
            "q": f'"{company}" contact email OR impressum OR careers',
            "num": 6
        }

        try:
            res = requests.post(url, headers=headers, json=payload, timeout=8)
            if res.status_code == 403:
                logger.warning(f"Serper API returned 403 for {company} (Key expired or invalid on serper.dev).")
                return None, None, None, None
            if res.status_code != 200:
                logger.warning(f"Serper API query failed: {res.status_code} - {res.text[:80]}")
                return None, None, None, None

            data = res.json()
            organic = data.get("organic", [])
            if not organic:
                return None, None, None, None

            snippets = []
            for item in organic:
                t = item.get("title", "")
                link = item.get("link", "")
                snip = item.get("snippet", "")
                snippets.append(f"Title: {t}\nURL: {link}\nSnippet: {snip}")

            corpus = "\n\n".join(snippets)

            candidate_emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', corpus)
            for cand in candidate_emails:
                cand_clean = cand.rstrip(".")
                if not any(x in cand_clean.lower() for x in ["example", "sentry", "schema", "w3.org", "png", "jpg"]):
                    is_valid, verified, _ = verify_and_clean_email(cand_clean)
                    if is_valid:
                        return verified, "Hiring Team", "Talent Acquisition", None

            prompt = f"""Analyze the following Google Search results for the company "{company}".
Find:
1. The official contact or inquiry email address (if visible).
2. The real website domain of the company (e.g. "sdu.nl", "f-e.de", "bjak.my", "careship.de").
3. The name and title of the Founder, CEO, CTO, or Talent Lead if mentioned.

Google Search Snippets:
{corpus[:2000]}

Return ONLY a JSON object with keys:
- email: string (exact email or empty string)
- real_domain: string (e.g. "sdu.nl" or empty string)
- contact_name: string (e.g. "Jane Doe" or "Founder / CTO")
- contact_title: string (e.g. "Engineering Lead" or "Founder")
"""
            llm_data = self.generate_json(prompt, system_prompt="You are an expert executive talent researcher.", temperature=0.1)
            raw_email = llm_data.get("email", "").strip()
            real_dom = llm_data.get("real_domain", "").strip()
            name = llm_data.get("contact_name") or "Founder / CTO"
            title = llm_data.get("contact_title") or "Technical Decision Maker"

            if raw_email:
                is_valid, verified, _ = verify_and_clean_email(raw_email)
                if is_valid:
                    return verified, name, title, real_dom

            return None, name, title, real_dom

        except Exception as e:
            logger.warning(f"Serper search failed for {company}: {e}")
            return None, None, None, None
