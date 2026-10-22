import sys, json
from pathlib import Path
from record_io import read, sha, now
p=Path(sys.argv[1]); expected=json.loads(Path(sys.argv[2]).read_text()); d,b=read(p)
assert set(['contract','task','status','execution_mode','stage_result','candidate','next','blocked']) <= d.keys()
assert d['contract']=='0.8' and d['task']=='prefix-source' and d['execution_mode']=='unattended'
assert d['stage_result']=={'stage':expected['stage'],'status':'completed','round':expected['round']}
assert d['candidate']==expected['candidate'] and Path(d['candidate']['snapshot']).is_file()
assert d['blocked']=={'value':False,'reason':None}
assert f"{expected['stage']}-01.md" in b
handoff=p.parent.parent/f"{expected['stage']}-01.md"
h=handoff.read_text(); assert 'unattended' in h and '0.10.1' in h
if expected['stage']=='validate':
    assert d['status']=='completed' and d['acceptance']=={'status':'passed'}
    assert d['next']=={'stage':None,'allowed':False,'reason':'task_completed'}
    assert '验收通过' in h and '$cohestra ' not in h.split('## 下一步交接')[1]
else:
    nxt={'code':'review','review':'validate'}[expected['stage']]
    assert d['status']=='in_progress' and d['next']=={'stage':nxt,'allowed':True,'reason':'stage_completed'}
    assert '$cohestra '+nxt in h
proof={'validated':True,'parser':'JSON parser for JSON subset of YAML 1.2 Front Matter','pending_path':str(p),'sha256':sha(p),'stage':expected['stage'],'round':expected['round'],'candidate':d['candidate'],'time':now()}
Path(str(p)+'.validation.json').write_text(json.dumps(proof,indent=2)); print(json.dumps(proof))
