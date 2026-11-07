"""Local-only TLS syntax fixture and disposable database restore check."""
import datetime
import subprocess
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from configure import ROOT

dc=['docker','compose','--env-file','.env.production.local','-f','compose.production.yml']
def run(args,**kw):
    return subprocess.run(args,cwd=ROOT,check=True,**kw)
fixture=ROOT/'verification/tls-fixture'
fixture.mkdir(parents=True,exist_ok=True)
certdir=fixture/'certs/live/dodam.invalid'
certdir.mkdir(parents=True,exist_ok=True)
confdir=fixture/'conf'
confdir.mkdir(exist_ok=True)
key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'dodam.invalid')])
now=datetime.datetime.now(datetime.timezone.utc)
cert=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now).not_valid_after(now+datetime.timedelta(days=1)).sign(key,hashes.SHA256())
(certdir/'privkey.pem').write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
(certdir/'fullchain.pem').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
(confdir/'default.conf').write_text((ROOT/'nginx/https.conf').read_text().replace('__DOMAIN__','dodam.invalid'),encoding='utf-8')
run(dc+['run','--rm','--no-deps','-v',f'{(fixture/"certs").as_posix()}:/etc/letsencrypt:ro','-v',f'{confdir.as_posix()}:/etc/nginx/conf.d:ro','web','nginx','-t'])
print('PASS HTTPS template syntax with local fixture (not a trusted/public certificate)')
for script in ('deploy.sh','status.sh','backup.sh','renew.sh'):
    run(dc+['run','--rm','--no-deps','-v',f'{(ROOT/"scripts").as_posix()}:/check:ro','--entrypoint','bash','ai','-n','/check/'+script])
print('PASS Ubuntu shell script syntax')
backup=ROOT/'verification/restore-check.dump'
with backup.open('wb') as out:
    run(dc+['exec','-T','postgres','pg_dump','-U','dodam','-d','dodam','-Fc'],stdout=out)
restore_db='deploy_restore_'+now.strftime('%Y%m%d%H%M%S')
run(dc+['exec','-T','postgres','createdb','-U','dodam',restore_db])
with backup.open('rb') as inp:
    run(dc+['exec','-T','postgres','pg_restore','-U','dodam','-d',restore_db,'--no-owner','--exit-on-error'],stdin=inp)
run(dc+['exec','-T','postgres','psql','-U','dodam','-d',restore_db,'-c','SELECT count(*) FROM flyway_schema_history;'])
print('PASS DB dump and restore to separate test database:',restore_db)
