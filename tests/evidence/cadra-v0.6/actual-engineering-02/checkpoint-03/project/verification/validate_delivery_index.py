"""Low-level validation only. No stage selection, execution or scheduling."""
import sys,json
from pathlib import Path
from record_io import read,sha,now
p=Path(sys.argv[1]);e=json.loads(Path(sys.argv[2]).read_text());c,b=read(p)
assert c==e['contract']
assert c['contract']=='0.8' and c['task']=='greeting-service' and c['execution_mode']=='unattended'
assert c['stage_result']=={'stage':e['stage'],'status':'completed','round':e['round']}
assert c['candidate']==e['candidate'] and c['blocked']=={'value':False,'reason':None}
assert c['findings']=={'blocking':0,'non_blocking':0,'unresolved':0}
if e['stage']=='review':
 assert c['status']=='in_progress' and c['next']=={'stage':'validate','allowed':True,'reason':'stage_completed'}
else:
 assert e['stage']=='validate' and c['status']=='completed' and c['acceptance']=={'status':'passed'}
 assert c['next']=={'stage':None,'allowed':False,'reason':'task_completed'}
for phrase in e['required_body']: assert phrase in b,phrase
h=Path(e['handoff']);assert sha(h)==e['handoff_sha256'] and h.name==f"{e['stage']}-{e['round']:02d}.md"
for phrase in ['cohestra v0.8','0.10.1','unattended']+e['handoff_required']: assert phrase in h.read_text(),phrase
m=p.parent/'candidate-01/manifest.json';assert sha(m)==e['candidate_manifest_sha256']
for section in ('task_files','dependencies'):
 for entry in json.loads(m.read_text())[section].values(): assert sha(entry['snapshot'])==entry['sha256']
proof={'validated':True,'parser':'JSON subset of YAML 1.2','pending_path':str(p),'sha256':sha(p),'stage':e['stage'],'round':e['round'],'candidate':c['candidate'],'handoff_sha256':sha(h),'time':now()}
Path(str(p)+'.validation.json').write_text(json.dumps(proof,indent=2));print(json.dumps(proof))
