import json,hashlib,os,sys,datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'verification/independent'
OUT.mkdir(exist_ok=True)
SLUG='alpha-greeting'
TASK=ROOT/'.yuzio/cadra/tasks/alpha-greeting.md'
INDEX=ROOT/'.yuzio/cohestra/handoffs/alpha-greeting/README.md'
RUN=ROOT/'.yuzio/cadra/runs/run-20261022-02.md'
def now(): return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
def sha(b): return hashlib.sha256(b).hexdigest()
def read(p):
    s=Path(p).read_text(); parts=s.split('---',2); assert not parts[0].strip(); return json.loads(parts[1]),parts[2]
def encode(d,b): return '---\n'+json.dumps(d,ensure_ascii=False,indent=2)+'\n---'+b

def atomic(p,d,b,old=None):
    p=Path(p); previous=p.read_text() if p.exists() else None
    if old is not None: assert previous==old
    text=encode(d,b); parsed=json.loads(text.split('---',2)[1]); assert parsed==d
    tmp=p.with_name(p.name+'.independent.tmp'); assert not tmp.exists(); tmp.write_text(text); assert tmp.read_text()==text
    assert (p.read_text() if p.exists() else None)==previous
    os.replace(tmp,p); assert p.read_text()==text
    with (OUT/'writes.jsonl').open('a') as f: f.write(json.dumps({'time':now(),'path':str(p),'before_sha256':sha(previous.encode()) if previous is not None else None,'after_sha256':sha(text.encode())},ensure_ascii=False)+'\n')

def prepare_index(label,contract,body,handoff):
    p=OUT/(label+'-pending.md'); assert not p.exists(); p.write_text(encode(contract,body))
    rec={'target':str(INDEX),'expected_old':INDEX.read_text(),'pending':str(p),'sha256':sha(p.read_bytes()),'handoff':str(handoff),'stage':contract['stage_result']['stage'],'round':contract['stage_result']['round'],'candidate':contract['candidate']}
    (OUT/(label+'-input.json')).write_text(json.dumps(rec,ensure_ascii=False,indent=2))

def validate_index(label):
    rec=json.loads((OUT/(label+'-input.json')).read_text()); p=Path(rec['pending']); assert sha(p.read_bytes())==rec['sha256']; c,b=read(p)
    assert c['contract']=='0.8' and c['task']==SLUG and c['execution_mode']=='unattended'
    assert c['stage_result']=={'stage':rec['stage'],'status':'completed','round':rec['round']}
    assert c['candidate']==rec['candidate'] and c['candidate']['snapshot']=='.yuzio/cohestra/handoffs/alpha-greeting/code-02.md'
    assert c['blocked']=={'value':False,'reason':None}
    h=Path(rec['handoff']).read_text(); assert rec['stage']+'-'+str(rec['round']).zfill(2) in h and 'unattended' in h
    assert 'code-02' in h and 'code-02' in b and rec['stage']+'-'+str(rec['round']).zfill(2) in b
    if rec['stage']=='code': assert c['status']=='in_progress' and c['next']=={'stage':'review','allowed':True,'reason':'stage_completed'} and '$cohestra review' in h
    elif rec['stage']=='review': assert c['status']=='in_progress' and c['next']=={'stage':'validate','allowed':True,'reason':'stage_completed'} and c['findings']['blocking']==0 and '$cohestra validate' in h
    elif rec['stage']=='validate':
        assert c['status']=='completed' and c['acceptance']=={'status':'passed'} and c['next']=={'stage':None,'allowed':False,'reason':'task_completed'} and c['findings']['blocking']==0 and 'passed' in h
    else: raise AssertionError('unsupported explicit validation request')
    assert INDEX.read_text()==rec['expected_old']
    rec['validated_at']=now(); (OUT/(label+'-validated.json')).write_text(json.dumps(rec,ensure_ascii=False,indent=2)); print('VALIDATED',label,rec['sha256'])

def publish_index(label):
    rec=json.loads((OUT/(label+'-validated.json')).read_text()); p=Path(rec['pending']); assert sha(p.read_bytes())==rec['sha256']; c,b=read(p)
    atomic(INDEX,c,b,rec['expected_old']); assert INDEX.read_text()==p.read_text()
    if rec['stage']=='validate':
        d,_=read(INDEX); assert d['status']=='completed' and d['acceptance']['status']=='passed' and d['stage_result']=={'stage':'validate','status':'completed','round':rec['round']} and d['next']=={'stage':None,'allowed':False,'reason':'task_completed'} and d['blocked']=={'value':False,'reason':None}
    with (OUT/'publication-audit.jsonl').open('a') as f: f.write(json.dumps({'published_at':now(),**rec},ensure_ascii=False)+'\n')
    print('PUBLISHED AND READ BACK',label,sha(INDEX.read_bytes()))
if __name__=='__main__':
    {'validate':validate_index,'publish':publish_index}[sys.argv[1]](sys.argv[2])
