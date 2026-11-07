"""Create a private Sydney production config; never print generated secrets."""
import argparse
import os
import re
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def create_config(domain, tag, output):
    if not re.fullmatch(r'(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}', domain):
        raise ValueError('Use a real DNS hostname, without https:// or a path')
    if domain.endswith(('.invalid', '.example', '.localhost')) or domain in ('example.com', 'example.org', 'example.net'):
        raise ValueError('Use your actual domain, not a documentation example')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', tag):
        raise ValueError('Invalid image release tag')
    values = {
        'AWS_REGION': 'ap-southeast-2', 'RELEASE_TAG': tag,
        'DOMAIN': domain, 'PUBLIC_ORIGIN': 'https://' + domain,
        'BIND_ADDRESS': '0.0.0.0', 'HTTP_PORT': '80', 'HTTPS_PORT': '443',
        'NGINX_MODE': 'bootstrap', 'COOKIE_SECURE': 'true',
        'ISOLATE_NETWORK': 'false',
        **{key: secrets.token_hex(32) for key in ('POSTGRES_PASSWORD', 'JWT_SECRET', 'AI_INTERNAL_TOKEN')},
    }
    lines = (ROOT / '.env.production.example').read_text(encoding='utf-8').splitlines()
    content = '\n'.join(line.split('=', 1)[0] + '=' + values[line.split('=', 1)[0]]
                        if '=' in line and line.split('=', 1)[0] in values else line for line in lines) + '\n'
    # O_EXCL prevents replacing a live DB password or signing key on reruns.
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
        stream.write(content)
    return Path(output)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--domain', required=True)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--output', type=Path, default=ROOT / '.env.production')
    args = parser.parse_args()
    try:
        create_config(args.domain, args.tag, args.output)
    except (ValueError, FileExistsError) as exc:
        parser.exit(1, f'Config not created: {exc}\n')
    print('Sydney config created; existing files are never overwritten. Add provider keys privately before deployment.')
