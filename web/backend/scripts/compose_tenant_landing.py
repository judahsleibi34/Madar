"""Compose the Ibtikar tenant site through Madar's existing builder schema.

This is an explicit tenant-data migration. It resolves the target through
website_settings, preserves forms/workflows/roles and form-bearing pages, runs
the production publish validator, and uses the same atomic publish RPC as the
builder API. It never changes shared frontend components or global themes.
"""

from __future__ import annotations

import argparse
import copy
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from database import service_supabase
from routes.builder_routes import (
    publish_project_atomically,
    validate_publish_schema,
)


IBTIKAR = "https://ibtikar.ps"
MEDIA = {
    "logo": f"{IBTIKAR}/wp-content/uploads/2023/08/logo-2023-ibtikar.png",
    "hero": f"{IBTIKAR}/wp-content/uploads/2025/03/4783a8fe-f6da-4458-b474-186374e2afff.jpeg",
    "education": f"{IBTIKAR}/wp-content/uploads/2025/03/Copy-of-IMG_7594.jpg",
    "future": f"{IBTIKAR}/wp-content/uploads/2025/03/slider1.jpg",
    "collage": f"{IBTIKAR}/wp-content/uploads/2025/03/Ibtikar-Collage-1.jpg",
    "puppets": f"{IBTIKAR}/wp-content/uploads/2025/03/01784fb2-e758-4ed7-ad0b-1bd195549471-scaled.jpg",
    "story_bazaar": f"{IBTIKAR}/wp-content/uploads/2025/06/IMG_6941-1-1024x683.jpg",
    "story_sheleads": f"{IBTIKAR}/wp-content/uploads/2025/06/IMG_8932-1-1024x683.jpg",
    "story_resilience": f"{IBTIKAR}/wp-content/uploads/2025/03/IMG_4657-1-scaled.jpg",
}

DONOR_LOGOS = [
    ("Partner logo", f"{IBTIKAR}/wp-content/uploads/2025/03/Picture1-1-150x150.png"),
    ("GIZ", f"{IBTIKAR}/wp-content/uploads/2025/03/giz-2-150x150.jpg"),
    ("GIZ partner", f"{IBTIKAR}/wp-content/uploads/2025/03/giz2-150x150.jpg"),
    ("Kinder partner", f"{IBTIKAR}/wp-content/uploads/2025/03/small_thumb_Kinder_Logo_small-1-150x150.png"),
    ("SANAD", f"{IBTIKAR}/wp-content/uploads/2025/03/small_thumb_sanad-color-1-150x150.png"),
    ("Mercy Relief", f"{IBTIKAR}/wp-content/uploads/2025/03/logo-mercyrelief@2x-150x150.png"),
    ("Ministere partner", f"{IBTIKAR}/wp-content/uploads/2025/03/ministere-150x150.jpg"),
    ("EFG", f"{IBTIKAR}/wp-content/uploads/2025/03/efg-150x150.jpg"),
    ("Women Rights Online", f"{IBTIKAR}/wp-content/uploads/2025/03/Laboratory-women-right-online-LOGO-150x150.png"),
    ("Donor logo", f"{IBTIKAR}/wp-content/uploads/2025/07/Donor-150x150.png"),
]

THEME = {
    "mode": "light",
    "name": "Ibtikar Impact",
    "background": "#fffdf6",
    "surface": "#ffffff",
    "headerBackground": "#ffffff",
    "softSurface": "#edf6f7",
    "text": "#0a1425",
    "muted": "#4e5d66",
    "primary": "#f6de56",
    "accent": "#005571",
    "accentDark": "#003f54",
    "buttonText": "#ffffff",
    "border": "#d7e2e4",
    "radius": 22,
    "fontFamily": "Poppins",
}

BASE_STYLES = {
    "color": "var(--theme-text)",
    "backgroundColor": "",
    "borderRadius": "16px",
    "fontSize": "",
    "fontWeight": "",
    "textAlign": "left",
    "lineHeight": "",
    "alignSelf": "auto",
}


def ident(prefix: str, name: str) -> str:
    safe = "".join(character if character.isalnum() else "_" for character in name.lower())
    return f"ibtikar_{prefix}_{safe.strip('_')}"


