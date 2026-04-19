"""HTML rendering helpers for the built-in admin UI."""

from __future__ import annotations

from html import escape
from typing import Any


def _layout(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      --bg: #f6f0e3;
      --panel: #fffdf8;
      --ink: #1f1a17;
      --muted: #6c6258;
      --line: #d9cdbd;
      --accent: #914f2d;
      --accent-soft: #f3dcc7;
      --good: #0f766e;
      --bad: #b42318;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      background:
        radial-gradient(circle at top left, #fff8ef, transparent 30%),
        linear-gradient(180deg, #f4ebdc 0%, var(--bg) 100%);
      color: var(--ink);
    }}
    .shell {{ max-width: 1100px; margin: 0 auto; padding: 32px 18px 64px; }}
    h1, h2, h3 {{ margin: 0 0 14px; line-height: 1.1; }}
    h1 {{ font-size: 2.2rem; }}
    h2 {{ font-size: 1.2rem; }}
    p, li, label, input, select, textarea, button {{ font-size: 0.98rem; }}
    .grid {{ display: grid; gap: 18px; grid-template-columns: repeat(auto-fit, minmax(290px, 1fr)); }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 18px;
      box-shadow: 0 14px 40px rgba(43, 24, 10, 0.06);
    }}
    .hero {{
      display: grid;
      gap: 18px;
      grid-template-columns: 1.4fr 1fr;
      margin-bottom: 22px;
    }}
    @media (max-width: 800px) {{ .hero {{ grid-template-columns: 1fr; }} }}
    input, select, textarea {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 10px 12px;
      background: white;
      margin: 6px 0 12px;
    }}
    button {{
      border: none;
      border-radius: 999px;
      padding: 11px 16px;
      background: var(--accent);
      color: white;
      cursor: pointer;
    }}
    button.secondary {{ background: #3b3b37; }}
    .muted {{ color: var(--muted); }}
    .flash {{ padding: 12px 14px; border-radius: 12px; margin-bottom: 18px; }}
    .flash.ok {{ background: #def7ec; color: var(--good); }}
    .flash.error {{ background: #fef3f2; color: var(--bad); }}
    .list {{ display: grid; gap: 10px; }}
    .item {{
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 12px;
      background: #fff;
    }}
    .pill {{
      display: inline-block;
      border-radius: 999px;
      padding: 2px 8px;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 0.85rem;
    }}
    pre {{
      white-space: pre-wrap;
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 12px;
      max-height: 380px;
      overflow: auto;
    }}
    .row {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
  </style>
</head>
<body>
  <div class="shell">{body}</div>
</body>
</html>"""


def render_setup_page(message: str | None = None) -> str:
    flash = f'<div class="flash error">{escape(message)}</div>' if message else ""
    body = f"""
    <div class="card" style="max-width:520px;margin:80px auto;">
      <h1>BookRAG Setup</h1>
      <p class="muted">Create the single admin account for this deployment.</p>
      {flash}
      <form method="post" action="/setup">
        <label>Username</label>
        <input name="username" value="admin" required>
        <label>Password</label>
        <input type="password" name="password" required>
        <button type="submit">Create Admin</button>
      </form>
    </div>
    """
    return _layout("BookRAG Setup", body)


def render_login_page(message: str | None = None) -> str:
    flash = f'<div class="flash error">{escape(message)}</div>' if message else ""
    body = f"""
    <div class="card" style="max-width:520px;margin:80px auto;">
      <h1>BookRAG Login</h1>
      <p class="muted">Sign in to manage books, providers, and chat sessions.</p>
      {flash}
      <form method="post" action="/login">
        <label>Username</label>
        <input name="username" required>
        <label>Password</label>
        <input type="password" name="password" required>
        <button type="submit">Sign In</button>
      </form>
    </div>
    """
    return _layout("BookRAG Login", body)


def render_dashboard(
    libraries: list[dict[str, Any]],
    providers: list[dict[str, Any]],
    books_by_library: dict[int, list[dict[str, Any]]],
    series_by_library: dict[int, list[dict[str, Any]]],
    jobs: list[dict[str, Any]],
    flash: str | None = None,
    answer: str | None = None,
) -> str:
    flash_html = ""
    if flash:
        flash_html = f'<div class="flash ok">{escape(flash)}</div>'

    library_cards = []
    for library in libraries:
        books = books_by_library.get(library["id"], [])
        series_items = series_by_library.get(library["id"], [])
        book_items = "".join(
            f"""
            <div class="item">
              <div class="row">
                <strong>{escape(book['title'])}</strong>
                <span class="pill">{escape(book['source_type'])}</span>
                <span class="pill">{escape(book['ingest_status'])}</span>
              </div>
              <div class="muted">Chapters: {book['chapter_count']} | Chunks: {book['chunk_count']}</div>
              <form method="post" action="/web/books/{book['id']}/ingest">
                <label>Embedding provider</label>
                <select name="embedding_provider_id" required>
                  {''.join(f"<option value='{provider['id']}'>{escape(provider['name'])}</option>" for provider in providers)}
                </select>
                <label>Embedding model</label>
                <input name="embedding_model" placeholder="text-embedding-3-small or gemini-embedding-001" required>
                <label>OCR mode</label>
                <select name="ocr_mode">
                  <option value="disabled">disabled</option>
                  <option value="auto">auto</option>
                  <option value="force">force</option>
                </select>
                <label>OCR provider</label>
                <select name="ocr_provider_id">
                  <option value="">none</option>
                  {''.join(f"<option value='{provider['id']}'>{escape(provider['name'])}</option>" for provider in providers)}
                </select>
                <label>OCR model</label>
                <input name="ocr_model" placeholder="Vision model if OCR is enabled">
                <div class="muted">OCR is intended for scanned PDFs, comics, and manga and may consume significant model credits.</div>
                <label><input type="checkbox" name="confirm_ocr_cost" value="yes"> I understand OCR may cost more</label>
                <div style="margin-top:12px;"><button type="submit">Index Book</button></div>
              </form>
            </div>
            """
            for book in books
        )
        series_items_html = "".join(
            f"""
            <div class='item'>
              <strong>{escape(series['name'])}</strong>
              <div class='muted'>Books: {len(series['books'])}</div>
              <div class='muted'>Current order: {escape(', '.join(str(book['id']) for book in series['books']) or 'none')}</div>
              <form method="post" action="/web/series/{series['id']}/reorder">
                <label>Ordered book ids</label>
                <input name="ordered_book_ids" placeholder="e.g. 3,5,7">
                <button type="submit" class="secondary">Save Order</button>
              </form>
            </div>
            """
            for series in series_items
        )
        library_cards.append(
            f"""
            <div class="card">
              <h2>{escape(library['name'])}</h2>
              <p class="muted">{escape(library.get('description') or '')}</p>
              <form method="post" enctype="multipart/form-data" action="/web/libraries/{library['id']}/books/upload">
                <label>Upload EPUB or PDF</label>
                <input type="file" name="file" accept=".epub,.pdf" required>
                <button type="submit">Upload Book</button>
              </form>
              <div class="list">{book_items or "<div class='item muted'>No books yet.</div>"}</div>
              <hr style="margin:18px 0;border:none;border-top:1px solid var(--line);">
              <form method="post" action="/web/series">
                <input type="hidden" name="library_id" value="{library['id']}">
                <label>Create series</label>
                <input name="name" placeholder="Series name" required>
                <button type="submit" class="secondary">Create Series</button>
              </form>
              <div class="list" style="margin-top:12px;">{series_items_html or "<div class='item muted'>No series yet.</div>"}</div>
            </div>
            """
        )

    provider_items = "".join(
        f"""
        <div class="item">
          <strong>{escape(provider['name'])}</strong>
          <div class="muted">{escape(provider['provider_type'])}</div>
          <div class="muted">Embedding default: {escape(provider.get('default_embedding_model') or '-')}</div>
          <div class="muted">Chat default: {escape(provider.get('default_chat_model') or '-')}</div>
        </div>
        """
        for provider in providers
    )

    job_items = "".join(
        f"<div class='item'><strong>Job #{job['id']}</strong><div class='muted'>{escape(job['status'])}: {escape(job.get('message') or '')}</div></div>"
        for job in jobs[:12]
    )

    body = f"""
    <div class="hero">
      <div class="card">
        <h1>BookRAG Application</h1>
        <p class="muted">Upload books, pick your own provider keys and models, chat with spoiler boundaries, and expose the same library over REST and MCP.</p>
      </div>
      <div class="card">
        <form method="post" action="/logout">
          <button type="submit" class="secondary">Log Out</button>
        </form>
      </div>
    </div>
    {flash_html}
    <div class="grid">
      <div class="card">
        <h2>Add Provider</h2>
        <form method="post" action="/web/providers">
          <label>Name</label>
          <input name="name" required>
          <label>Type</label>
          <select name="provider_type">
            <option value="ollama">ollama</option>
            <option value="openrouter">openrouter</option>
            <option value="nvidia_nim">nvidia_nim</option>
            <option value="openai_compatible">openai_compatible</option>
            <option value="anthropic">anthropic</option>
            <option value="google">google</option>
          </select>
          <label>API Key</label>
          <input name="api_key" required>
          <label>Base URL</label>
          <input name="base_url" placeholder="Optional custom base URL">
          <label>Default embedding model</label>
          <input name="default_embedding_model">
          <label>Default chat model</label>
          <input name="default_chat_model">
          <label>Default OCR model</label>
          <input name="default_ocr_model">
          <button type="submit">Save Provider</button>
        </form>
        <div class="list" style="margin-top:12px;">{provider_items or "<div class='item muted'>No providers yet.</div>"}</div>
      </div>
      <div class="card">
        <h2>Create Library</h2>
        <form method="post" action="/web/libraries">
          <label>Name</label>
          <input name="name" required>
          <label>Description</label>
          <textarea name="description"></textarea>
          <button type="submit">Create Library</button>
        </form>
        <div class="muted" style="margin-top:12px;">Books are indexed into the selected library and can be queried by REST, CLI, or MCP.</div>
      </div>
      <div class="card">
        <h2>Chat</h2>
        <form method="post" action="/web/chat">
          <label>Library</label>
          <select name="library_id">{''.join(f"<option value='{library['id']}'>{escape(library['name'])}</option>" for library in libraries)}</select>
          <label>Chat provider</label>
          <select name="chat_provider_id">{''.join(f"<option value='{provider['id']}'>{escape(provider['name'])}</option>" for provider in providers)}</select>
          <label>Chat model</label>
          <input name="chat_model" required>
          <label>Context mode</label>
          <select name="context_mode">
            <option value="">advanced spoiler_mode below</option>
            <option value="spoiler">spoiler</option>
            <option value="no_spoiler">no_spoiler</option>
          </select>
          <label>Spoiler mode</label>
          <select name="spoiler_mode">
            <option value="full_context">full_context</option>
            <option value="book_only">book_only</option>
            <option value="through_chapter">through_chapter</option>
            <option value="through_series_boundary">through_series_boundary</option>
          </select>
          <label>Active book id</label>
          <input name="active_book_id" placeholder="Optional">
          <label>Active chapter index</label>
          <input name="active_chapter_index" placeholder="Optional">
          <label>Question</label>
          <textarea name="question" required></textarea>
          <button type="submit">Ask</button>
        </form>
        {f"<pre>{escape(answer)}</pre>" if answer else "<div class='muted' style='margin-top:12px;'>Chat answers will appear here with citations.</div>"}
      </div>
    </div>
    <div class="grid" style="margin-top:18px;">
      {''.join(library_cards) or "<div class='card muted'>No libraries yet.</div>"}
    </div>
    <div class="card" style="margin-top:18px;">
      <h2>Recent Jobs</h2>
      <div class="list">{job_items or "<div class='item muted'>No jobs yet.</div>"}</div>
    </div>
    """
    return _layout("BookRAG", body)
