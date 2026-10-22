import json, os, hashlib, datetime
from pathlib import Path
ROOT=Path('/private/tmp/cadra-crash-recovery-xjhbj4gn/run_replace_ack_lost')
def now(): return datetime.datetime.now().astimezone().isoformat()
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
    text=Path(p).read_text(); _,head,body=text.split('---',2)
    return json.loads(head),body

def write(p,data,body,expected):
    p=Path(p); p.parent.mkdir(parents=True,exist_ok=True)
    assert (sha(p) if p.exists() else None)==expected,'concurrent change'
    content='---\n'+json.dumps(data,ensure_ascii=False,indent=2)+'\n---\n'+body
    temp=p.with_name(p.name+'.tmp-'+str(os.getpid()))
    temp.write_text(content); assert read(temp)==(data,'\n'+body)
    assert (sha(p) if p.exists() else None)==expected,'concurrent change'
    os.replace(temp,p); assert p.read_text()==content
    print(json.dumps({'path':str(p),'sha256':sha(p),'readback':True}))
