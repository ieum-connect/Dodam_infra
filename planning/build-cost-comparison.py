"""Offline budget model using the saved AWS public price rows. No AWS API calls."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
ec2_rows = json.loads((ROOT/'AmazonEC2-sydney-prices.json').read_text())['rows']
elb_rows = json.loads((ROOT/'AWSELB-sydney-prices.json').read_text())['rows']
rates = {r['Instance Type']:float(r['PricePerUnit']) for r in ec2_rows if r.get('Instance Type')}
gp3 = next(float(r['PricePerUnit']) for r in ec2_rows if r['Unit']=='GB-Mo')
alb = next(float(r['PricePerUnit']) for r in elb_rows if r.get('Product Family')=='Load Balancer-Application' and r['Unit']=='Hrs' and r.get('usageType')=='APS2-LoadBalancerUsage' and r.get('Location Type')=='AWS Region')
lcu = next(float(r['PricePerUnit']) for r in elb_rows if r.get('Product Family')=='Load Balancer-Application' and r['Unit']=='LCU-Hrs')
plans = [
    dict(name='단일 EC2 · Compose',instances={'t3.medium':1},disk=30,ips=1,alb=0,eks=0,note='서버 장애 자동 대체 없음'),
    dict(name='kubeadm · 기본형',instances={'t3.medium':3,'t3.small':1},disk=140,ips=6,alb=1,eks=0,note='관리 1 + 작업 2 + 데이터 1 / 관리·데이터 단일 지점'),
    dict(name='K3s · 관리 HA형',instances={'t3.medium':3,'t3.small':1},disk=140,ips=7,alb=1,eks=0,note='관리+작업 3 + 데이터 1 / 데이터 서버는 단일 지점'),
    dict(name='Sporty 사양 + ALB',instances={'t3.medium':1,'t3.large':3},disk=140,ips=6,alb=1,eks=0,note='과거 청구액 아님 / 진입점 비교를 위해 ALB 추가'),
    dict(name='EKS · 표준 지원',instances={'t3.medium':2,'t3.small':1},disk=110,ips=5,alb=1,eks=1,note='관리형 제어 영역 + 작업 2 + 데이터 1'),
]
for p in plans:
    p['computeHourly'] = sum(rates[k]*v for k,v in p['instances'].items())
    p['components'] = dict(ec2=p['computeHourly']*730,disk=p['disk']*gp3,
                           ipv4=p['ips']*.005*730,alb=p['alb']*(alb+lcu)*730,
                           eks=p['eks']*.1*730,allowance=10)
    p['monthly'] = sum(p['components'].values())
    p['daily'] = p['monthly']/730*24
    p['days100'] = 100/p['daily']
    p['days80'] = 80/p['daily']
assert abs(plans[2]['monthly']-208.13)<.01
assert plans[0]['days100']>plans[2]['days100']>plans[3]['days100']
model = dict(asOf='2026-11-07',region='ap-southeast-2',currency='USD',hoursPerMonth=730,
             gp3=gp3,ipv4=.005,alb=alb,lcu=lcu,eks=.1,rates=rates,plans=plans)
(ROOT/'cost-model.json').write_text(json.dumps(model,ensure_ascii=False,indent=2),encoding='utf-8')
html = '''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>도담 Kubernetes 구성·비용 비교</title>
<style>*{box-sizing:border-box}body{margin:0;background:#fcfafb;color:#292431;font:15px/1.7 system-ui,'Malgun Gothic',sans-serif}main{max-width:1200px;margin:auto;padding:36px 28px}h1{font-size:26px;margin:0 0 10px}h2{font-size:20px;margin:32px 0 12px}p{max-width:1000px}a{color:#a5355e}.muted,small{color:#706573}.summary{padding:20px 0;border-bottom:2px solid #b34f72}.summary strong{color:#a5355e}.controls{display:flex;flex-wrap:wrap;gap:18px;padding:20px 0}label{display:grid;gap:5px;font-size:13px}input{font:inherit;padding:9px;width:140px;border:1px solid #c8bcc3;border-radius:5px}input:focus{outline:2px solid #a5355e}.scroll{overflow:auto}table{width:100%;border-collapse:collapse;text-align:right;background:white;font-size:14px}th,td{padding:12px 10px;border-bottom:1px solid #e4dce0;white-space:nowrap}th{background:#f1e9ed;font-weight:600}th:first-child,td:first-child{text-align:left}tr.recommended td{background:#fff1f6}td small{display:block;font-size:11px;white-space:normal;max-width:290px}.diagram{border:1px solid #d8ced3;padding:20px;display:grid;gap:12px;background:white}.entry{text-align:center;padding:12px;background:#f4e9ee}.nodes{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.node{border:1px solid #d8ced3;padding:15px;text-align:center}.limits{border-left:3px solid #b34f72;padding:10px 18px;background:#fff1f6}li{margin:8px 0}button{font:inherit;padding:8px 15px;background:white;border:1px solid #d8ced3;border-radius:5px;cursor:pointer}.barrow{display:grid;grid-template-columns:170px 1fr 90px;align-items:center;gap:10px;font-size:13px;margin:9px 0}.track{height:17px;background:#eee7eb}.bar{height:17px;background:#8b7883}.bar.recommended{background:#b34f72}.axis{font-size:12px;color:#706573;margin-left:180px;display:flex;justify-content:space-between}code{font-size:13px;overflow-wrap:anywhere}@media(max-width:650px){main{padding:20px 14px}.nodes{grid-template-columns:1fr}.barrow{grid-template-columns:110px 1fr 70px}.axis{margin-left:120px}h1{font-size:23px}}@media print{.controls,button{display:none}main{max-width:none;padding:0}body{font-size:10pt}.scroll{overflow:visible}th,td{white-space:normal;font-size:9pt}h2{break-after:avoid}.diagram{break-inside:avoid}@page{size:A4 landscape;margin:14mm}}</style></head><body><main>
<p class="muted">DODAM · 팀 이음 · 시드니 · 2026-11-07 · 설계안 / AWS 미생성</p>
<h1>Kubernetes 구축과 100달러 운영 예산</h1><p class="limits"><strong>보류된 비교 자료 · 2026-11-08</strong><br>현재 배포는 EC2 1대 + Docker Compose로 확정되었습니다. 아래 Kubernetes 추천은 비교 당시의 안입니다. <a href="../EC2_SYDNEY.md">확정된 EC2 생성 안내</a></p>
<div class="summary"><strong>K3s 3노드 + 데이터 서버 1대</strong>를 추천안으로 비교했습니다. 관리 노드 한 대 장애를 견디는 구성을 목표로 하지만 DB·문서는 단일 서버입니다. 24시간 기준 약 <strong>$6.84/일</strong>, 100달러 전액 약 <strong>14.6일</strong>. 20달러를 남기면 약 <strong>11.7일</strong>입니다.</div>
<p><a href="KUBERNETES_PLAN.md">상세 구성·선행 코드 작업</a> · <a href="cost-model.json">계산 데이터</a> · <button onclick="window.print()">인쇄 / PDF 저장</button></p>
<h2>운영 조건을 바꿔 비교</h2><div class="controls">
<label>현재 크레딧 (USD)<input id="budget" type="number" min="0" value="100"></label>
<label>남겨둘 금액 (USD)<input id="reserve" type="number" min="0" value="20"></label>
<label>EC2 가동 시간 (시간/일)<input id="hours" type="number" min="1" max="24" value="24"></label>
<label>평균 ALB LCU<input id="lcu" type="number" min="0" step="0.1" value="1"></label>
<label>기타 사용 계획액 (USD/월)<input id="extra" type="number" min="0" value="10"></label>
<label>비교 기간 (일)<input id="period" type="number" min="1" value="14"></label></div>
<p class="muted">서버를 중지해도 디스크·보유 IPv4·ALB·EKS 관리료는 계속 계산합니다. 하루 8시간 운영은 16시간 서비스 중단을 뜻합니다. 중지/재시작 자동화는 아직 없습니다. 예산 알림은 비용을 강제로 차단하지 않습니다.</p>
<div class="scroll"><table><thead><tr><th>구성</th><th>일 비용 (USD)</th><th>730시간 환산월 (USD)</th><th>기간 비용 (USD)</th><th>전액 사용 (일)</th><th>예비금 제외 (일)</th></tr></thead><tbody id="comparison"></tbody></table></div>
<h2>구성별 하루 예상 비용</h2><p class="muted">세로: 구성 / 가로: USD·일. 입력 조건으로 환산한 비용입니다.</p><div id="bars"></div><div class="axis"><span>$0 / 일</span><span id="max"></span></div>
<h2>추천안 구성</h2><div class="diagram"><div class="entry">사용자 → 도메인 / ALB HTTPS (3 AZ, IPv4 최소 3개)</div><div class="nodes"><div class="node">AZ A · t3.medium<br>관리 + 앱 / etcd 1<br>gp3 30GiB</div><div class="node">AZ B · t3.medium<br>관리 + 앱 / etcd 2<br>gp3 30GiB</div><div class="node">AZ C · t3.medium<br>관리 + 앱 / etcd 3<br>gp3 30GiB</div></div><div class="entry">프론트·백·AI 복제본 분산 → 사설 네트워크 → 데이터 EC2 t3.small<br>PostgreSQL + pgvector / 문서 NFS · 루트 20GiB + 데이터 30GiB</div></div>
<p class="limits"><strong>한계:</strong> 데이터 서버 장애는 자동 전환되지 않습니다. Kubernetes 관리 쿼럼과 앱 노드 장애를 검증하는 구성이지, 서비스 전체 고가용성 보장은 아닙니다. DB 고가용성·공유 파일 관리형 서비스는 별도 비용과 구현이 필요합니다.</p>
<h2>왜 지금 바로 컨테이너만 복제하면 안 되나</h2><ul><li>현재 백엔드에 OAuth·HttpSession 사용 코드가 있습니다. 로그인 시작과 콜백이 다른 Pod로 갔을 때의 공유 세션을 검증해야 합니다.</li><li>백엔드와 AI가 같은 로컬 문서 폴더를 읽습니다. 서버별 hostPath 대신 공용 마운트를 연결해야 합니다.</li><li>복약·알림 스케줄러는 DB 잠금 코드가 있지만 다중 프로세스 중복 처리 테스트가 남아 있습니다.</li><li>노드 강제 중지 후 접속·데이터·세션을 측정하고, DB·문서 백업 복원은 따로 시험합니다. 실제 유료 AI 호출은 이 계획에 포함하지 않습니다.</li></ul>
<h2>24시간 기준 비용 구성 (USD / 730시간 환산월)</h2><div class="scroll"><table><thead><tr><th>구성</th><th>EC2</th><th>EBS</th><th>IPv4</th><th>ALB + 1 LCU</th><th>EKS</th><th>기타 계획액</th></tr></thead><tbody id="breakdown"></tbody></table></div>
<h2>견적 범위와 공식 단가</h2><p>t3.small $0.0264/h · t3.medium $0.0528/h · t3.large $0.1056/h · gp3 $0.096/GB-월 · IPv4 $0.005/주소·h · ALB $0.0252/h + $0.008/LCU·h · EKS 표준 지원 $0.10/h.</p>
<p>Linux 온디맨드, 시드니, 730시간 환산. 기타 월 10달러는 ECR·백업·소량 로그·AZ 전송 등 <strong>임의의 계획 여유분</strong>이며 정액 요금이 아닙니다. 세금·도메인·외부 AI·NAT·RDS/EFS·CPU 초과 비용·대규모 전송은 제외합니다. 사용량이 커지면 운영 기간이 줄어듭니다. 100달러는 공유 화면의 잔액이며 현재 잔액이나 모든 항목의 크레딧 충당을 검증한 것은 아닙니다.</p>
<ul><li><a href="https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/ap-southeast-2/index.csv">AWS EC2/EBS 시드니 공식 요금 데이터</a> · <a href="AmazonEC2-sydney-prices.json">조회한 행 보관본</a></li><li><a href="https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSELB/current/ap-southeast-2/index.csv">AWS ELB 시드니 공식 요금 데이터</a> · <a href="AWSELB-sydney-prices.json">조회한 행 보관본</a></li><li><a href="https://aws.amazon.com/vpc/pricing/">공인 IPv4</a> · <a href="https://aws.amazon.com/eks/pricing/">EKS</a> · <a href="https://docs.k3s.io/datastore/ha-embedded">K3s 3노드 쿼럼</a></li></ul>
<p>기존 EC2 한 대 생성 가이드는 Compose안입니다. Kubernetes를 선택하면 먼저 네 대의 역할·VPC·8 vCPU 한도·운영 기간을 확인하고 별도 구현 PR로 진행합니다. 이번 분석은 자원을 생성하지 않습니다.</p>
</main><script>const model=__MODEL__;
const money=n=>n.toFixed(2);const day=n=>n.toFixed(1);
function num(id,min=0,max=Infinity){return Math.min(max,Math.max(min,Number(document.getElementById(id).value)||0))}
function calculate(p,h,lcu,extra){const fixed=p.disk*model.gp3+p.ips*model.ipv4*730+p.alb*(model.alb+lcu*model.lcu)*730+p.eks*model.eks*730+extra;return p.computeHourly*h+fixed/730*24;}
function render(){const budget=num('budget'),reserve=num('reserve'),hours=num('hours',1,24),lc=num('lcu'),extra=num('extra'),period=num('period',1);const rows=model.plans.map(p=>({...p,daily:calculate(p,hours,lc,extra)}));
document.getElementById('comparison').innerHTML=rows.map((p,i)=>`<tr class="${i===2?'recommended':''}"><td><strong>${p.name}</strong><small>${p.note}</small></td><td>$${money(p.daily)}</td><td>$${money(p.daily*730/24)}</td><td>$${money(p.daily*period)}</td><td>${day(budget/p.daily)}</td><td>${day(Math.max(0,budget-reserve)/p.daily)}</td></tr>`).join('');
const max=Math.max(...rows.map(p=>p.daily));document.getElementById('max').textContent='$'+money(max)+' / 일';document.getElementById('bars').innerHTML=rows.map((p,i)=>`<div class="barrow"><span>${p.name}</span><div class="track"><div class="bar ${i===2?'recommended':''}" style="width:${p.daily/max*100}%"></div></div><span>$${money(p.daily)}</span></div>`).join('');}
document.getElementById('breakdown').innerHTML=model.plans.map(p=>`<tr><td>${p.name}</td>${Object.values(p.components).map(x=>`<td>$${money(x)}</td>`).join('')}</tr>`).join('');document.querySelectorAll('input').forEach(x=>x.addEventListener('input',render));render();
</script></body></html>'''
(ROOT/'도담_Kubernetes_비용비교.html').write_text(html.replace('__MODEL__',json.dumps(model,ensure_ascii=False)),encoding='utf-8')
print(json.dumps([{k:p[k] for k in ('name','monthly','daily','days100','days80')} for p in plans],ensure_ascii=False,indent=2))
