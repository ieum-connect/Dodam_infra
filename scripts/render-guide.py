"""Render the repository's deployment guide as a standalone, offline HTML file."""
from pathlib import Path
import html
import re

ROOT = Path(__file__).resolve().parents[1]

def inline(text):
    text = html.escape(text)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)

parts, nav, paragraph, block = [], [], [], []
in_code = False
list_open = False

def flush():
    if paragraph:
        parts.append('<p>' + inline(' '.join(paragraph)) + '</p>')
        paragraph.clear()

for line in (ROOT / 'DEPLOYMENT_GUIDE.md').read_text(encoding='utf-8').splitlines():
    if line.startswith('```'):
        flush()
        if list_open:
            parts.append('</ul>'); list_open = False
        if in_code:
            parts.append('<pre><code>' + html.escape('\n'.join(block)) + '</code></pre>')
            block.clear()
        in_code = not in_code
        continue
    if in_code:
        block.append(line); continue
    if not line.strip():
        flush()
        if list_open:
            parts.append('</ul>'); list_open = False
        continue
    if line.startswith('# '):
        parts.append('<h1>' + inline(line[2:]) + '</h1>'); continue
    if line.startswith('## '):
        flush()
        title = line[3:]; ident = 'step-' + title.split('.')[0]
        nav.append(f'<a href="#{ident}">{inline(title)}</a>')
        parts.append(f'<h2 id="{ident}">{inline(title)}</h2>'); continue
    match = re.match(r'^(?:- |\d+\. )(.*)', line)
    if match:
        flush()
        if not list_open:
            parts.append('<ul>'); list_open = True
        item = match[1]
        if item.startswith('[ ] '):
            parts.append('<li class="check"><label><input type="checkbox"> ' + inline(item[4:]) + '</label></li>')
        else:
            parts.append('<li>' + inline(item) + '</li>')
        continue
    paragraph.append(line)
flush()
if list_open:
    parts.append('</ul>')
assert not in_code, 'Unclosed code fence'

page = '''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>도담 AWS 배포 실행 가이드 | 팀 이음</title>
<style>
:root{color-scheme:light;--pink:#bd426b;--ink:#292332;--muted:#685e6b;--line:#eadce2}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:24px}
body{margin:0;background:#fffafb;color:var(--ink);font:16px/1.85 "Malgun Gothic",system-ui,sans-serif}
.layout{max-width:1430px;margin:auto;display:grid;grid-template-columns:260px minmax(0,1fr);gap:46px;padding:38px}
nav{position:sticky;top:24px;align-self:start;max-height:90vh;overflow:auto;font-size:13px}
nav b{display:block;color:var(--pink);letter-spacing:2px;margin-bottom:18px}nav a{display:block;padding:9px 12px;margin:3px 0;border-radius:7px;color:var(--muted);text-decoration:none}nav a:hover{background:#f6e5ed;color:var(--pink)}
main{min-width:0;background:#fff;border:1px solid var(--line);border-radius:18px;padding:48px 54px}
h1{font-size:34px;line-height:1.35;letter-spacing:-1.1px;margin:0 0 18px;color:var(--pink)}h2{font-size:23px;line-height:1.5;margin:55px 0 20px;padding-top:25px;border-top:1px solid var(--line);letter-spacing:-.6px}
p{margin:16px 0}a{color:#a52e59;text-underline-offset:3px}strong{font-weight:700}li{margin:9px 0}ul{padding-left:24px}code{font:13px/1.7 Consolas,monospace;background:#f8eff3;padding:2px 5px;border-radius:4px;overflow-wrap:anywhere}
pre{background:#242330;color:#f9f0f5;padding:22px;border-radius:10px;overflow-x:auto;max-width:100%;font-size:13px;line-height:1.75}pre code{background:none;padding:0;color:inherit;overflow-wrap:normal}
.check{list-style:none;margin-left:-22px}input{accent-color:var(--pink);width:16px;height:16px;vertical-align:middle}.notice{background:#fff1f6;border-left:4px solid var(--pink);padding:16px 20px;margin:25px 0}.tools{display:flex;gap:12px;margin-bottom:24px;flex-wrap:wrap}button{background:#fff;border:1px solid var(--line);padding:10px 16px;border-radius:8px;color:var(--ink);cursor:pointer;font:inherit;font-size:13px}
@media(max-width:900px){.layout{display:block;padding:18px}nav{position:static;max-height:none;margin-bottom:24px;display:flex;gap:4px;flex-wrap:wrap}nav b{width:100%;margin:0}nav a{padding:5px 8px}main{padding:26px 22px}h1{font-size:28px}h2{font-size:21px}}
@media print{body{background:white;font-size:10pt}.layout{display:block;padding:0}nav,.tools{display:none}main{border:0;padding:0}h2{break-after:avoid}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f5f5;color:#222;break-inside:avoid}a{color:inherit}h1{font-size:24pt}@page{size:A4;margin:18mm}}
</style></head><body><div class="layout"><nav><b>DODAM / DEPLOYMENT</b>''' + ''.join(nav) + '''</nav><main><div class="tools"><button onclick="window.print()">인쇄 / PDF 저장</button><button onclick="document.querySelectorAll('input[type=checkbox]').forEach(x=>x.checked=false)">체크 초기화</button><a href="DEPLOYMENT_GUIDE.md">편집용 원문</a></div><div class="notice">로컬 검증 완료 · AWS 배포 전<br>각 단계의 완료 기준을 확인하며 진행하세요. 체크는 이 화면에서만 유지됩니다.</div>''' + ''.join(parts) + '</main></div></body></html>'
(ROOT / '도담_배포_가이드라인.html').write_text(page, encoding='utf-8')
print('Rendered deployment guide:', len(nav), 'sections')
