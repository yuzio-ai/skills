import json, pathlib, datetime, hashlib, os, subprocess, difflib, sys
P=pathlib.Path(__file__).resolve().parent.parent
V=P/'verification'
S=pathlib.Path('/Users/zhubowen/Documents/yuzio-ai/skills')
def now(): return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
def read(p):
 s=p.read_text(); return json.loads(s.split('---',2)[1]),s.split('---',2)[2]
def render(d,b): return '---\n'+json.dumps(d,ensure_ascii=False,indent=2)+'\n---\n'+b
def atomic(p,s):
 old=p.read_bytes() if p.exists() else None
 t=p.with_name('.'+p.name+'.forward.tmp'); t.write_text(s)
 assert t.read_text()==s
 assert (p.read_bytes() if p.exists() else None)==old
 os.replace(t,p); assert p.read_text()==s
 return hashlib.sha256(s.encode()).hexdigest()
def taskpath(slug):return P/'.yuzio/cadra/tasks'/f'{slug}.md'
def runpath(run):return P/'.yuzio/cadra/runs'/f'{run}.md'
def handdir(slug):return P/'.yuzio/cohestra/handoffs'/slug
def initcadra():
 gi=P/'.gitignore'; assert not gi.exists(); gi.write_text('/.yuzio/\n')
 subprocess.run(['git','check-ignore','-v','.yuzio/probe'],cwd=P,check=True)
 assert not subprocess.check_output(['git','ls-files','.yuzio'],cwd=P).strip()
 c=P/'.yuzio/cadra'; (c/'tasks').mkdir(parents=True); (c/'runs').mkdir()
 (c/'README.md').write_text((S/'cadra/assets/project/README.md').read_text().replace('<实际项目名>',P.name).replace('<实际 Skill 版本>','0.6.0'))
 (c/'.gitignore').write_text((S/'cadra/assets/project/.gitignore').read_text())
def add(slug):
 req={'alpha-greeting':'实现 alpha.py greet(name)：非空字符串名字返回 Hello, <name>!；空字符串返回 Hello, world!。仅修改 alpha.py 与必要 tests/test_alpha.py。输入为字符串，不扩展其他类型行为。AC1 非空名字原样插入；AC2 空字符串使用 world。','beta-square':'实现 beta.py square(value)，返回整数输入的平方。仅修改 beta.py 与必要 tests/test_beta.py。AC1 负整数、零、正整数得到精确整数平方。不增加非整数输入校验或外部依赖。'}[slug]
 d=dict(protocol='0.6',slug=slug,title=slug,revision=1,preparation='draft',priority='medium',dependencies=[],flow='small-change',execution_policy={'stop_queue_on_failure':False},cohestra_task=f'.yuzio/cohestra/handoffs/{slug}/',revision_base=None,changed_fields=[])
 b=f'\n# {slug}\n\n## Requirement\n\n{req}\n\n## 绑定与修订\n\n- 绑定确认：无既有交付。\n- 创建：forward_validation；{now()}；Cadra 0.6.0 / 协议 0.6。来源：用户明确 add 请求。\n\n## Ready Gate\n\n当前结论：revision 1 draft，待 ready。\n'
 atomic(taskpath(slug),render(d,b));print('ADD',slug,'draft')
def ready(slug):
 p=taskpath(slug);d,b=read(p);assert d['preparation']=='draft';d['preparation']='ready'
 b+=f'\n### Gate revision {d["revision"]} · {now()}\n当前结论：通过。\n'
 for k,v in {'目标':'函数行为可判定','范围':'对应模块与必要测试，排除外部依赖及其他模块','验收':'输入输出及 unittest 可判定','人类决定':'无未决取舍，用户已授权实现及测试','输入':'项目模块、测试及 Python 可用','依赖':'空依赖','起点':'small-change start=code；首次无既有交付' if d['revision']==1 else 'requirement 修订由 code 重启；旧 Run 已结束且契约合法','范围配置':'small-change allowed=code,review,fix,validate'}.items():b+=f'- {k}：通过；{v}。\n'
 atomic(p,render(d,b)); print('READY',slug,d['revision'])
