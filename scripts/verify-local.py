"""No AI inference calls: edge routing, health, DB, renderer and shared filesystem."""
import json
import re
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from configure import ROOT

DC=['docker','compose','--env-file','.env.production.local','-f','compose.production.yml']
results=[]
def command(name,args):
    p=subprocess.run(DC+args,cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    results.append({'check':name,'passed':p.returncode==0,'detail':(p.stdout+p.stderr).strip()})
    return p.stdout
def get(path):
    try:
        r=urllib.request.urlopen('http://localhost:4280'+path,timeout=10)
    except urllib.error.HTTPError as e:
        r=e
    return r.status,dict(r.headers),r.read().decode(errors='replace')
def http(name,path,status,header=None):
    code,headers,body=get(path)
    ok=code==status and (header is None or header in headers.get('Cache-Control',''))
    results.append({'check':name,'passed':ok,'status':code,'type':headers.get('Content-Type'),'cache':headers.get('Cache-Control')})
    return body

html=http('HTML','/index.html',200,'no-cache')
http('SPA reload','/calendar',200,'no-cache')
http('Missing SW is not HTML','/sw.js',404,'no-cache')
http('Missing manifest is not HTML','/manifest.webmanifest',404,'no-cache')
http('Missing asset','/assets/not-real.js',404)
http('Protected API','/api/not-real',401,'no-store')
http('Original file blocked','/local-documents/test.png',403)
http('Internal API blocked','/internal/welfare-programs/test',404)
http('Direct AI blocked','/api/v1/welfare/test',404)
body=http('Spring public config','/api/auth/config',200,'no-store')
results.append({'check':'Production demo login disabled','passed':json.loads(body).get('demoLogin') is False,'detail':body})
for asset in re.findall(r'(?:src|href)="(/assets/[^\"]+)"',html):
    http('Hashed asset cache',asset,200,'immutable')
command('Nginx syntax',['exec','-T','web','nginx','-t'])
command('AI health (no inference)',['exec','-T','ai','python','-c',"import urllib.request; assert urllib.request.urlopen('http://localhost:8006/health').status==200; print('ok')"])
command('DB migrations and vector',['exec','-T','postgres','psql','-U','dodam','-d','dodam','-c',"SELECT count(*) AS migrations, bool_and(success) AS all_success FROM flyway_schema_history; SELECT extversion FROM pg_extension WHERE extname='vector';"])
command('PDF renderer and shared write',['exec','-T','ai','python','-c',"import fitz; from pathlib import Path; d=fitz.open(); d.new_page(); assert d[0].get_pixmap().width>0; Path('/data/object-storage/.deployment-check').write_text('dodam-only'); print('PDF render and shared write ok')"])
command('Spring shared read',['exec','-T','backend','sh','-c',"test \"$(cat /data/object-storage/.deployment-check)\" = dodam-only && echo 'shared read ok'"])
command('Remove own probe',['exec','-T','ai','python','-c',"from pathlib import Path; Path('/data/object-storage/.deployment-check').unlink()"])
command('Image identities',['images','--format','json'])
out=ROOT/'verification'; out.mkdir(exist_ok=True)
(out/'local-checks.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
for item in results: print(('PASS' if item['passed'] else 'FAIL'),item['check'])
raise SystemExit(0 if all(x['passed'] for x in results) else 1)
