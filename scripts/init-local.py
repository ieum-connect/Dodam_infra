"""Create a disposable local-only config with empty paid API credentials."""
import secrets
from pathlib import Path
from configure import ROOT, configure

target=ROOT/'.env.production.local'
if target.exists():
    raise SystemExit('Local config already exists; preserving it')
text=(ROOT/'.env.production.example').read_text()
changes={
    'COMPOSE_PROJECT_NAME':'dodam-deploy-check', 'RELEASE_TAG':'develop-20261107',
    'BIND_ADDRESS':'127.0.0.1','HTTP_PORT':'4280','HTTPS_PORT':'4443',
    'DOMAIN':'localhost','PUBLIC_ORIGIN':'http://localhost:4280',
    'NGINX_MODE':'local','COOKIE_SECURE':'false',
    'POSTGRES_PASSWORD':secrets.token_hex(32),'JWT_SECRET':secrets.token_hex(32),
    'AI_INTERNAL_TOKEN':secrets.token_hex(32),
    'EMBEDDING_API_KEY':'local-disabled-not-a-real-key',
    'LLM_BASE_URL':'http://127.0.0.1:9/v1','ISOLATE_NETWORK':'true',
}
text='\n'.join(k+'='+changes[k] if '=' in line and (k:=line.split('=',1)[0]) in changes else line for line in text.splitlines())+'\n'
target.write_text(text,encoding='utf-8')
target.chmod(0o600)
configure(target)
print('Local config created. No real API keys; outbound network isolated.')
