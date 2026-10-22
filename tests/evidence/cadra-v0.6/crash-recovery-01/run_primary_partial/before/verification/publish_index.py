import sys, json, os
from pathlib import Path
from record_io import sha,read,now
pending=Path(sys.argv[1]); expected=json.loads(Path(sys.argv[2]).read_text()); proof=json.loads(Path(str(pending)+'.validation.json').read_text())
assert proof['validated'] and proof['sha256']==sha(pending)
target=pending.parent.parent/'README.md'
assert (sha(target) if target.exists() else None)==expected['old_sha256']
content=pending.read_bytes(); temp=target.with_name('.README-publish-'+str(os.getpid()))
with temp.open('xb') as f: f.write(content)
assert temp.read_bytes()==content and read(temp)==read(pending)
assert (sha(target) if target.exists() else None)==expected['old_sha256']
os.replace(temp,target)
assert target.read_bytes()==content
print(json.dumps({'published':True,'readback':True,'sha256':sha(target),'stage':proof['stage'],'round':proof['round'],'time':now()}))
