import sys,json,hashlib
from pathlib import Path
from record_io import read,sha,now,ROOT
p=Path(sys.argv[1]).resolve(); c,body=read(p); h=p.parent.parent; stage=c['stage_result']['stage']; rnd=c['stage_result']['round']; handoff=h/f'{stage}-{rnd:02d}.md'
assert c['contract']=='0.8' and c['task']==h.name=='greeting-service'
assert c['execution_mode']=='unattended' and c['stage_result']['status']=='completed' and type(rnd) is int and rnd==1
assert c['candidate']=={'commit':None,'snapshot':str(h/'code-01.md')}
assert c['blocked']=={'value':False,'reason':None}
assert stage in ('code','review','validate')
assert len(body.strip())>100 and f'{stage}-{rnd:02d}' in body
text=handoff.read_text(); assert 'unattended' in text and '0.10.1' in text and '0.8' in text
assert text.count('\n## ')==5
m=json.loads((h/'scratch/candidate-01/manifest.json').read_text())
for section in ('task_files','dependencies'):
 for name,item in m[section].items():
  assert sha(ROOT/name)==sha(Path(item['snapshot']))==item['sha256']
  if 'diff_sha256' in item: assert sha(Path(item['snapshot']+'.diff'))==item['diff_sha256']
if stage=='validate':
 assert c['status']=='completed' and c['acceptance']=={'status':'passed'}
 assert c['next']=={'stage':None,'allowed':False,'reason':'task_completed'}
 assert c['findings']=={'blocking':0,'non_blocking':0,'unresolved':0}
 assert '验收 passed' in text and '终点' in body and '$cohestra review' not in body and '$cohestra validate' not in body
else:
 nxt={'code':'review','review':'validate'}[stage]
 assert c['status']=='in_progress' and c['next']=={'stage':nxt,'allowed':True,'reason':'stage_completed'}
 assert f'$cohestra {nxt}' in body
 if stage=='review': assert c['findings']=={'blocking':0,'non_blocking':0,'unresolved':0}
proof={'validated':True,'path':str(p),'sha256':sha(p),'stage':stage,'round':rnd,'candidate':c['candidate'],'handoff_sha256':sha(handoff),'candidate_manifest_sha256':sha(h/'scratch/candidate-01/manifest.json'),'checks':['JSON YAML-subset parse','complete required contract','stage/round/mode','handoff readback','candidate and dependency bytes','body/next agreement','joint completion fields if validate'],'time':now()}
Path(str(p)+'.validation.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)); print(json.dumps(proof,ensure_ascii=False))
