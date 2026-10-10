"""静态门禁：`logger.*(..., extra={...})` 的键不得与 LogRecord 保留属性同名。

真实事故（本文件就是它的墓碑）：
    logger.info("content created", extra={"kind": ..., "name": row.name})
stdlib 的 `Logger.makeRecord` 会执行 `rv.__dict__[key] = value`，遇到保留属性名时抛
`KeyError: "Attempt to overwrite 'name' in LogRecord"`。结果：**创建角色卡直接 500**，
而单元测试不会暴露（没人断言日志），只有打到真实数据库的集成测试才炸。

命名冲突属于「静默逻辑错误 / 静默缺失」类失效，靠人记不住，所以用 AST 扫描把整条
红线钉死：新增任何日志字段都会在 pytest 阶段被拦下。

保留属性集合不手抄，直接从 stdlib 构造一个 LogRecord 取 __dict__，随 Python 版本自动同步。
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path

# 需要扫描的源码根目录（本文件位于 backend/tests/）
APP_ROOT = Path(__file__).resolve().parent.parent / "app"

# stdlib 保留属性：手抄会漏，直接问 Python 自己
RESERVED_KEYS = frozenset(
    logging.LogRecord(
        name="", level=0, pathname="", lineno=0, msg="", args=(), exc_info=None
    ).__dict__
)


def _iter_extra_dicts() -> list[tuple[Path, int, ast.Dict]]:
    """遍历 app/ 下所有 .py，产出 (文件, 行号, extra 的字典字面量)。

    `extra=` 的值不是字典字面量（如变量、`**kwargs`）时无法静态判定，跳过——
    本门禁覆盖的是实际写法（全仓均为字面量）。
    """
    found: list[tuple[Path, int, ast.Dict]] = []
    for path in sorted(APP_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for kw in node.keywords:
                if kw.arg != "extra" or not isinstance(kw.value, ast.Dict):
                    continue
                found.append((path, kw.value.lineno, kw.value))
    return found


def _literal_string_keys(node: ast.Dict) -> list[str]:
    return [k.value for k in node.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)]


def test_reserved_key_set_is_not_empty() -> None:
    """门禁自身的前提：保留属性集合必须真实存在（否则测试会「假通过」）。"""
    assert {"name", "module", "msg", "args", "levelname", "lineno"} <= RESERVED_KEYS


def test_scanner_actually_sees_log_extra_calls() -> None:
    """门禁自身的有效性：确实扫到了日志调用，而不是 glob 写错了什么都没扫到。"""
    assert _iter_extra_dicts(), "未扫描到任何 extra= 字典，检查 APP_ROOT 是否正确"


def test_no_log_extra_key_collides_with_log_record() -> None:
    violations = [
        f"{path.relative_to(APP_ROOT.parent)}:{lineno} -> extra[{key!r}]"
        for path, lineno, node in _iter_extra_dicts()
        for key in _literal_string_keys(node)
        if key in RESERVED_KEYS
    ]
    assert not violations, (
        "以下日志调用使用了 LogRecord 保留属性名作为 extra 键，"
        "运行时会抛 KeyError 并把请求打成 500：\n  " + "\n  ".join(violations)
    )
