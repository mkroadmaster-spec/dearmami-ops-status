#!/usr/bin/env python
"""쉬운 채널 연결 가이드 만들기 — 같은 내용을 세 가지 형식으로.

  python scripts/build_guide.py [--repo owner/repo]
    → dist/guide/운영대시보드-채널연결-쉬운가이드.html   (복사 버튼 · 체크 표시 · 저장소 이름을 넣으면 링크가 자동 완성)
    → dist/guide/운영대시보드-채널연결-쉬운가이드.docx   (Word)
    → docs/EASY-CHANNEL-GUIDE.md                          (저장소·스킬에 넣는 글 형식)

내용은 scripts/guide_content.py 한 곳에서만 고친다.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import guide_content as G  # noqa: E402

NAME = "운영대시보드-채널연결-쉬운가이드"
SECTIONS = [G.SETUP, *G.CHANNELS]


def fill(text: str, repo: str | None) -> str:
    """{{REPO}} · {{DASH}} 채우기. repo 가 없으면 사람이 읽을 수 있는 자리표시."""
    if repo and "/" in repo:
        owner, name = repo.split("/", 1)
        return text.replace("{{REPO}}", repo).replace("{{DASH}}", f"https://{owner}.github.io/{name}/")
    return text.replace("{{REPO}}", "<내 저장소>").replace("{{DASH}}", "<대시보드 주소>")


# ---------------- Markdown ----------------
def to_md(repo: str | None) -> str:
    f = lambda t: fill(t, repo)  # noqa: E731
    o = [f"# {G.INTRO['title']}", "", G.INTRO["lead"], "",
         "> `<내 저장소>` 는 GitHub 저장소 이름(예: `my-company/shop-dashboard`), `<대시보드 주소>` 는 `https://<소유자>.github.io/<저장소>/` 입니다.",
         "> 같은 내용의 HTML 파일(복사 버튼 포함)과 Word 파일은 `python scripts/build_guide.py` 로 만듭니다.", "",
         "## 지켜야 할 것", ""] + [f"- {r}" for r in G.INTRO["rules"]] + [""]
    for b in G.BASICS:
        o += [f"## {b['title']}", ""]
        o += [f"{i}. {f(t)}" + (f"\n   {f(u)}" if u else "") for i, (t, u) in enumerate(b["steps"], 1)]
        o += [""] + [f"- {n}" for n in b["notes"]] + [""]
    o += ["## Claude 에게 보낼 말 (복사해서 쓰세요)", "", "| 언제 | 보낼 말 |", "|---|---|"] + [f"| {w} | `{f(s)}` |" for w, s in G.SAY] + [""]
    for s in SECTIONS:
        o += [f"## {s['title']}", "", f"- 걸리는 시간: {s['time']}", f"- 누가: {s['who']}", "- 준비물: " + " / ".join(s["need"]), "", "### 순서", ""]
        o += [f"{i}. {f(t)}" + (f"\n   {f(u)}" if u else "") for i, (t, u) in enumerate(s["steps"], 1)]
        if s["secrets"]:
            o += ["", "### GitHub 에 넣을 값", "", "| Name (그대로 복사) | Secret 에 넣을 값 |", "|---|---|"] + [f"| `{n}` | {v} |" for n, v in s["secrets"]]
        o += ["", f"### 다 했으면 Claude 에게", "", f"`{s['say']}`", "", "### 잘 됐는지 보는 법", "", s["check"], "", "### 막혔을 때", "", "| 이런 일이 생기면 | 이렇게 합니다 |", "|---|---|"]
        o += [f"| {a} | {f(b)} |" for a, b in s["trouble"]]
        o += [""] + [f"> {n}" for n in s.get("notes", [])] + [""]
    o += [f"## {G.AFTER['title']}", ""] + [f"- {x}" for x in G.AFTER["items"]] + [""]
    return "\n".join(o)


# ---------------- HTML ----------------
def rich(text: str) -> str:
    """**굵게** 와 `복사 값` 을 HTML 로. 링크 자리표시는 그대로 두고 화면에서 채운다."""
    t = html.escape(text, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    return re.sub(r"`([^`]+)`", lambda m: f'<span class="cp" data-v="{html.escape(m.group(1))}"><code>{m.group(1)}</code><button type="button">복사</button></span>', t)


def to_html(repo: str | None) -> str:
    def steps(items, sid):
        out = []
        for i, (t, u) in enumerate(items, 1):
            link = f'<div class="lk"><a href="{html.escape(u)}" target="_blank" rel="noopener" data-url="{html.escape(u)}">{html.escape(u)}</a></div>' if u else ""
            out.append(f'<li><label><input type="checkbox" data-k="{sid}-{i}"><span class="n">{i}</span><div class="st">{rich(t)}{link}</div></label></li>')
        return '<ol class="steps">' + "".join(out) + "</ol>"
    nav = "".join(f'<a href="#{s["id"]}">{html.escape(s["title"].split(" — ")[0])}</a>' for s in SECTIONS)
    body = [f'<header><h1>{html.escape(G.INTRO["title"])}</h1><p class="lead">{html.escape(G.INTRO["lead"])}</p>'
            '<div class="repo"><b>먼저 한 번만:</b> 내 GitHub 저장소 이름을 적으면 아래 모든 링크와 주소가 내 것으로 바뀝니다.'
            '<div class="row"><input id="repo" placeholder="예: my-company/shop-dashboard" autocomplete="off" spellcheck="false"><span id="repoMsg"></span></div>'
            '<div class="small">대시보드 주소: <code id="dash">(저장소 이름을 적으면 나옵니다)</code></div></div>'
            f'<nav>{nav}</nav></header>',
            '<section><h2>지켜야 할 것</h2><ul class="rules">' + "".join(f"<li>{rich(r)}</li>" for r in G.INTRO["rules"]) + "</ul></section>"]
    for bi, b in enumerate(G.BASICS):
        body.append(f'<section class="basic"><h2>{html.escape(b["title"])}</h2>{steps(b["steps"], f"b{bi}")}<ul class="notes">' + "".join(f"<li>{rich(n)}</li>" for n in b["notes"]) + "</ul></section>")
    body.append('<section><h2>Claude 에게 보낼 말</h2><p class="small">문장을 복사해 ○○ 부분만 바꿔 보내세요.</p><table><tr><th>언제</th><th>보낼 말</th></tr>'
                + "".join(f"<tr><td>{html.escape(w)}</td><td>{rich('`' + s + '`')}</td></tr>" for w, s in G.SAY) + "</table></section>")
    for s in SECTIONS:
        sec = [f'<section id="{s["id"]}" class="ch"><h2>{html.escape(s["title"])}</h2>',
               f'<div class="meta"><span>⏱ {html.escape(s["time"])}</span><span>👤 {html.escape(s["who"])}</span></div>',
               '<div class="need"><b>준비물</b><ul>' + "".join(f"<li>{rich(n)}</li>" for n in s["need"]) + "</ul></div>",
               "<h3>순서</h3>", steps(s["steps"], s["id"])]
        if s["secrets"]:
            sec.append('<h3>GitHub 에 넣을 값</h3><table class="sec"><tr><th>Name (그대로 복사)</th><th>Secret 에 넣을 값</th></tr>'
                       + "".join(f"<tr><td>{rich('`' + n + '`')}</td><td>{rich(v)}</td></tr>" for n, v in s["secrets"]) + "</table>")
        sec.append(f'<div class="say"><b>다 했으면 Claude 에게 보내세요</b>{rich("`" + s["say"] + "`")}</div>')
        sec.append(f'<h3>잘 됐는지 보는 법</h3><p>{rich(s["check"])}</p>')
        sec.append('<h3>막혔을 때</h3><table class="tr"><tr><th>이런 일이 생기면</th><th>이렇게 합니다</th></tr>' + "".join(f"<tr><td>{rich(a)}</td><td>{rich(b)}</td></tr>" for a, b in s["trouble"]) + "</table>")
        sec += [f'<p class="note">{rich(n)}</p>' for n in s.get("notes", [])]
        body.append("".join(sec) + "</section>")
    body.append(f'<section><h2>{html.escape(G.AFTER["title"])}</h2><ul class="rules">' + "".join(f"<li>{rich(x)}</li>" for x in G.AFTER["items"]) + "</ul></section>")
    css = """
