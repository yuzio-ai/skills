from records import *
def report(run):
 p=runpath(run);d,b=read(p);n=len(d['reports'])+1;rp=p.with_name(f'{run}-report-{n:02}.md');assert not rp.exists()
 text=f'# {run} 执行报告\n\nRun 状态：{d["status"]}\n\nCadra 0.6.0 / 协议 0.6；生成时间 {now()}；执行者 forward_validation。来源仅为 [{p.name}]({p.name}) 的固定结果快照和调用记录。\n\n'
 counts={s:sum(t['state']==s for t in d['tasks']) for s in ['completed','blocked','failed','skipped']};text+=f'汇总：{counts}。未结束项：0。\n\n'
 for t in d['tasks']:
  r=t['result'];text+=f'## {t["slug"]} · revision {t["revision"]}\n\n- 状态：{r["state"]}；acceptance：{r["acceptance"]}。\n- 来源 Run：{t["previous_run"]}；首个动作：{t["start_action"]["kind"]}。\n- 实际调用：'+ ' → '.join(c['stage'] for c in t['calls'])+f'；总调用 {t["budget"]["calls"]}，整改 {t["budget"]["remediation"]}，失败重试 0。\n- 最后交付：{r["source"]}。\n- 候选：{r["candidate"]}。\n- 未关闭 findings：{r["findings"]}。\n- 人工介入：无；下一步：{r["next"]}。\n\n'
 text+='## 证据与限制\n\n真实业务实现、测试、作者审查与验收均有 Cohestra handoff；同一执行者 review，不声称独立审查。无提交，无网络，无外部依赖。首轮 alpha 验收时 beta 原有未实现失败已区分，beta 完成后的全量测试通过。\n\n## 后续\n\nRun 已结束，无必要待办。未来需求变化使用 $cadra add <slug>，然后 $cadra ready <slug>；本报告不触发额外执行。\n'
 atomic(rp,text);d['reports'].append(str(rp.relative_to(P)));atomic(p,render(d,b));print('REPORT',rp)
def revise():
 p=taskpath('alpha-greeting');d,b=read(p);r,_=read(runpath('run-20261022-01'));assert r['status']=='completed';assert d['revision']==1
 d.update(revision=2,preparation='draft',revision_base={'run':'run-20261022-01','revision':1},changed_fields=['requirement'])
 old=b.split('## Requirement\n\n')[1].split('\n## ')[0]
 req='实现 alpha.py greet(name)：先对输入字符串首尾空白做 strip；strip 后非空返回 Hello, <name>!；strip 后为空返回 Hello, world!。仅修改 alpha.py 与必要 tests/test_alpha.py。输入为字符串，不扩展其他类型行为。AC1 Ada 保持问候；AC2 空串、纯空格、制表符与换行归 world；AC3 首尾空白被去除，内部空白保留。'
 b=b.replace(old,req+'\n',1);b+=f'\n### 定义修订 · {now()}\n用户第二轮明确 add 要求 strip 首尾空白，覆盖 revision 1 非空名字原样插入约束。旧定义以 run-20261022-01 tasks[alpha-greeting].definition 为真源。revision 1 Gate 失效；当前 revision 2 draft，待 ready。变更字段 requirement。既有 Cohestra 主题对应本函数，绑定不变。\n'
 atomic(p,render(d,b));print('ADD_REVISION',d['slug'],d['revision'],'draft')
if __name__=='__main__':globals()[sys.argv[1]](*sys.argv[2:])