def action(action_type: str = "none", **values: Any) -> dict[str, Any]:
    return {
        "type": action_type,
        "pageId": "",
        "sectionId": "",
        "formId": "",
        "url": "",
        "message": "",
        "status": "",
        **values,
    }


def element(kind: str, name: str, content: str = "", *, styles: dict[str, Any] | None = None, **extra: Any) -> dict[str, Any]:
    return {
        "id": ident("element", name),
        "type": kind,
        "name": name,
        "content": content,
        "mode": "auto",
        "connectedFormId": "",
        "action": action(),
        "styles": {**BASE_STYLES, **(styles or {})},
        **extra,
    }


def heading(name: str, content: str, level: int = 2, *, centered: bool = False, size: str | None = None) -> dict[str, Any]:
    sizes = {1: "60px", 2: "42px", 3: "28px"}
    return element(
        "heading",
        name,
        content,
        headingLevel=level,
        directWidthMode="auto",
        styles={
            "fontSize": size or sizes.get(level, "28px"),
            "fontWeight": "800",
            "lineHeight": "1.1",
            "textAlign": "center" if centered else "left",
            "alignSelf": "stretch" if centered else "auto",
        },
    )


def text(name: str, content: str, *, eyebrow: bool = False, centered: bool = False) -> dict[str, Any]:
    return element(
        "text",
        name,
        content,
        styles={
            "color": "var(--theme-primary)" if eyebrow else "var(--theme-text-soft)",
            "fontSize": "14px" if eyebrow else "17px",
            "fontWeight": "800" if eyebrow else "500",
            "letterSpacing": "0.08em" if eyebrow else "",
            "lineHeight": "1.7",
            "textAlign": "center" if centered else "left",
            "alignSelf": "stretch" if centered else "auto",
        },
    )


def button(name: str, label: str, *, page_id: str = "", url: str = "", secondary: bool = False) -> dict[str, Any]:
    target = action("goToPage", pageId=page_id) if page_id else action("openUrl", url=url, openInNewTab=True)
    return element(
        "button",
        name,
        label,
        action=target,
        backgroundColor="#FFFFFF" if secondary else "#005571",
        textColor="#005571" if secondary else "#FFFFFF",
        hoverBackgroundColor="#EDF6F7" if secondary else "#003F54",
        hoverTextColor="#003F54" if secondary else "#FFFFFF",
        borderColor="#005571",
        styles={
            "borderWidth": "2px" if secondary else "0px",
            "borderStyle": "solid",
            "borderRadius": "12px",
            "fontSize": "15px",
            "fontWeight": "800",
        },
    )


def image(name: str, source: str, *, radius: str = "24px", logo: bool = False) -> dict[str, Any]:
    return element(
        "image",
        name,
        source,
        styles={
            "borderRadius": radius,
            "alignSelf": "stretch",
            "objectFit": "contain" if logo else "cover",
            "height": "96px" if logo else "100%",
            "minHeight": "0px" if logo else "360px",
            "padding": "14px" if logo else "0px",
            "backgroundColor": "#ffffff" if logo else "",
        },
    )


def editorial_card(name: str, title: str, description: str, source: str, *, page_id: str = "", url: str = "", label: str = "Explore") -> dict[str, Any]:
    target = action("goToPage", pageId=page_id) if page_id else action("openUrl", url=url, openInNewTab=True)
    return element(
        "imageButton",
        name,
        source,
        imageButtonVariant="editorialCard",
        imageCardMediaWidth=200,
        cardIcon="none",
        cardTitle=title,
        cardDescription=description,
        cardActionLabel=label,
        action=target,
        styles={
            "backgroundColor": "var(--theme-surface)",
            "borderRadius": "20px",
            "alignSelf": "stretch",
        },
    )


def metric(name: str) -> dict[str, Any]:
    return element(
        "metric",
        name,
        metricColumns=4,
        metrics=[
            {"value": "5000+", "label": "Innovators Trained", "description": "Impactful reach"},
            {"value": "30+", "label": "Educational Programs", "description": "Programs and initiatives"},
            {"value": "10+", "label": "Global Partnerships", "description": "Community engagement"},
            {"value": "80%", "label": "Women Participants", "description": "Women empowerment"},
        ],
        styles={
            "backgroundColor": "var(--theme-surface)",
            "borderRadius": "22px",
            "alignSelf": "stretch",
            "metricTextColor": "#0a1425",
            "metricSymbolColor": "#005571",
        },
    )


