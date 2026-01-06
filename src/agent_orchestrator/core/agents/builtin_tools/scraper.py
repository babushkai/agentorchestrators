"""Web scraping tool for extracting content from web pages."""

import re
from typing import Any, Literal
from urllib.parse import urljoin, urlparse

import httpx
import structlog
from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel, Field

from agent_orchestrator.core.agents.definition import ToolConfig
from agent_orchestrator.core.agents.tools import Tool

logger = structlog.get_logger(__name__)


class WebScrapingConfig(BaseModel):
    """Configuration for the web scraping tool."""

    blocked_domains: list[str] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1", "0.0.0.0", "169.254.169.254"],
        description="Blocked domains (security).",
    )
    max_content_length: int = Field(
        default=500000,  # 500KB
        description="Maximum content length to process.",
    )
    default_timeout: float = Field(
        default=30.0,
        description="Default request timeout.",
    )
    user_agent: str = Field(
        default="Mozilla/5.0 (compatible; AgentOrchestrator/1.0)",
        description="User agent for requests.",
    )


class WebScrapingTool(Tool):
    """Tool for extracting content from web pages."""

    def __init__(self, config: WebScrapingConfig | None = None) -> None:
        tool_config = ToolConfig(
            tool_id="builtin_web_scraping",
            name="web_scrape",
            description=(
                "Extract content from web pages. "
                "Can extract full page text, specific elements via CSS selectors, "
                "links, images, and metadata. "
                "Output formats: text, markdown, html."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL to scrape",
                    },
                    "selectors": {
                        "type": "object",
                        "description": (
                            "CSS selectors to extract specific elements. "
                            "Keys are names, values are CSS selectors. "
                            "Example: {'title': 'h1', 'content': '.article-body'}"
                        ),
                        "additionalProperties": {"type": "string"},
                    },
                    "extract_links": {
                        "type": "boolean",
                        "description": "Extract all links from the page",
                        "default": False,
                    },
                    "extract_images": {
                        "type": "boolean",
                        "description": "Extract all image URLs from the page",
                        "default": False,
                    },
                    "output_format": {
                        "type": "string",
                        "enum": ["text", "markdown", "html"],
                        "description": "Output format for extracted content",
                        "default": "text",
                    },
                    "max_length": {
                        "type": "integer",
                        "description": "Maximum output length in characters",
                    },
                },
                "required": ["url"],
            },
            timeout_seconds=60.0,
        )
        super().__init__(tool_config)
        self._scrape_config = config or WebScrapingConfig()

    def _validate_url(self, url: str) -> str | None:
        """Validate URL against blocked domains."""
        try:
            parsed = urlparse(url)
            domain = parsed.hostname or ""

            for blocked in self._scrape_config.blocked_domains:
                if domain == blocked or domain.endswith(f".{blocked}"):
                    return f"Domain '{domain}' is blocked"

            if parsed.scheme not in ("http", "https"):
                return f"Invalid scheme: {parsed.scheme}"

            return None
        except Exception as e:
            return f"Invalid URL: {e}"

    async def execute(
        self,
        url: str,
        selectors: dict[str, str] | None = None,
        extract_links: bool = False,
        extract_images: bool = False,
        output_format: Literal["text", "markdown", "html"] = "text",
        max_length: int | None = None,
    ) -> dict[str, Any]:
        """Execute web scraping."""
        # Validate URL
        validation_error = self._validate_url(url)
        if validation_error:
            return {"error": validation_error}

        try:
            # Fetch page
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={"User-Agent": self._scrape_config.user_agent},
                    timeout=self._scrape_config.default_timeout,
                    follow_redirects=True,
                )
                response.raise_for_status()

            # Check content type
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                return {
                    "error": f"Unsupported content type: {content_type}",
                    "url": str(response.url),
                }

            # Check content length
            html = response.text
            if len(html) > self._scrape_config.max_content_length:
                html = html[: self._scrape_config.max_content_length]
                truncated = True
            else:
                truncated = False

            # Parse HTML
            soup = BeautifulSoup(html, "lxml")

            result: dict[str, Any] = {
                "url": str(response.url),
                "status_code": response.status_code,
                "truncated": truncated,
            }

            # Extract metadata
            result["metadata"] = self._extract_metadata(soup)

            # Extract specific selectors
            if selectors:
                result["selected"] = self._extract_selectors(soup, selectors, output_format)

            # Extract main content
            result["content"] = self._extract_main_content(soup, output_format, max_length)

            # Extract links
            if extract_links:
                result["links"] = self._extract_links(soup, str(response.url))

            # Extract images
            if extract_images:
                result["images"] = self._extract_images(soup, str(response.url))

            logger.info(
                "Web scraping completed",
                url=url,
                content_length=len(result.get("content", "")),
            )

            return result

        except httpx.TimeoutException:
            return {"error": f"Request timed out", "url": url}
        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP error: {e.response.status_code}", "url": url}
        except httpx.RequestError as e:
            return {"error": f"Request failed: {e}", "url": url}
        except Exception as e:
            logger.warning("Web scraping failed", url=url, error=str(e))
            return {"error": f"Scraping failed: {e}", "url": url}

    def _extract_metadata(self, soup: BeautifulSoup) -> dict[str, str | None]:
        """Extract page metadata."""
        metadata: dict[str, str | None] = {}

        # Title
        title_tag = soup.find("title")
        metadata["title"] = title_tag.get_text(strip=True) if title_tag else None

        # Meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and isinstance(meta_desc, Tag):
            metadata["description"] = meta_desc.get("content")

        # Meta keywords
        meta_keywords = soup.find("meta", attrs={"name": "keywords"})
        if meta_keywords and isinstance(meta_keywords, Tag):
            metadata["keywords"] = meta_keywords.get("content")

        # Open Graph
        og_title = soup.find("meta", property="og:title")
        if og_title and isinstance(og_title, Tag):
            metadata["og_title"] = og_title.get("content")

        og_desc = soup.find("meta", property="og:description")
        if og_desc and isinstance(og_desc, Tag):
            metadata["og_description"] = og_desc.get("content")

        return metadata

    def _extract_selectors(
        self,
        soup: BeautifulSoup,
        selectors: dict[str, str],
        output_format: str,
    ) -> dict[str, str | list[str] | None]:
        """Extract content using CSS selectors."""
        result: dict[str, str | list[str] | None] = {}

        for name, selector in selectors.items():
            elements = soup.select(selector)

            if not elements:
                result[name] = None
            elif len(elements) == 1:
                result[name] = self._format_element(elements[0], output_format)
            else:
                result[name] = [self._format_element(el, output_format) for el in elements]

        return result

    def _format_element(self, element: Tag, output_format: str) -> str:
        """Format an element based on output format."""
        match output_format:
            case "html":
                return str(element)
            case "markdown":
                return self._html_to_markdown(element)
            case _:  # text
                return element.get_text(separator=" ", strip=True)

    def _extract_main_content(
        self,
        soup: BeautifulSoup,
        output_format: str,
        max_length: int | None,
    ) -> str:
        """Extract main page content."""
        # Remove script, style, and other non-content elements
        for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        # Try to find main content
        main_content = (
            soup.find("main")
            or soup.find("article")
            or soup.find("div", class_=re.compile(r"content|main|body", re.I))
            or soup.find("body")
        )

        if not main_content:
            return ""

        # Format content
        match output_format:
            case "html":
                content = str(main_content)
            case "markdown":
                content = self._html_to_markdown(main_content)
            case _:  # text
                content = main_content.get_text(separator="\n", strip=True)
                # Clean up excessive whitespace
                content = re.sub(r"\n{3,}", "\n\n", content)

        # Apply max length
        if max_length and len(content) > max_length:
            content = content[:max_length] + "..."

        return content

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> list[dict[str, str]]:
        """Extract all links from the page."""
        links = []

        for a in soup.find_all("a", href=True):
            href = a["href"]
            # Resolve relative URLs
            absolute_url = urljoin(base_url, href)

            links.append({
                "text": a.get_text(strip=True),
                "url": absolute_url,
            })

        return links[:100]  # Limit to 100 links

    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> list[dict[str, str | None]]:
        """Extract all images from the page."""
        images = []

        for img in soup.find_all("img"):
            src = img.get("src")
            if src:
                absolute_url = urljoin(base_url, src)
                images.append({
                    "src": absolute_url,
                    "alt": img.get("alt"),
                    "title": img.get("title"),
                })

        return images[:50]  # Limit to 50 images

    def _html_to_markdown(self, element: Tag) -> str:
        """Convert HTML element to simple markdown."""
        lines = []

        for child in element.descendants:
            if isinstance(child, str):
                text = child.strip()
                if text:
                    lines.append(text)
            elif child.name:
                match child.name:
                    case "h1":
                        lines.append(f"\n# {child.get_text(strip=True)}\n")
                    case "h2":
                        lines.append(f"\n## {child.get_text(strip=True)}\n")
                    case "h3":
                        lines.append(f"\n### {child.get_text(strip=True)}\n")
                    case "h4" | "h5" | "h6":
                        lines.append(f"\n#### {child.get_text(strip=True)}\n")
                    case "p":
                        lines.append(f"\n{child.get_text(strip=True)}\n")
                    case "li":
                        lines.append(f"- {child.get_text(strip=True)}")
                    case "a":
                        href = child.get("href", "")
                        text = child.get_text(strip=True)
                        if href and text:
                            lines.append(f"[{text}]({href})")
                    case "strong" | "b":
                        lines.append(f"**{child.get_text(strip=True)}**")
                    case "em" | "i":
                        lines.append(f"*{child.get_text(strip=True)}*")
                    case "code":
                        lines.append(f"`{child.get_text(strip=True)}`")
                    case "pre":
                        lines.append(f"\n```\n{child.get_text()}\n```\n")
                    case "br":
                        lines.append("\n")

        return " ".join(lines)
