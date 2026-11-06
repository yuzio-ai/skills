"""Isolated inputs for real standalone-review sessions; no agent output is generated."""

from pathlib import Path
import shutil
import subprocess

REPO = Path(__file__).resolve().parents[2]


def prepare(suite):
    suite = Path(suite)
    suite.mkdir(parents=True, exist_ok=False)
    shutil.copytree(REPO / "cohestra", suite / "skill")
    for name in ("default", "unavailable", "self-review"):
        root = suite / name
        root.mkdir()
        (root / ".gitignore").write_text("/.yuzio/\n__pycache__/\n")
        (root / "AGENTS.md").write_text(
            "这是隔离审查项目。业务源文件及需求只读，允许 Python 检查。\n"
            "只写本次审查所需的 Cohestra 交付及必要正式报告。\n"
            "不执行整改、验收、提交或推送；不访问其他项目。\n")
        (root / "requirements.md").write_text(
            "# 展示名称\n\nnormalize_name 必须先去除两端空白；"
            "空字符串及纯空白字符串均返回 Untitled，其余返回去空白后的名称。\n"
            "当前候选由测试夹具生成，不是执行会话或 reviewer 编写。\n")
        (root / "names.py").write_text(
            'def normalize_name(value):\n    return value.strip() if value else "Untitled"\n')
        def git(*args):
            return subprocess.run(["git", "-C", str(root), "-c", "core.hooksPath=/dev/null", *args], check=True,
                                  text=True, capture_output=True).stdout.strip()
        git("init", "-q")
        git("add", ".gitignore", "AGENTS.md", "requirements.md", "names.py")
        git("-c", "user.name=Cohestra fixture", "-c", "user.email=fixture@example.invalid",
            "-c", "commit.gpgsign=false", "commit", "-qm", "Fixed review input")
        candidate = git("rev-parse", "HEAD")
        request = (
            f"使用 {suite / 'skill/SKILL.md'} 的 $cohestra review。\n"
            f"目标项目：{root}\n任务目录：{root / '.yuzio/cohestra/handoffs/name-normalization'}\n"
            f"首次从 review 起步。固定候选：{candidate}。需求见 requirements.md。\n"
            "审查 names.py 是否满足需求，只完成本轮 review。允许必要的只读检查。\n")
        if name == "unavailable":
            request += "本次运行环境禁止创建或调用任何子智能体；这是工具条件限制，不是请求改做自审。\n"
        elif name == "self-review":
            request += "本次明确要求不委派，由当前会话自审，并如实记录审查方式。\n"
        (suite / f"{name}-request.md").write_text(request)
    return suite