def column(name: str, items: list[dict[str, Any]], align: str = "left") -> dict[str, Any]:
    return {"id": ident("column", name), "name": name, "layout": {"align": align}, "elements": items}


def row(name: str, columns: list[dict[str, Any]], *, gap: str = "medium", align: str = "center") -> dict[str, Any]:
    return {
        "id": ident("row", name),
        "layout": {"columns": str(len(columns)), "align": align, "gap": gap},
        "columns": columns,
    }


def section(name: str, rows: list[dict[str, Any]], *, background: str = "var(--theme-surface)", width: str = "large", min_height: int = 0) -> dict[str, Any]:
    return {
        "id": ident("section", name),
        "name": name,
        "mode": "auto",
        "layout": {
            "width": width,
            "paddingY": "large",
            "background": background,
            "minHeight": min_height,
            "fullBleed": width == "full",
        },
        "rows": rows,
        "freeElements": [],
    }


def page(page_id: str, name: str, slug: str, sections: list[dict[str, Any]], *, default: bool = False, navigation_label: str | None = None) -> dict[str, Any]:
    return {
        "id": page_id,
        "name": name,
        "navigationLabel": navigation_label or name,
        "slug": slug,
        "isDefault": default,
        "backgroundColor": "var(--theme-bg)",
        "visibility": "public",
        "showInNavigation": True,
        "pageType": "main",
        "sections": sections,
    }


