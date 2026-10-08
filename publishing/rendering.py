import bleach
import markdown


def render_body(body):
    """Permit basic Markdown, strip raw HTML scripts and unsafe URL schemes."""
    html = markdown.markdown(body, extensions=["fenced_code", "tables"])
    return bleach.clean(
        html,
        tags=[
            "p",
            "br",
            "strong",
            "em",
            "h2",
            "h3",
            "h4",
            "ul",
            "ol",
            "li",
            "a",
            "blockquote",
            "pre",
            "code",
            "hr",
            "table",
            "thead",
            "tbody",
            "tr",
            "th",
            "td",
        ],
        attributes={"a": ["href", "title"]},
        protocols=["http", "https", "mailto"],
        strip=True,
    )
