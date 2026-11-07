"""Render Nginx from a deliberately selected env file; never print secrets."""
import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read_env(path):
    return dict(line.split('=', 1) for line in Path(path).read_text(encoding='utf-8-sig').splitlines()
                if line.strip() and not line.lstrip().startswith('#') and '=' in line)

def configure(path):
    env = read_env(path)
    for key in ('POSTGRES_PASSWORD', 'JWT_SECRET', 'AI_INTERNAL_TOKEN'):
        if not re.fullmatch(r'[a-fA-F0-9]{64,}', env.get(key, '')):
            raise SystemExit(f'{key}: use at least 64 random hex characters, not example values')
    mode = env.get('NGINX_MODE', 'bootstrap')
    if mode not in ('local', 'bootstrap', 'https'):
        raise SystemExit('NGINX_MODE must be local, bootstrap or https')
    domain = env.get('DOMAIN', '')
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9.-]*', domain):
        raise SystemExit('DOMAIN must be a hostname')
    if mode != 'local':
        if '.' not in domain or 'replace' in domain or domain.endswith('.invalid'):
            raise SystemExit('Set the actual public domain before AWS deployment')
        if env.get('PUBLIC_ORIGIN') != 'https://' + domain or env.get('COOKIE_SECURE') != 'true':
            raise SystemExit('Production requires matching HTTPS origin and secure cookies')
    elif env.get('BIND_ADDRESS') != '127.0.0.1':
        raise SystemExit('HTTP local mode must bind to loopback')
    name = {'local':'http-local.conf','bootstrap':'http-bootstrap.conf','https':'https.conf'}[mode]
    target = ROOT / 'nginx/active'
    target.mkdir(exist_ok=True)
    (target/'default.conf').write_text((ROOT/'nginx'/name).read_text().replace('__DOMAIN__',domain),encoding='utf-8')
    print('Nginx rendered:',mode)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('env_file')
    configure(parser.parse_args().env_file)
