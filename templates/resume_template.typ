#set page(paper: "us-letter", margin: (x: 0.45in, y: 0.42in))
#set text(font: "Liberation Sans", size: 9pt)
#set par(justify: true, leading: 0.52em)

#align(center)[
  #text(size: 15pt, weight: "bold")[{{CANDIDATE_NAME}}] \
  #v(2pt)
  #text(size: 9.5pt, weight: "bold")[{{CANDIDATE_TITLE}}] \
  #v(2pt)
  {{CANDIDATE_CONTACT_LINE}}
]
#line(length: 100%, stroke: 0.5pt)

*RELEVANT HIGHLIGHTS FOR {{COMPANY_NAME}} ({{ANGLE_TITLE}})*
{{TAILORED_BULLETS}}

#v(3pt)
*EXPERIENCE*
{{EXPERIENCE_SECTION}}

#v(3pt)
*FLAGSHIP PROJECTS*
{{PROJECTS_SECTION}}

#v(3pt)
*TECHNICAL SKILLS*
{{SKILLS_SECTION}}

#v(3pt)
*EDUCATION*
{{EDUCATION_SECTION}}
