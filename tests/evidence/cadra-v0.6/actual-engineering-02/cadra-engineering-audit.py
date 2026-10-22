from pathlib import Path
import hashlib, json, re, shutil, subprocess, sys
PROJECT = Path('/private/tmp/cadra-engineering-recovery-kvs3043i')
EVIDENCE = Path('/Users/zhubowen/Documents/yuzio-ai/skills/tests/evidence/cadra-v0.6/actual-engineering-02')
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def front(p):
    text=p.read_text(); block=text.split('---',2)[1]
    try: return json.loads(block)
    except json.JSONDecodeError:
        result=subprocess.run(['ruby','-r','yaml','-r','json','-r','date','-e','puts JSON.generate(YAML.safe_load(STDIN.read, [Date, Time], [], true))'],input=block,text=True,capture_output=True,check=True)
        return json.loads(result.stdout)
def inventory():
    return {str(p.relative_to(PROJECT)):digest(p) for p in sorted(PROJECT.rglob('*')) if p.is_file() and not any(x in p.relative_to(PROJECT).parts for x in ('.git','__pycache__')) and p.suffix!='.pyc'}
def summary():
    runs=[]
    for p in sorted((PROJECT/'.yuzio/cadra/runs').glob('*.md')):
        if not re.fullmatch(r'run-\d{8}-\d+\.md',p.name): continue
        d=front(p)
        runs.append({'path':str(p.relative_to(PROJECT)),'id':d['run_id'],'status':d['status'],'tasks':[{k:i.get(k) for k in ('slug','revision','previous_run','state','authorization_consumed','budget','calls','checkpoint','start_action','result')} for i in d['tasks']]})
    return {'runs':runs,'tasks':{p.stem:front(p) for p in sorted((PROJECT/'.yuzio/cadra/tasks').glob('*.md'))}}
if __name__=='__main__':
    name=sys.argv[1]; target=EVIDENCE/name
    target.mkdir(exist_ok=False)
    hashes=inventory()
    for key in hashes:
        dest=target/'project'/key;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(PROJECT/key,dest)
    info=summary(); info['project']=str(PROJECT);info['hashes']=hashes
    (target/'snapshot.json').write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'snapshot':str(target),'files':len(hashes),'runs':[{k:r[k] for k in ('id','status')}|{'items':[{'slug':i['slug'],'revision':i['revision'],'state':i['state'],'calls':len(i['calls']),'budget':i['budget']} for i in r['tasks']]} for r in info['runs']]},ensure_ascii=False))
