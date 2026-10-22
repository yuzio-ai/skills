import json,sys
from pathlib import Path
from record_io import read,sha,now
p=Path(sys.argv[1]); c,b=read(p); stage=sys.argv[2]; task=p.parent.parent; handoff=task/f'{stage}-01.md'; h=handoff.read_text()
assert c['contract']=='0.8' and c['task']=='greeting-service' and c['execution_mode']=='unattended'
assert c['stage_result']=={'stage':stage,'status':'completed','round':1}
assert c['candidate']==read(task/'README.md')[0]['candidate']
assert Path(c['candidate']['snapshot']).is_file()
assert c['findings']=={'blocking':0,'non_blocking':0,'unresolved':0}
assert c['blocked']=={'value':False,'reason':None}
assert all(name in h for name in ('## 身份与输入','## 有效上下文','## 本阶段结果','## 证据与限制','## 下一步交接','unattended'))
assert f'{stage}-01' in b and f'{stage}-01' in h
if stage=='review':
 assert c['status']=='in_progress' and c['next']=={'stage':'validate','allowed':True,'reason':'stage_completed'}
 assert '$cohestra validate' in h and '$cohestra validate' in b
else:
 assert stage=='validate' and c['status']=='completed' and c['acceptance']=={'status':'passed'}
 assert c['next']=={'stage':None,'allowed':False,'reason':'task_completed'}
 assert '验收通过' in h and '验收通过' in b and '无后续必做阶段' in h and '无后续必做阶段' in b
for group in ('task_files','dependencies'):
 for name,v in json.loads((task/'scratch/candidate-01/manifest.json').read_text())[group].items():
  assert sha(Path.cwd()/name)==v['sha256']==sha(v['snapshot'])
proof={'validated':True,'parser':'JSON parser for YAML 1.2 JSON subset','pending_path':str(p),'sha256':sha(p),'stage':stage,'round':1,'candidate':c['candidate'],'handoff_sha256':sha(handoff),'time':now()}
Path(str(p)+'.validation.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2));print(json.dumps(proof,ensure_ascii=False))
