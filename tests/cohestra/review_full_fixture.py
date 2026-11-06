"""Raw projects and observable publication faults for standalone-review live tests.

Stage outputs are never generated here. Pre-existing code/index inputs for fault
cases are explicitly synthetic; independent agents decide and publish review.
"""

import json
from pathlib import Path
import shutil
import subprocess

from .review_fixture import prepare

CASES = ("auto-route", "unattended", "candidate-unavailable", "identity-unavailable",
         "self-review-gate", "publish-failure", "publish-conflict")


def prepare_full(suite):
    suite = prepare(suite)
    seed = suite / "default"
    for name in CASES:
        shutil.copytree(seed, suite / name)
    for name in ("default", "unavailable", "self-review"):
        shutil.rmtree(suite / name)
        (suite / f"{name}-request.md").unlink()
    shutil.copy2(Path(__file__).with_name("validate_fixture.py"), suite / "publication-driver.py")
    controller = []
    for name in CASES:
        root = suite / name
        candidate = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        task = root / ".yuzio/cohestra/handoffs" / ("sample" if name.startswith("publish-") else "name-normalization")
        intro = (f"使用 {suite / 'skill/SKILL.md'} 的 Cohestra。\n" if name == "auto-route"
                 else f"使用 {suite / 'skill/SKILL.md'} 的 $cohestra review。\n")
        request = intro + f"目标项目：{root}\n任务目录：{task}\n固定候选：{candidate}。需求见 requirements.md。\n"
        request += "请审查现有 names.py 是否符合需求。只交付本轮审查，允许必要的只读 Python 检查；不整改或验收。\n"
        if name == "unattended":
            request += "execution_mode: unattended\n"
        elif name == "candidate-unavailable":
            request = request.replace(candidate, "0" * 40)
            request += "本次只能审查显式指定的提交，不允许改用 HEAD 或另建候选快照。\n"
        elif name == "identity-unavailable":
            request += ("运行前提：被审候选的实现/整改作者身份无法取得，且没有可信作者审计记录。"
                        "requirements.md 中通用的夹具生成声明不适用于本例；不能凭角色名称或新会话猜测作者分离。\n")
        elif name == "self-review-gate":
            request += ("本次明确要求不委派，由当前会话自审；如实记录。既定验收仍必须有独立审查，"
                        "本次指令不免除该验收门禁。\n")
        elif name.startswith("publish-"):
            task.mkdir(parents=True)
            project = root / ".yuzio/cohestra/README.md"
            project.write_text("# 受控既有项目\n\n预置索引和 code 输入为合成测试资料，不是实际 agent 执行证据。\n")
            state = dict(contract="0.8", task="sample", status="in_progress", execution_mode="attended",
                         stage_result=dict(stage="code", status="completed", round=1),
                         candidate=dict(commit=candidate, snapshot=None),
                         next=dict(stage="review", allowed=True, reason="stage_completed"),
                         blocked=dict(value=False, reason=None))
            (task / "README.md").write_text("---\n" + json.dumps(state) + "\n---\n\n# 展示名称\n\n"
                                            "预置 code-01 为合成输入，引用 requirements.md 和固定提交；待实际 review。\n")
            (task / "code-01.md").write_text("# 合成 code 输入\n\n候选 " + candidate +
                                            "，来源为测试夹具。请独立按 requirements.md 审查；没有既有审查结论。\n")
            (root / "PUBLICATION.md").write_text(
                "# 项目发布接口\n\n本项目的任务 README 只能通过外部测试驱动发布，不得直接写入。"
                "review handoff 正常写入。不要绕过接口或修改驱动/controller。\n"
                f"校验：python3 -B {suite / 'publication-driver.py'} preflight {root} <完整提案路径>\n"
                f"发布：python3 -B {suite / 'publication-driver.py'} publish {root} <同一提案路径> <旧 README 的 sha256>\n"
                "校验语义由执行者核对；必须先收到校验成功，再另一次工具调用发布。"
                "提案与 handoff 放在任务目录。接口错误后遵守技能的失败与恢复规则。\n")
            request += "项目的索引发布接口约束见 PUBLICATION.md，派发时传给实际 reviewer。\n"
            controller.append(dict(id=name, fault="replace" if name == "publish-failure" else "concurrent"))
        (suite / f"{name}-request.md").write_text(request)
    (suite / "controller.json").write_text(json.dumps(controller, indent=2) + "\n")
    root = suite / "closeout-integration"
    shutil.copytree(suite / "auto-route", root)
    (root / "names.py").write_text('def normalize_name(value):\n    return value.strip() or "Untitled"\n')
    (root / "AGENTS.md").write_text(
        "这是隔离验证项目。允许 Python 只读验证和阶段交付。需求见 requirements.md。"
        "没有 UI 或外部依赖。不得提交、推送或发布。\n")
    subprocess.run(["git", "-C", str(root), "add", "names.py", "AGENTS.md"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "-c", "core.hooksPath=/dev/null",
                    "-c", "user.name=Cohestra fixture", "-c", "user.email=fixture@example.invalid",
                    "-c", "commit.gpgsign=false", "commit", "-qm", "Correct closeout candidate"],
                   check=True, capture_output=True)
    candidate = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    (suite / "closeout-integration-request.md").write_text(
        f"使用 {suite / 'skill/SKILL.md'} 的 $cohestra closeout。\n目标项目：{root}\n"
        f"任务目录：{root / '.yuzio/cohestra/handoffs/name-normalization'}\n候选：{candidate}。"
        "首次从 review 开始，不补造前置历史；需求见 requirements.md。允许审查、必要整改与验收收尾。"
        "候选由测试宿主生成，允许 Python 检查。不提交、推送或发布。\n")
    return suite