:root{--bg:#f4f6f9;--card:#fff;--text:#0f172a;--t2:#475569;--t3:#8a94a6;--line:#e2e8f0;--blue:#2a78d6;--blue-bg:#eef4fd;--good:#0f8a3c;--warn-bg:#fff6e8;--code:#f1f5f9}
@media (prefers-color-scheme:dark){:root{--bg:#0f1420;--card:#171d2b;--text:#eef0f4;--t2:#b8bfcc;--t3:#8089a0;--line:#2b3242;--blue:#6aa8f0;--blue-bg:#1a2742;--good:#4ebd4e;--warn-bg:#3a2d14;--code:#232b3d}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:16px/1.7 'Pretendard','Malgun Gothic','Apple SD Gothic Neo',sans-serif}
main{max-width:860px;margin:0 auto;padding:16px}h1{font-size:26px;margin:8px 0}h2{font-size:20px;margin:0 0 10px}h3{font-size:15px;margin:18px 0 6px;color:var(--t2)}
header,section{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin-bottom:14px}.lead{color:var(--t2);margin:0 0 12px}
.repo{background:var(--blue-bg);border-radius:10px;padding:12px 14px}.repo .row{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:8px 0 4px}
.repo input{flex:1;min-width:220px;font:inherit;padding:9px 12px;border:2px solid var(--blue);border-radius:8px;background:var(--card);color:var(--text)}
nav{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}nav a{font-size:13px;text-decoration:none;color:var(--blue);border:1px solid var(--line);border-radius:999px;padding:3px 10px;background:var(--card)}
.small{font-size:13px;color:var(--t3)}code{background:var(--code);border-radius:6px;padding:2px 6px;font:14px/1.5 Consolas,'D2Coding',monospace;word-break:break-all}
.cp{display:inline-flex;flex-wrap:wrap;align-items:center;gap:4px;max-width:100%;vertical-align:middle;margin:2px 0}.cp code{min-width:0}main{overflow-wrap:anywhere}section,header{min-width:0}.cp button{font:inherit;font-size:12px;border:1px solid var(--blue);color:var(--blue);background:var(--card);border-radius:6px;padding:1px 8px;cursor:pointer;white-space:nowrap}
.cp button.ok{background:var(--good);border-color:var(--good);color:#fff}
ol.steps{list-style:none;padding:0;margin:0}ol.steps li{border-top:1px solid var(--line)}ol.steps li:first-child{border-top:0}
ol.steps label{display:flex;gap:10px;align-items:flex-start;padding:10px 0;cursor:pointer}ol.steps input{width:20px;height:20px;margin-top:4px;flex:none;accent-color:var(--good)}
.n{flex:none;width:26px;height:26px;border-radius:50%;background:var(--blue);color:#fff;font-weight:700;font-size:13px;display:grid;place-items:center;margin-top:1px}
.st{min-width:0}li.done .st{color:var(--t3)}li.done .n{background:var(--good)}.lk a{color:var(--blue);word-break:break-all;font-size:14px}
table{border-collapse:collapse;width:100%;font-size:14.5px;table-layout:fixed}table.sec th:first-child,table.sec td:first-child{width:44%}th,td{border:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top}th{background:var(--code);font-size:13px;color:var(--t2)}
.meta{display:flex;flex-wrap:wrap;gap:10px;font-size:13px;color:var(--t2);margin-bottom:8px}.need{background:var(--code);border-radius:10px;padding:8px 14px;font-size:14.5px}.need ul{margin:4px 0;padding-left:18px}
.say{background:var(--blue-bg);border-left:4px solid var(--blue);border-radius:8px;padding:10px 14px;margin:14px 0}.say b{display:block;font-size:13px;color:var(--t2)}
.note,.notes{background:var(--warn-bg);border-radius:8px;padding:8px 14px;font-size:14px}ul.notes{padding-left:30px}ul.rules{margin:0;padding-left:20px}
@media print{body{background:#fff}header,section{break-inside:avoid;border-color:#cbd5e1}.cp button,nav,.repo input,#repoMsg{display:none}}
"""
    js = """
const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const store={get:k=>{try{return localStorage.getItem(k)}catch(e){return null}},set:(k,v)=>{try{localStorage.setItem(k,v)}catch(e){}}};
// 저장소 이름을 적으면 모든 링크·주소가 채워진다
function applyRepo(){const v=$('#repo').value.trim().replace(/^https?:\\/\\/github\\.com\\//,'').replace(/\\/+$/,'');const ok=/^[\\w.-]+\\/[\\w.-]+$/.test(v);
  const dash=ok?`https://${v.split('/')[0]}.github.io/${v.split('/')[1]}/`:'<대시보드 주소>',repo=ok?v:'<내 저장소>';
  $('#dash').textContent=ok?dash:'(저장소 이름을 적으면 나옵니다)';$('#repoMsg').textContent=v&&!ok?'소유자/저장소 형식으로 적어 주세요':(ok?'✓ 적용됨':'');
  const f=t=>t.replaceAll('{{REPO}}',repo).replaceAll('{{DASH}}',dash);
  $$('a[data-url]').forEach(a=>{const u=f(a.dataset.url);a.textContent=u;if(ok||!a.dataset.url.includes('{{'))a.href=u;else a.removeAttribute('href');});
  $$('.cp').forEach(c=>{c.dataset.t??=c.dataset.v;const t=f(c.dataset.t);c.dataset.v=t;c.querySelector('code').textContent=t;});
  if(ok)store.set('guide:repo',v);}
$('#repo').value=store.get('guide:repo')||REPO_DEFAULT;$('#repo').oninput=applyRepo;applyRepo();
// 복사 버튼
document.addEventListener('click',async e=>{const b=e.target.closest('.cp button');if(!b)return;e.preventDefault();const v=b.parentElement.dataset.v;
  try{await navigator.clipboard.writeText(v)}catch(err){const t=document.createElement('textarea');t.value=v;document.body.appendChild(t);t.select();document.execCommand('copy');t.remove();}
  b.textContent='복사됨 ✓';b.classList.add('ok');setTimeout(()=>{b.textContent='복사';b.classList.remove('ok')},1500);});
// 한 단계씩 체크 (이 브라우저에 기억)
$$('ol.steps input').forEach(c=>{const k='guide:step:'+c.dataset.k;c.checked=store.get(k)==='1';c.closest('li').classList.toggle('done',c.checked);
  c.onchange=()=>{store.set(k,c.checked?'1':'0');c.closest('li').classList.toggle('done',c.checked);};});
"""
    return (f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{html.escape(G.INTRO["title"])}</title><style>{css}</style></head><body><main>{"".join(body)}'
            f'<p class="small" style="text-align:center">인쇄(Ctrl+P)하면 종이·PDF 로도 쓸 수 있습니다.</p></main>'
            f'<script>const REPO_DEFAULT={json.dumps(repo or "")};{js}</script></body></html>')


# ---------------- Word ----------------
def to_docx(repo: str | None, path: Path) -> None:
    from docx import Document
    from docx.enum.text import WD_BREAK
    from docx.oxml.ns import qn
    from docx.shared import Pt, RGBColor
    f = lambda t: fill(t, repo)  # noqa: E731
    doc = Document()
    st = doc.styles["Normal"]; st.font.name = "맑은 고딕"; st.font.size = Pt(10.5)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "맑은 고딕")

    def runs(par, text: str) -> None:
        for part in re.split(r"(\*\*.+?\*\*|`[^`]+`)", f(text)):
            if part.startswith("**"):
                par.add_run(part[2:-2]).bold = True
            elif part.startswith("`"):
                r = par.add_run(part[1:-1]); r.font.name = "Consolas"; r.font.color.rgb = RGBColor(0x1D, 0x4E, 0xD8); r.bold = True
            elif part:
                par.add_run(part)

    def table(head, rows) -> None:
        t = doc.add_table(rows=1, cols=len(head)); t.style = "Light Grid Accent 1"
        for i, h in enumerate(head):
            t.rows[0].cells[i].text = h
        for row in rows:
            cells = t.add_row().cells
            for i, v in enumerate(row):
                cells[i].text = ""; runs(cells[i].paragraphs[0], v)

    def steps(items) -> None:
        for i, (t, u) in enumerate(items, 1):
            p = doc.add_paragraph(); p.add_run(f"{i}. ").bold = True; runs(p, t)
            if u:
                q = doc.add_paragraph(); q.paragraph_format.left_indent = Pt(18); r = q.add_run(f(u)); r.font.name = "Consolas"; r.font.size = Pt(9); r.font.color.rgb = RGBColor(0x1D, 0x4E, 0xD8)

    doc.add_heading(G.INTRO["title"], 0)
    doc.add_paragraph(G.INTRO["lead"])
    p = doc.add_paragraph(); runs(p, "이 문서의 **<내 저장소>** 는 GitHub 저장소 이름(예: `my-company/shop-dashboard`), **<대시보드 주소>** 는 `https://<소유자>.github.io/<저장소>/` 입니다. "
                                     "파란 글자는 그대로 복사해서 붙여넣는 값입니다. 복사 버튼이 필요하면 같은 내용의 HTML 파일을 쓰세요.")
    doc.add_heading("지켜야 할 것", 1)
    for r in G.INTRO["rules"]:
        runs(doc.add_paragraph(style="List Bullet"), r)
    for b in G.BASICS:
        doc.add_heading(b["title"], 1); steps(b["steps"])
        for n in b["notes"]:
            runs(doc.add_paragraph(style="List Bullet"), n)
    doc.add_heading("Claude 에게 보낼 말", 1)
    table(["언제", "보낼 말 (복사해서 ○○ 만 바꾸기)"], [(w, f"`{s}`") for w, s in G.SAY])
    for s in SECTIONS:
        doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        doc.add_heading(s["title"], 1)
        runs(doc.add_paragraph(), f"**걸리는 시간** {s['time']}   **누가** {s['who']}")
        runs(doc.add_paragraph(), "**준비물** " + " / ".join(s["need"]))
        doc.add_heading("순서", 2); steps(s["steps"])
        if s["secrets"]:
            doc.add_heading("GitHub 에 넣을 값", 2); table(["Name (그대로 복사)", "Secret 에 넣을 값"], [(f"`{n}`", v) for n, v in s["secrets"]])
        doc.add_heading("다 했으면 Claude 에게 보내세요", 2); runs(doc.add_paragraph(), f"`{s['say']}`")
        doc.add_heading("잘 됐는지 보는 법", 2); runs(doc.add_paragraph(), s["check"])
        doc.add_heading("막혔을 때", 2); table(["이런 일이 생기면", "이렇게 합니다"], s["trouble"])
        for n in s.get("notes", []):
            runs(doc.add_paragraph(style="List Bullet"), n)
    doc.add_heading(G.AFTER["title"], 1)
    for x in G.AFTER["items"]:
        runs(doc.add_paragraph(style="List Bullet"), x)
    doc.save(path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=None, help="owner/repo — 넣으면 링크가 그 저장소로 채워진 파일이 나온다 (기본: 자리표시)")
    ap.add_argument("--out", default=str(ROOT / "dist" / "guide"))
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    (out / f"{NAME}.html").write_text(to_html(a.repo), encoding="utf-8")
    to_docx(a.repo, out / f"{NAME}.docx")
    (ROOT / "docs" / "EASY-CHANNEL-GUIDE.md").write_text(to_md(None), encoding="utf-8")
    for p in (out / f"{NAME}.html", out / f"{NAME}.docx", ROOT / "docs" / "EASY-CHANNEL-GUIDE.md"):
        print(f"✓ {p}  ({p.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