def build_pages(home_id: str) -> list[dict[str, Any]]:
    about_id = ident("page", "about")
    programs_id = ident("page", "programs")
    puppets_id = ident("page", "palestinian_puppets")
    stories_id = ident("page", "stories")
    contact_id = ident("page", "contact")

    program_cards = [
        editorial_card(
            "program education",
            "Education, Civic Engagement & SDGs",
            "Experiential education that strengthens creativity, active citizenship and global responsibility.",
            MEDIA["education"],
            page_id=programs_id,
            label="Explore program",
        ),
        editorial_card(
            "program empowerment",
            "Empowerment, Social Innovation & Entrepreneurship",
            "Skills, mentoring and practical pathways that help people turn ideas into solutions for their communities.",
            MEDIA["hero"],
            page_id=programs_id,
            label="Explore program",
        ),
        editorial_card(
            "program advocacy",
            "Advocacy for Inclusive Ecosystems",
            "Advocacy for educational and entrepreneurial systems that are fair, accessible and open to all Palestinians.",
            MEDIA["future"],
            page_id=programs_id,
            label="Explore program",
        ),
    ]

    story_cards = [
        editorial_card(
            "story bazaars",
            "Open-Air Bazaars Empower Refugee Women",
            "Five community markets brought women-led businesses together to sell, connect and grow.",
            MEDIA["story_bazaar"],
            url=f"{IBTIKAR}/ibtikar-organizes-vibrant-open-air-bazaar-to-empower-refugee-women/",
            label="Read story",
        ),
        editorial_card(
            "story sheleads",
            "SHELEADS II: Empowerment in Action",
            "A sustained program supporting women entrepreneurs with practical skills, visibility and community connections.",
            MEDIA["story_sheleads"],
            url=f"{IBTIKAR}/news-events/",
            label="Read story",
        ),
        editorial_card(
            "story resilience",
            "Empowering Digital Resilience",
            "Community learning that helps women and young people participate online with greater safety and confidence.",
            MEDIA["story_resilience"],
            url=f"{IBTIKAR}/news-events/",
            label="Read story",
        ),
    ]

    home_sections = [
        section(
            "home hero",
            [row("hero split", [
                column("hero copy", [
                    text("hero eyebrow", "PALESTINIAN IDEAS. LASTING CHANGE.", eyebrow=True),
                    heading("hero title", "Empowering Changemakers", 1),
                    text("hero body", "Ibtikar connects, inspires, trains and mentors innovators creating positive change through education, entrepreneurship and social innovation."),
                    button("hero programs", "Explore Our Programs", page_id=programs_id),
                    button("hero about", "About Ibtikar", page_id=about_id, secondary=True),
                ]),
                column("hero image", [image("Ibtikar changemakers", MEDIA["hero"], radius="30px")]),
            ], gap="large")],
            background="var(--theme-bg)",
            min_height=620,
        ),
        section(
            "impact numbers",
            [
                row("impact heading", [column("impact heading copy", [
                    text("impact eyebrow", "OUR IMPACT", eyebrow=True, centered=True),
                    heading("impact title", "Change measured in people and possibility", 2, centered=True),
                ])]),
                row("impact metrics", [column("impact metric group", [metric("Ibtikar impact metrics")])]),
            ],
            background="#f6de56",
        ),
        section(
            "about mission",
            [row("about split", [
                column("about image", [image("Ibtikar community collage", MEDIA["collage"])]),
                column("about copy", [
                    text("about eyebrow", "ROOTED IN BETHLEHEM", eyebrow=True),
                    heading("about title", "Innovation in service of community", 2),
                    text("about body", "Founded in Bethlehem in 2019, Ibtikar is a Palestinian NGO helping youth, women, teachers and students use creativity to respond to social challenges and build a more inclusive society."),
                    button("about learn", "Our Story", page_id=about_id),
                ]),
            ], gap="large")],
            background="var(--theme-surface)",
        ),
        section(
            "programs",
            [
                row("program heading", [column("program heading copy", [
                    text("program eyebrow", "WHAT WE DO", eyebrow=True, centered=True),
                    heading("program title", "Programs that turn ideas into impact", 2, centered=True),
                    text("program intro", "Three connected areas of work bring education, entrepreneurship and advocacy together.", centered=True),
                ])]),
                row("program cards", [column(f"program card {index}", [card]) for index, card in enumerate(program_cards, 1)], gap="medium", align="stretch"),
            ],
            background="var(--theme-bg-soft)",
        ),
        section(
            "community impact",
            [row("community split", [
                column("community copy", [
                    text("community eyebrow", "LEARNING THAT MOVES", eyebrow=True),
                    heading("community title", "Education becomes powerful when people can use it", 2),
                    text("community body", "Ibtikar creates practical learning experiences where young people, women and educators can experiment, collaborate and develop solutions grounded in Palestinian communities."),
                    button("community programs", "See the Programs", page_id=programs_id),
                ]),
                column("community image", [image("Ibtikar education activity", MEDIA["education"], radius="30px")]),
            ], gap="large")],
            background="var(--theme-surface)",
        ),
        section(
            "palestinian puppets feature",
            [row("puppets split", [
                column("puppets image", [image("Palestinian Puppets", MEDIA["puppets"], radius="30px")]),
                column("puppets copy", [
                    text("puppets eyebrow", "HERITAGE IN EVERY THREAD", eyebrow=True),
                    heading("puppets title", "Palestinian stories, made by hand", 2),
                    text("puppets body", "Palestinian Puppets brings heritage, embroidery and storytelling together—preserving cultural memory while creating economic opportunities for women in marginalized communities."),
                    button("puppets discover", "Discover Palestinian Puppets", page_id=puppets_id),
                ]),
            ], gap="large")],
            background="var(--theme-bg-soft)",
        ),
        section(
            "partners",
            [
                row("partner heading", [column("partner heading copy", [
                    text("partner eyebrow", "TRUSTED COLLABORATION", eyebrow=True, centered=True),
                    heading("partner title", "Donors and partners", 2, centered=True),
                    text("partner intro", "Organizations working alongside Ibtikar to strengthen learning, livelihoods and inclusive communities.", centered=True),
                ])]),
                row("partner logos one", [column(f"partner logo column {index}", [image(name, url, radius="14px", logo=True)]) for index, (name, url) in enumerate(DONOR_LOGOS[:5], 1)], gap="small"),
                row("partner logos two", [column(f"partner logo column {index + 5}", [image(name, url, radius="14px", logo=True)]) for index, (name, url) in enumerate(DONOR_LOGOS[5:], 1)], gap="small"),
            ],
            background="var(--theme-surface)",
        ),
        section(
            "impact stories",
            [
                row("story heading", [column("story heading copy", [
                    text("story eyebrow", "IMPACT IN ACTION", eyebrow=True, centered=True),
                    heading("story title", "Stories from the community", 2, centered=True),
                ])]),
                row("story cards", [column(f"story card {index}", [card]) for index, card in enumerate(story_cards, 1)], gap="medium", align="stretch"),
                row("story action", [column("story action column", [button("all stories", "View All Stories", page_id=stories_id)], align="center")]),
            ],
            background="var(--theme-bg-soft)",
        ),
        section(
            "participation cta",
            [row("cta copy", [column("cta column", [
                text("cta eyebrow", "INSPIRE. INNOVATE. EMPOWER.", eyebrow=True, centered=True),
                heading("cta title", "Be part of the change", 2, centered=True),
                text("cta body", "Learn, volunteer, collaborate or support work that helps Palestinian communities turn creativity into lasting impact.", centered=True),
                button("cta contact", "Get In Touch", page_id=contact_id),
            ], align="center")])],
            background="#f6de56",
        ),
    ]

    about_page = page(
        about_id,
        "About",
        "/about",
        [
            section("about page hero", [row("about page split", [
                column("about page copy", [
                    text("about page eyebrow", "ABOUT IBTIKAR", eyebrow=True),
                    heading("about page title", "Creativity can build a fairer future", 1, size="52px"),
                    text("about page intro", "Ibtikar is a Palestinian NGO established in 2019 in Bethlehem. Its programs connect education, social innovation and entrepreneurship so people can respond to community needs with confidence and care."),
                    button("about source", "Visit Ibtikar", url=f"{IBTIKAR}/about-ibtikar/"),
                ]),
                column("about page image", [image("Ibtikar people and programs", MEDIA["collage"], radius="30px")]),
            ], gap="large")], background="var(--theme-bg)"),
            section("mission vision", [
                row("mission heading", [column("mission heading copy", [heading("mission title", "Mission and vision", 2, centered=True)])]),
                row("mission cards", [
                    column("vision card", [heading("vision heading", "Vision of change", 3), text("vision copy", "Empower the next generation to address society's needs and improve well-being for all.")]),
                    column("mission card", [heading("mission heading card", "Mission", 3), text("mission copy", "Connect, inspire, train and mentor change agents who strengthen Palestinian entrepreneurship and education in line with the Sustainable Development Goals.")]),
                ], gap="large", align="stretch"),
            ], background="var(--theme-bg-soft)"),
        ],
    )

    programs_page = page(
        programs_id,
        "Programs",
        "/programs",
        [
            section("programs page hero", [row("programs page heading", [column("programs page heading copy", [
                text("programs page eyebrow", "PROGRAMS", eyebrow=True, centered=True),
                heading("programs page title", "Learning, enterprise and advocacy in one ecosystem", 1, centered=True, size="52px"),
                text("programs page intro", "Ibtikar equips people to learn by doing, create practical solutions and advocate for systems where everyone can participate.", centered=True),
            ])])], background="var(--theme-bg)"),
            section("program details", [row("program detail cards", [
                column("education detail", [heading("education detail title", "Education, Civic Engagement & SDGs", 3), text("education detail body", "Non-formal and experiential learning that strengthens creativity, civic participation and global citizenship."), button("education source", "Learn More", url=f"{IBTIKAR}/education-civic-engagement-sdgs/")]),
                column("empowerment detail", [heading("empowerment detail title", "Empowerment, Social Innovation & Entrepreneurship", 3), text("empowerment detail body", "Skills, mentoring and pre- and post-incubation support that help youth, women and children develop solutions to social challenges."), button("empowerment source", "Learn More", url=f"{IBTIKAR}/empowerment-social-innovation-entrepreneurship/")]),
                column("advocacy detail", [heading("advocacy detail title", "Advocacy for Inclusive Ecosystems", 3), text("advocacy detail body", "Work toward fair, accessible educational and entrepreneurial systems for Palestinians from every background."), button("advocacy source", "Learn More", url=f"{IBTIKAR}/")]),
            ], gap="medium", align="stretch")], background="var(--theme-bg-soft)"),
        ],
    )

    puppets_page = page(
        puppets_id,
        "Palestinian Puppets",
        "/palestinian-puppets",
        [
            section("puppets page hero", [row("puppets page split", [
                column("puppets page image", [image("Handmade Palestinian Puppets", MEDIA["puppets"], radius="30px")]),
                column("puppets page copy", [
                    text("puppets page eyebrow", "ART. HERITAGE. LIVELIHOODS.", eyebrow=True),
                    heading("puppets page title", "Stories that carry Palestine forward", 1, size="52px"),
                    text("puppets page body", "Each handmade puppet carries the embroidery and story of a Palestinian place. The initiative combines cultural education with paid opportunities for women artisans in marginalized communities."),
                    button("puppets source", "Explore the Initiative", url=f"{IBTIKAR}/the-palestinian-puppets/"),
                ]),
            ], gap="large")], background="var(--theme-bg)"),
            section("puppet narrative", [row("puppet narrative row", [column("puppet narrative copy", [
                heading("puppet narrative title", "Heritage becomes a living classroom", 2, centered=True),
                text("puppet narrative body", "Traditional embroidery, character-led storytelling and community craftsmanship help children connect with history while introducing Palestinian culture to audiences around the world.", centered=True),
            ], align="center")])], background="#f6de56"),
        ],
    )

    stories_page = page(
        stories_id,
        "Stories",
        "/stories",
        [
            section("stories page hero", [row("stories page heading", [column("stories page copy", [
                text("stories page eyebrow", "IMPACT IN ACTION", eyebrow=True, centered=True),
                heading("stories page title", "Community stories worth sharing", 1, centered=True, size="52px"),
                text("stories page intro", "A curated view of recent Ibtikar work in women's economic empowerment, community enterprise and digital resilience.", centered=True),
            ])])], background="var(--theme-bg)"),
            section("stories page cards", [row("stories page card row", [column(f"stories page card {index}", [{**copy.deepcopy(card), "id": ident("element", f"stories page {card['name']}") }]) for index, card in enumerate(story_cards, 1)], gap="medium", align="stretch")], background="var(--theme-bg-soft)"),
        ],
    )

    contact_page = page(
        contact_id,
        "Contact",
        "/contact",
        [section("contact page", [row("contact page split", [
            column("contact page copy", [
                text("contact page eyebrow", "CONNECT WITH IBTIKAR", eyebrow=True),
                heading("contact page title", "Let's create change together", 1, size="52px"),
                text("contact page body", "Interested in learning, volunteering, partnering or supporting Ibtikar's work? Use the organization's official contact page to start the conversation."),
                button("contact official", "Open Official Contact Page", url=f"{IBTIKAR}/contact-us/"),
            ]),
            column("contact page image", [image("Ibtikar community activity", MEDIA["future"], radius="30px")]),
        ], gap="large")], background="var(--theme-bg)")],
    )

    return [
        page(home_id, "Home", "/", home_sections, default=True),
        about_page,
        programs_page,
        puppets_page,
        stories_page,
        contact_page,
    ]


