from records import *
def stage_prepare(slug,stage,roundstr,result,evidence):
 n=int(roundstr);h=handdir(slug);h.mkdir(parents=True,exist_ok=True); hp=h/f'{stage}-{n:02}.md';assert not hp.exists()
 old=h/'README.md';previous=old.read_text() if old.exists() else None
 module='alpha' if slug=='alpha-greeting' else 'beta';files=[f'{module}.py',f'tests/test_{module}.py']
 d,b=read(taskpath(slug));req=b.split('## Requirement\n\n')[1].split('\n## ')[0].strip()
 if stage=='code':
  snap=h/'scratch'/f'code-{n:02}';snap.mkdir(parents=True);manifest={}
  for f in files:
   q=snap/f;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes((P/f).read_bytes());manifest[f]=hashlib.sha256(q.read_bytes()).hexdigest()
  (snap/'manifest.json').write_text(json.dumps(manifest,indent=2))
  baseline=V/'baseline' if n==1 else h/'scratch'/f'code-{n-1:02}'
  diff=''.join(''.join(difflib.unified_diff((baseline/f).read_text().splitlines(True),(P/f).read_text().splitlines(True),fromfile='baseline/'+f,tofile='candidate/'+f)) for f in files)
  (snap/'candidate.diff').write_text(diff)
  cand={'commit':None,'snapshot':str(hp.relative_to(P))}; inputs=str(taskpath(slug));meta=f'固定候选：{snap}；manifest.json 记录全部任务文件 SHA-256；candidate.diff 保存精确差异。Git 无 HEAD；初始所有业务文件未跟踪，原内容保存在 verification/baseline。'
 else:
  pd,_=read(old);cand=pd['candidate'];inputs=str(h/f'{"code" if stage=="review" else "review"}-{n:02}.md');meta='候选沿用 '+cand['snapshot']+'；本阶段未改变业务文件。'
  manifest=json.loads((h/'scratch'/f'code-{n:02}'/'manifest.json').read_text())
  assert all(hashlib.sha256((P/f).read_bytes()).hexdigest()==v for f,v in manifest.items())
 nxt={'code':'review','review':'validate','validate':None}[stage]
 contract=dict(contract='0.8',task=slug,status='completed' if stage=='validate' else 'in_progress',execution_mode='unattended',stage_result={'stage':stage,'status':'completed','round':n},candidate=cand,next={'stage':nxt,'allowed':nxt is not None,'reason':'task_completed' if nxt is None else 'stage_completed'},blocked={'value':False,'reason':None})
 if stage in ['review','validate']:contract['findings']={'blocking':0,'non_blocking':0,'unresolved':0}
 if stage=='validate':contract['acceptance']={'status':'passed'}
 nexttext='任务验收完成，终点已到达，无后续必做阶段。' if nxt is None else f'$cohestra {nxt} {hp}；execution_mode: unattended。'
 text=f'# {slug} · {stage}-{n:02}\n\n## 身份与输入\n\n- 协议：cohestra v0.8；Skill 0.10.1，来源 {S}/cohestra。\n- 执行者：main_resume_validation，唯一索引维护者。\n- 时间：{now()}\n- 执行模式：unattended。\n- 阶段状态：已结束，completed。\n- 输入与上游依据：{inputs}；显式指定任务目录 {h}。\n- {meta}\n'+('- 初始化：本轮首次 code 前最小初始化 .yuzio/cohestra。\n' if slug=='alpha-greeting' and stage=='code' and n==1 else '')+f'\n## 有效上下文\n\n流程起点 code，small-change 允许 code/review/fix/validate。用户授权对应模块与必要测试；无提交、无网络、仅标准库。当前定义 revision {d["revision"]}：{req}\n'+('修订确认：用户第二轮 add 请求明确 strip 首尾空白；覆盖第一轮 AC1 名字原样插入，并扩展空白归一化验收。\n' if n>1 else '')+f'\n## 本阶段结果\n\n{result}\n\n## 证据与限制\n\n{evidence}\n环境：本机 Python 3，标准库 unittest，无网络，无额外权限。原始 alpha/beta 均抛 NotImplementedError，基线测试失败已保存在 verification/baseline-test.log。\n\n## 下一步交接\n\n{nexttext}\n'
 hp.write_text(text);assert hp.read_text()==text
 body=f'\n# {slug}\n\n- 任务目标与有效决定：见 {hp.name}，当前 requirement revision {d["revision"]}。从 code 起步；无补造 need/design。\n- 索引维护者：main_resume_validation。\n- 工作项：实现与作者检查见 code；同一执行者 review，不能视为独立审查；用户与项目无强制独立审查要求。验收依据见实际 validate 轮次。无提交或发布授权。\n- 正式文档：局部函数变更，无共享文档需求；保留本机记录。\n- 最近更新：{now()}\n\n| 阶段/轮次 | 交付物及覆盖职责 | 结论 | 输入/目标候选 |\n|---|---|---|---|\n'
 if previous:
  body+='\n'.join(x for x in previous.splitlines() if x.startswith('| ') and not x.startswith('| 阶段'))+'\n'
 body+=f'| {stage}-{n:02} | [{hp.name}]({hp.name}) | completed | {cand["snapshot"]} |\n'
 if nxt:body+=f'\n下一步输入与责任：{hp}；main_resume_validation 由 Cadra 按 next 派发。\n'
 content=render(contract,body);pending=V/f'{slug}-{stage}-{n:02}-pending.md';pending.write_text(content)
 meta={'target':str(old),'expected_old':previous,'pending':str(pending),'sha256':hashlib.sha256(content.encode()).hexdigest(),'stage':stage,'round':n,'candidate':cand,'handoff':str(hp)}
 (V/'publication-input.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2));print('HANDOFF_READBACK_OK',hp,'PENDING',pending)
def validate_pending():
 m=json.loads((V/'publication-input.json').read_text());p=pathlib.Path(m['pending']);s=p.read_text();d,b=read(p)
 assert hashlib.sha256(s.encode()).hexdigest()==m['sha256'];assert pathlib.Path(m['handoff']).exists()
 assert d['contract']=='0.8' and d['execution_mode']=='unattended';assert d['stage_result']=={'stage':m['stage'],'status':'completed','round':m['round']};assert d['candidate']==m['candidate'];assert d['task']==pathlib.Path(m['target']).parent.name
 assert d['blocked']=={'value':False,'reason':None}
 if m['stage']=='validate':assert d['status']=='completed' and d['acceptance']=={'status':'passed'} and d['next']=={'stage':None,'allowed':False,'reason':'task_completed'}
 else:assert d['status']=='in_progress' and d['next']=={'stage':{'code':'review','review':'validate'}[m['stage']],'allowed':True,'reason':'stage_completed'}
 assert ('下一步输入' in b)==d['next']['allowed'];assert f'| {m["stage"]}-{m["round"]:02} |' in b
 # JSON-object Front Matter is a strict subset of YAML 1.2. json.loads validates all syntax used here.
 (V/'publication-validated.json').write_text(json.dumps(m,ensure_ascii=False,indent=2));print('PREPUBLICATION_VALIDATION_OK',m['sha256'],m['stage'],m['round'],m['candidate'])
def publish():
 m=json.loads((V/'publication-validated.json').read_text());assert m==json.loads((V/'publication-input.json').read_text());p=pathlib.Path(m['pending']);s=p.read_text();assert hashlib.sha256(s.encode()).hexdigest()==m['sha256'];target=pathlib.Path(m['target']);assert (target.read_text() if target.exists() else None)==m['expected_old'];atomic(target,s);assert read(target)==read(p)
 with (V/'publication-audit.jsonl').open('a') as f:f.write(json.dumps({k:v for k,v in m.items() if k!='expected_old'},ensure_ascii=False)+'\n')
 print('INDEX_SYNC_SUCCESS',target,m['sha256'])
def close(run,slug):
 p=runpath(run);d,b=read(p);t=next(t for t in d['tasks'] if t['slug']==slug);c=t['calls'][-1];idx=handdir(slug)/'README.md';state,_=read(idx);m=json.loads((V/'publication-validated.json').read_text())
 assert hashlib.sha256(idx.read_bytes()).hexdigest()==m['sha256'];assert state['task']==slug and state['execution_mode']=='unattended' and state['stage_result']['stage']==c['stage'];assert not c['closed']
 if c['before'] and c['before']['stage_result']['stage']==c['stage']:assert state['stage_result']['round']>c['before']['stage_result']['round']
 delivery={'contract':state,'handoff':m['handoff'],'index':str(idx),'index_sha256':m['sha256'],'sync':'confirmed','time':now()}
 c['result']=delivery;c['closed']=True;c['closed_at']=now();t['checkpoint']={'pending_call':None,'last_delivery':delivery}
 if state['status']=='completed':
  assert state['acceptance']['status']=='passed';t['state']='completed';t['result']={'state':'completed','last_delivery':delivery,'candidate':state['candidate'],'findings':state.get('findings'),'acceptance':state['acceptance']['status'],'human_intervention':[],'next':state['next'],'source':m['handoff'],'time':now()}
 if all(x['state']=='completed' for x in d['tasks']):d['status']='completed';d['completed_at']=now()
 assert t['budget']['calls']==sum(x['charged']['calls'] for x in t['calls']);atomic(p,render(d,b));print('CALL_CLOSED',slug,c['stage'],t['state'],'RUN',d['status'])
if __name__=='__main__':globals()[sys.argv[1]](*sys.argv[2:])
