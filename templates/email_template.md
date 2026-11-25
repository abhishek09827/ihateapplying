# Cold Outreach Email Format & Copywriting Guidelines
# The ApplicationCrafterAgent uses natural, peer-to-peer prose tailored
# specifically to each target company so emails read like a human Gmail note
# and avoid spam/AI detection triggers.

---

### Format Architecture

```text
Subject: {{SHORT_LOWERCASE_SUBJECT}} (e.g. "kafka ingestion at {{COMPANY}}")

Hi {{RECIPIENT_FIRST_NAME}},

{{CONTEXT_OPENING}} (1-2 natural sentences referencing what {{COMPANY}} is building or solving).

{{RELEVANT_PROOF}} (1-2 conversational sentences weaving in the most relevant systems/PRs built from your profile matching {{COMPANY}}'s domain).

{{HUMAN_ASK}} (Brief, low-pressure question specific to their team).

Best,
{{CANDIDATE_NAME}}
{{CANDIDATE_PHONE}} | {{CANDIDATE_EMAIL}}
Resume: {{RESUME_DRIVE_URL}}
GitHub: {{GITHUB_URL}}
Portfolio: {{PORTFOLIO_URL}}
LinkedIn: {{LINKEDIN_URL}}
```

---

### Anti-AI & Anti-Spam Rules Enforced by Crafter Agent

1. **Concise Prose (60–90 words)**: Short 2–3 paragraph conversational note. Avoid rigid bulleted lists inside the email body.
2. **Zero Em-Dashes, Emojis, or Attached-Resume Boilerplate**: No `—`, no `📎`, no `"Tailored 1-page PDF resume is also attached"`, and no `"Links:"` / `"Verified Links:"` headers.
3. **Plain Human Language**: Uses natural contractions, avoids corporate buzzwords (*leverage*, *delve*, *streamline*, *thrilled*, *impressed by*), and never uses formulaic headings like *"Two things from my background that may be relevant:"*.
4. **Domain-Matched Proof**: Dynamically selects only the candidate achievements and projects that directly overlap with the company's stack.
5. **Silent PDF Attachment**: Compiled 1-page PDF resume is attached cleanly to the email without advertising a "tailored PDF" in the message text.