def initcohestra():
 c=P/'.yuzio/cohestra'; assert not c.exists()
 subprocess.run(['git','check-ignore','-v','.yuzio/probe'],cwd=P,check=True)
 for q in ['handoffs','retrospectives']:(c/q).mkdir(parents=True);(c/q/'.gitkeep').touch()
 (c/'README.md').write_text((S/'cohestra/assets/project/README.md').read_text().replace('<实际项目名称>',P.name).replace('<实际发行版本；仅记录初始化来源，不锁定后续调用>','0.10.1'))
 (c/'.gitignore').write_text((S/'cohestra/assets/project/.gitignore').read_text())
def newrun(run,slugs):
 assert not runpath(run).exists(); tasks=[]
 for slug in slugs:
  d,b=read(taskpath(slug));assert d['preparation']=='ready'; h=handdir(slug)/'README.md'; before=read(h)[0] if h.exists() else None
  req=b.split('## Requirement\n\n')[1].split('\n## ')[0].strip()
  tasks.append(dict(slug=slug,revision=d['revision'],previous_run=None if d['revision']==1 else d['revision_base']['run'],state='queued',definition={**d,'requirement':req,'gate_evidence':b.split('## Ready Gate')[1]},start_action={'kind':'首次启动' if before is None else '修订重启','stage':'code','source':'用户 run 授权；Ready Gate 八项复核通过；无依赖；初始无交付' if before is None else 'requirement 修订；用户 add/ready/run；沿旧合法契约从 code 重启','before':before},authorization_consumed=False,budget={'calls':0,'remediation':0,'retries':{}},checkpoint={'pending_call':None,'last_delivery':None},calls=[],result=None))
 d=dict(protocol='0.6',run_id=run,status='running',execution_mode='unattended',created_at=now(),skill_version='0.6.0',tasks=tasks,reports=[])
 b=f'\n# {run}\n\n## 建立依据\n目标：{P}。已有可写 Git 工作区，无 HEAD，未跟踪文件通过快照固定。非技能源仓库。无未完成 Run；Gate 八项逐项复核通过。\n范围：{slugs}，恢复列表为空。Cohestra 实际来源 {S}/cohestra，0.10.1，契约 0.8，支持 unattended 及单阶段。\n\n## 记录约定\n执行顺序与状态仅由 tasks 数组保存。当前执行者 forward_validation 唯一写入。无共享正式文档需要，过程与报告保存在本机。\n'
 atomic(runpath(run),render(d,b)); print('RUN_CREATED',run,slugs)
def intent(run,slug,stage):
 p=runpath(run);d,b=read(p); t=next(t for t in d['tasks'] if t['slug']==slug)
 current,_=read(taskpath(slug));assert current['revision']==t['revision'];assert t['checkpoint']['pending_call'] is None
 assert not any(x['state']=='running' and x['slug']!=slug for x in d['tasks'])
 h=handdir(slug)/'README.md';before=read(h)[0] if h.exists() else None
 if t['calls']:assert before['next']['allowed'] and before['next']['stage']==stage
 t['state']='running';n=len(t['calls'])+1;assert n<=16;t['budget']['calls']+=1
 t['calls'].append(dict(id=n,reason=t['start_action']['source'] if n==1 else '合法 next.stage；stage_completed',stage=stage,execution_mode='unattended',before=before,dispatch='prepared',closed=False,result=None,charged={'calls':1,'remediation':0,'retry_stage':None},prepared_at=now()))
 t['checkpoint']['pending_call']=n
 if t['revision']>1 and n==1:t['authorization_consumed']=True
 atomic(p,render(d,b));print('INTENT',run,slug,stage,n)
def dispatch(run,slug):
 p=runpath(run);d,b=read(p);t=next(t for t in d['tasks'] if t['slug']==slug);t['calls'][-1]['dispatch']='dispatched';t['calls'][-1]['dispatched_at']=now();atomic(p,render(d,b));print('DISPATCHED',slug,t['calls'][-1]['stage'])
if __name__=='__main__':globals()[sys.argv[1]](*sys.argv[2:])
