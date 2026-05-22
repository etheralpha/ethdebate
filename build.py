#!/usr/bin/env python3
"""Build static debate pages from Markdown and YAML content.

Source folders live in content/<topic-slug>/ and must include:
  - topic.yaml
  - overview.md
  - potential-paths.yaml
  - arguments-for.yaml
  - arguments-against.yaml

Optional per-topic files:
  - key-resources.yaml

The generated site is written to public/.
"""

from __future__ import annotations

import html
import re
import shutil
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
CONTENT_DIR = ROOT / "content"
ASSETS_DIR = ROOT / "assets"
PUBLIC_DIR = ROOT / "public"
CONFIG_PATH = ROOT / "config.yaml"


def read_text(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def read_yaml(path: Path) -> Any:
	with path.open("r", encoding="utf-8") as f:
		return yaml.safe_load(f) or []


def attr(value: Any) -> str:
	return html.escape(str(value or ""), quote=True)


def inline_markdown(text: Any) -> str:
	"""Small, dependency-free inline Markdown renderer for trusted content files."""
	value = html.escape(str(text or ""), quote=False)

	# Inline code first, before emphasis.
	value = re.sub(r"`([^`]+)`", r"<code>\1</code>", value)

	# Links: [label](https://example.com)
	def link_repl(match: re.Match[str]) -> str:
		label = match.group(1)
		url = html.escape(match.group(2), quote=True)
		return f'<a href="{url}" target="_blank" rel="noopener noreferrer">{label}</a>'

	value = re.sub(r"\[([^\]]+)\]\(([^\s)]+)\)", link_repl, value)

	# Bold and emphasis.
	value = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", value)
	value = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", value)
	return value


def render_markdown(markdown_text: str) -> str:
	"""Render the simple Markdown used by this site into static HTML.

	Supports paragraphs, h1-h3 headings, unordered lists, links, bold, italics,
	inline code, and line breaks. For more advanced Markdown, add a Markdown
	package and replace this function.
	"""
	lines = markdown_text.replace("\r\n", "\n").split("\n")
	blocks: list[str] = []
	paragraph: list[str] = []
	list_items: list[str] = []

	def flush_paragraph() -> None:
		nonlocal paragraph
		if paragraph:
			body = "<br>".join(inline_markdown(line.strip()) for line in paragraph if line.strip())
			if body:
				blocks.append(f"<p>{body}</p>")
			paragraph = []

	def flush_list() -> None:
		nonlocal list_items
		if list_items:
			items = "".join(f"<li>{inline_markdown(item)}</li>" for item in list_items)
			blocks.append(f"<ul>{items}</ul>")
			list_items = []

	for raw_line in lines:
		line = raw_line.rstrip()
		stripped = line.strip()

		if not stripped:
			flush_paragraph()
			flush_list()
			continue

		heading = re.match(r"^(#{1,3})\s+(.+)$", stripped)
		if heading:
			flush_paragraph()
			flush_list()
			level = len(heading.group(1))
			blocks.append(f"<h{level}>{inline_markdown(heading.group(2))}</h{level}>")
			continue

		bullet = re.match(r"^[-*]\s+(.+)$", stripped)
		if bullet:
			flush_paragraph()
			list_items.append(bullet.group(1))
			continue

		flush_list()
		paragraph.append(stripped)

	flush_paragraph()
	flush_list()
	return "\n".join(blocks)


def render_markdown_list(items: list[Any]) -> str:
	if not items:
		return "<p>None listed.</p>"
	return "<ul>" + "".join(f"<li>{inline_markdown(item)}</li>" for item in items) + "</ul>"


def render_paths(paths: list[dict[str, Any]]) -> str:
	cards = []
	for path in paths:
		cards.append(
			f"""
			<article class="card path-card">
			  <h3>{inline_markdown(path.get('option', 'Untitled option'))}</h3>
			  <div class="markdown">{render_markdown(str(path.get('details', '')))}</div>
			</article>
			"""
		)
	return "\n".join(cards)


def render_resources(resources: list[dict[str, Any]]) -> str:
	if not resources:
		return ""

	cards = []
	for resource in resources:
		title = inline_markdown(resource.get("title", "Untitled resource"))
		url = attr(resource.get("url", "#"))
		meta = resource.get("meta") or ""
		description = resource.get("description") or ""
		meta_html = f'<p class="resource-meta">{inline_markdown(meta)}</p>' if meta else ""
		description_html = f'<p>{inline_markdown(description)}</p>' if description else ""
		cards.append(
			f"""
			<article class="card resource-card">
			  <a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a>
			  {meta_html}
			  {description_html}
			</article>
			"""
		)
	return '<div class="resource-grid">' + "\n".join(cards) + '</div>'


def topic_label(topic: dict[str, Any]) -> str:
	if topic.get("nav_label"):
		return str(topic["nav_label"])
	slug = str(topic.get("slug") or "").strip("/")
	return slug.replace("-", " ").replace("_", " ").title() or str(topic.get("title") or "Topic")


def render_topic_nav(topics: list[dict[str, Any]], active_slug: str) -> str:
	links = []
	for item in topics:
		slug = str(item.get("slug") or "").strip("/")
		if not slug:
			continue
		active = slug == active_slug
		aria_current = ' aria-current="page"' if active else ""
		class_name = "topic-link active" if active else "topic-link"
		links.append(f'<a class="{class_name}" href="/{attr(slug)}"{aria_current}>{inline_markdown(topic_label(item))}</a>')

	if not links:
		return ""

	return f"""
	<nav class="topic-switcher" aria-label="Debate topics">
	  <span>Topics</span>
	  <div>{''.join(links)}</div>
	</nav>
	"""


def render_arguments(arguments: list[dict[str, Any]]) -> str:
	items = []
	for entry in arguments:
		items.append(
			f"""
			<details>
			  <summary>{inline_markdown(entry.get('argument', 'Untitled argument'))}</summary>
			  <div class="detail-body">
				<div class="list-block claims">
				  <h4>Claims</h4>
				  {render_markdown_list(entry.get('claims') or [])}
				</div>
				<div class="list-block counterarguments">
				  <h4>Counterarguments</h4>
				  {render_markdown_list(entry.get('counterarguments') or [])}
				</div>
			  </div>
			</details>
			"""
		)
	return "\n".join(items)


def argument_randomizer_script() -> str:
    """Shuffle top-level argument topics on each page load.

    Only the direct <details> children inside each argument list are shuffled, so
    each argument's claims and counterarguments stay grouped together.
    """
    return """
  <script>
    (() => {
      const shuffle = (items) => {
        for (let i = items.length - 1; i > 0; i -= 1) {
          const j = Math.floor(Math.random() * (i + 1));
          [items[i], items[j]] = [items[j], items[i]];
        }
        return items;
      };

      document.querySelectorAll('.argument-list').forEach((list) => {
        const arguments = Array.from(list.children).filter((child) => child.tagName === 'DETAILS');
        if (arguments.length < 2) return;

        arguments.forEach((item) => item.removeAttribute('open'));
        shuffle(arguments).forEach((item, index) => {
          if (index === 0) item.setAttribute('open', '');
          list.appendChild(item);
        });
      });
    })();
  </script>
"""


def social_image_url(topic: dict[str, Any]) -> str:
	image = str(topic.get("social_image") or "/assets/img/cover.png")
	site_url = str(topic.get("site_url") or "").rstrip("/")
	if site_url and image.startswith("/"):
		return site_url + image
	return image


def canonical_url(topic: dict[str, Any]) -> str:
	site_url = str(topic.get("site_url") or "").rstrip("/")
	slug = str(topic.get("slug") or "").strip("/")
	return f"{site_url}/{slug}" if site_url and slug else ""


def merge_topic_defaults(topic: dict[str, Any]) -> dict[str, Any]:
	defaults = read_yaml(CONFIG_PATH) if CONFIG_PATH.exists() else {}
	if not isinstance(defaults, dict):
		defaults = {}
	if not isinstance(topic, dict):
		topic = {}
	return {**defaults, **topic}


def page_html(
	topic: dict[str, Any],
	topics: list[dict[str, Any]],
	overview_html: str,
	paths_html: str,
	resources_html: str,
	for_html: str,
	against_html: str,
	for_count: int,
	against_count: int,
) -> str:
	title = topic.get("title", "Debate")
	description = topic.get("description", "A neutral overview of debate paths and tradeoffs.")
	theme_color = topic.get("theme_color", "#f7f5f1")
	image = social_image_url(topic)
	canonical = canonical_url(topic)
	canonical_link = f'<link rel="canonical" href="{attr(canonical)}" />' if canonical else ""
	topic_nav = render_topic_nav(topics, str(topic.get("slug") or ""))
	source_files_link = str(topic.get("source_files_link") or "").strip()
	source_button = ""
	if source_files_link:
		source_button = f'<a class="source-button" href="{attr(source_files_link)}" target="_blank" rel="noopener noreferrer">{inline_markdown(topic.get("source_files_button_label", "View source files"))}</a>'

	resources_block = ""
	if resources_html:
		resources_block = f"""
	  <div class="resource-block">
		<div class="section-header small-header">
		  <h3>{inline_markdown(topic.get('resources_title', 'Key resources'))}</h3>
		  <p class="section-note">{inline_markdown(topic.get('resources_note', 'A starting point for readers who want to go deeper.'))}</p>
		</div>
		{resources_html}
	  </div>
		"""

	source_files_section = f"""
	<section id="resources" class="source-files-section" aria-labelledby="source-files-title">
	  <div class="source-panel card">
		<div class="section-header">
		  <h2 id="source-files-title">{inline_markdown(topic.get('source_files_title', 'Source files'))}</h2>
		  <p class="section-note">{inline_markdown(topic.get('source_files_note', 'The content on this page was generated with the help of AI from source files. You can download the source files to run your own analysis.'))}</p>
		</div>
		{source_button}
		{resources_block}
	  </div>
	</section>
	"""

	return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{attr(title)}</title>
  <meta name="description" content="{attr(description)}" />
  <meta property="og:title" content="{attr(title)}" />
  <meta property="og:description" content="{attr(description)}" />
  <meta property="og:type" content="website" />
  <meta property="og:image" content="{attr(image)}" />
  <meta property="og:image:type" content="image/png" />
	<meta property="og:image:width" content="1200" />
	<meta property="og:image:height" content="630" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:image" content="{attr(image)}" />
  <meta name="theme-color" content="{attr(theme_color)}" />
  {canonical_link}
  <link rel="icon" href="/assets/img/ethereum-favicon.svg" type="image/svg+xml" />
  <link rel="icon" href="/assets/img/favicon.ico" sizes="any" />
  <link rel="apple-touch-icon" href="/assets/img/apple-touch-icon.png" />
  <link rel="stylesheet" href="/assets/style.css" />
</head>
<body>
  <main class="site-shell">
	{topic_nav}
	<header class="hero">
	  <div class="eyebrow"><span class="dot"></span><span>{inline_markdown(topic.get('eyebrow', 'Debate'))}</span></div>
	  <h1>{inline_markdown(topic.get('hero_title', title))}</h1>
	  <div class="overview markdown">{overview_html}</div>
	  <nav class="section-jump-links" aria-label="Page sections">
		<a href="#paths">Paths</a>
		<a href="#arguments">Arguments</a>
		<a href="#resources">Resources</a>
	  </nav>
	</header>

	<section id="paths" aria-labelledby="paths-title">
	  <div class="section-header">
		<h2 id="paths-title">{inline_markdown(topic.get('paths_title', 'Potential paths'))}</h2>
		<p class="section-note">{inline_markdown(topic.get('paths_note', 'These are broad directions under discussion, not endorsements.'))}</p>
	  </div>
	  <div class="path-grid">{paths_html}</div>
	</section>

	<section id="arguments" aria-labelledby="arguments-title">
	  <div class="section-header">
		<h2 id="arguments-title">{inline_markdown(topic.get('arguments_title', 'Arguments for and against'))}</h2>
		<p class="section-note">{inline_markdown(topic.get('arguments_note', 'Open each item to compare the core claims with common counterarguments.'))}</p>
	  </div>
	  <div class="argument-grid">
		<article class="card argument-column" aria-labelledby="for-title">
		  <div class="column-title">
			<h3 id="for-title">{inline_markdown(topic.get('arguments_for_title', 'Arguments for'))}</h3>
			<span class="count-pill">{for_count} items</span>
		  </div>
		  <div class="argument-list">{for_html}</div>
		</article>

		<article class="card argument-column" aria-labelledby="against-title">
		  <div class="column-title">
			<h3 id="against-title">{inline_markdown(topic.get('arguments_against_title', 'Arguments against'))}</h3>
			<span class="count-pill">{against_count} items</span>
		  </div>
		  <div class="argument-list">{against_html}</div>
		</article>
	  </div>
	</section>

	{source_files_section}

	<footer>
	  <a class="github-link" href="https://github.com/etheralpha/ethdebate" target="_blank" rel="noopener noreferrer" aria-label="View source on GitHub">
		<svg viewBox="0 0 16 16" aria-hidden="true" width="35" height="35"><path fill="currentColor" d="M8 0C3.58 0 0 3.67 0 8.2c0 3.62 2.29 6.69 5.47 7.77.4.08.55-.18.55-.4 0-.2-.01-.86-.01-1.56-2.01.38-2.53-.5-2.69-.96-.09-.24-.48-.96-.82-1.15-.28-.16-.68-.55-.01-.56.63-.01 1.08.59 1.23.84.72 1.24 1.87.89 2.33.68.07-.53.28-.89.51-1.09-1.78-.21-3.64-.91-3.64-4.05 0-.89.31-1.63.82-2.2-.08-.21-.36-1.04.08-2.17 0 0 .67-.22 2.2.84A7.4 7.4 0 0 1 8 3.92c.68 0 1.36.09 2 .27 1.53-1.06 2.2-.84 2.2-.84.44 1.13.16 1.96.08 2.17.51.57.82 1.3.82 2.2 0 3.15-1.87 3.84-3.65 4.05.29.26.54.75.54 1.52 0 1.09-.01 1.97-.01 2.24 0 .22.15.48.55.4A8.12 8.12 0 0 0 16 8.2C16 3.67 12.42 0 8 0Z"/></svg>
	  </a>
	</footer>
  </main>
  {argument_randomizer_script()}
</body>
</html>
"""




def build_topic(topic_dir: Path, topics: list[dict[str, Any]]) -> str:
	topic = merge_topic_defaults(read_yaml(topic_dir / "topic.yaml"))
	slug = str(topic.get("slug") or topic_dir.name)
	topic["slug"] = slug

	overview_html = render_markdown(read_text(topic_dir / "overview.md"))
	paths = read_yaml(topic_dir / "potential-paths.yaml")
	arguments_for = read_yaml(topic_dir / "arguments-for.yaml")
	arguments_against = read_yaml(topic_dir / "arguments-against.yaml")
	resources_path = topic_dir / "key-resources.yaml"
	resources = read_yaml(resources_path) if resources_path.exists() else []

	html_out = page_html(
		topic=topic,
		topics=topics,
		overview_html=overview_html,
		paths_html=render_paths(paths),
		resources_html=render_resources(resources),
		for_html=render_arguments(arguments_for),
		against_html=render_arguments(arguments_against),
		for_count=len(arguments_for),
		against_count=len(arguments_against),
	)

	(PUBLIC_DIR / f"{slug}.html").write_text(html_out, encoding="utf-8")
	return slug


def main() -> None:
	if PUBLIC_DIR.exists():
		shutil.rmtree(PUBLIC_DIR)
	PUBLIC_DIR.mkdir(parents=True)

	if ASSETS_DIR.exists():
		shutil.copytree(ASSETS_DIR, PUBLIC_DIR / "assets")

	topic_dirs = [
		topic_dir
		for topic_dir in sorted(CONTENT_DIR.iterdir())
		if topic_dir.is_dir() and (topic_dir / "topic.yaml").exists()
	]

	if not topic_dirs:
		raise SystemExit("No topics found in content/<topic>/")

	topics = []
	for topic_dir in topic_dirs:
		topic = merge_topic_defaults(read_yaml(topic_dir / "topic.yaml"))
		topic["slug"] = str(topic.get("slug") or topic_dir.name)
		topics.append(topic)

	slugs = []
	for topic_dir in topic_dirs:
		slugs.append(build_topic(topic_dir, topics))

	# Small fallback for local static serving. Netlify redirects / to /issuance/.
	default_slug = "issuance" if "issuance" in slugs else slugs[0]
	(PUBLIC_DIR / "index.html").write_text(
		f'<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=/{attr(default_slug)}"><title>Redirecting…</title><p><a href="/{attr(default_slug)}">Continue to {html.escape(default_slug)}</a></p>',
		encoding="utf-8",
	)

	print(f"Built {len(slugs)} topic(s): {', '.join(slugs)}")


if __name__ == "__main__":
	main()