def page_contains_form(page_record: dict[str, Any]) -> bool:
    for section_record in page_record.get("sections") or []:
        elements = list(section_record.get("freeElements") or [])
        for row_record in section_record.get("rows") or []:
            for column_record in row_record.get("columns") or []:
                elements.extend(column_record.get("elements") or [])
        if any(isinstance(item, dict) and item.get("type") == "formBlock" for item in elements):
            return True
    return False


def compose(existing: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(existing)
    existing_pages = result.get("pages") or []
    existing_home = next((item for item in existing_pages if item.get("isDefault") or item.get("slug") == "/"), None)
    home_id = str((existing_home or {}).get("id") or ident("page", "home"))
    preserved_form_pages = [copy.deepcopy(item) for item in existing_pages if page_contains_form(item)]
    for form_page in preserved_form_pages:
        form_page["showInNavigation"] = False
        form_page["isDefault"] = False

    public_pages = build_pages(home_id)
    result.update({
        "name": "Ibtikar",
        "status": "published",
        "theme": THEME,
        "pages": [*public_pages, *preserved_form_pages],
        "defaultPageId": home_id,
        "activePageId": home_id,
        "siteChrome": {
            "logoWidth": 74,
            "showHeader": True,
            "showFooter": True,
            "brand": "Ibtikar",
            "logoUrl": MEDIA["logo"],
            "loadingImageUrl": MEDIA["logo"],
            "headerAlign": "center",
            "headerBackgroundColor": "#ffffff",
            "headerButtonLabel": "Get In Touch",
            "headerButtonHref": "Contact",
            "headerButtonPageId": ident("page", "contact"),
            "description": "A Palestinian NGO connecting education, social innovation and entrepreneurship to empower changemakers.",
            "contactEmail": "",
            "phone": "",
            "footerStoreName": "Ibtikar",
            "rights": "All rights reserved.",
            "footerShopTitle": "Explore",
            "footerShopLinks": "Home\nAbout\nPrograms\nPalestinian Puppets",
            "footerHelpTitle": "Connect",
            "footerHelpLinks": "Stories\nContact",
            "footerSocialLinks": "",
            "footerSocialItems": [
                {"label": "Facebook", "url": "https://www.facebook.com/ibtikar.palestine"},
                {"label": "Instagram", "url": "https://www.instagram.com/ibtikarpal/"},
                {"label": "YouTube", "url": "https://www.youtube.com/J8zJasBME0k"},
            ],
            "footerPaymentMethods": "",
            "footerPaymentItems": [],
            "footerLanguageLabel": "AR",
        },
    })
    result.setdefault("schema_version", 1)
    return result


def first(rows: list[dict[str, Any]], label: str) -> dict[str, Any]:
    if len(rows) != 1:
        raise RuntimeError(f"Expected exactly one {label}; found {len(rows)}")
    return rows[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-slug", required=True, help="Existing website_settings subdomain/path slug")
    parser.add_argument("--apply", action="store_true", help="Save the validated draft")
    parser.add_argument("--publish", action="store_true", help="Atomically publish after saving")
    arguments = parser.parse_args()

    settings_rows = (
        service_supabase.table("website_settings")
        .select("tenant_id,subdomain,standard_path_slug,published_project_id")
        .or_(f"subdomain.eq.{arguments.site_slug},standard_path_slug.eq.{arguments.site_slug}")
        .execute()
        .data
        or []
    )
    settings = first(settings_rows, "tenant website setting")
    project_id = str(settings.get("published_project_id") or "").strip()
    if not project_id:
        raise RuntimeError("The tenant has no published project binding")

    project_rows = (
        service_supabase.table("builder_projects")
        .select("*")
        .eq("id", project_id)
        .eq("tenant_id", settings["tenant_id"])
        .limit(1)
        .execute()
        .data
        or []
    )
    project_record = first(project_rows, "bound tenant project")
    draft = compose(project_record.get("draft_schema") or {})
    validated, schema_version = validate_publish_schema(
        draft,
        project_schema_version=project_record.get("schema_version"),
        tenant_id=int(settings["tenant_id"]),
    )
    form_page_count = sum(page_contains_form(item) for item in validated.get("pages") or [])
    print({
        "site": settings.get("standard_path_slug") or settings.get("subdomain"),
        "project": project_record.get("name"),
        "public_pages": [item.get("name") for item in (validated.get("pages") or []) if item.get("showInNavigation")],
        "preserved_form_pages": form_page_count,
        "forms": len(validated.get("forms") or []),
        "workflows": len(validated.get("workflows") or []),
        "schema_version": schema_version,
        "mode": "apply" if arguments.apply else "dry-run",
    })

    if not arguments.apply:
        return

    current_revision = int(project_record.get("draft_revision") or 0)
    next_revision = current_revision + 1
    save_response = (
        service_supabase.table("builder_projects")
        .update({
            "name": "Ibtikar",
            "slug": "ibtikar",
            "draft_schema": validated,
            "draft_revision": next_revision,
        })
        .eq("id", project_id)
        .eq("tenant_id", settings["tenant_id"])
        .eq("draft_revision", current_revision)
        .execute()
    )
    saved_rows = save_response.data or []
    if not saved_rows:
        raise RuntimeError("Draft revision changed before save; reload and retry")
    print({"saved": True, "draft_revision": next_revision})

    if not arguments.publish:
        return

    saved_project = saved_rows[0]
    published = publish_project_atomically(
        project={**saved_project, "draft_schema": validated},
        project_id=project_id,
        tenant_id=int(settings["tenant_id"]),
        expected_revision=next_revision,
        schema_version=schema_version,
        published_at=datetime.now(timezone.utc).isoformat(),
        require_active_entitlement=False,
    )
    print({
        "published": True,
        "published_version": published.get("published_version"),
        "published_revision": published.get("published_revision"),
    })


if __name__ == "__main__":
    main()
