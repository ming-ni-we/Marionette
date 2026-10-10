"""测试全局环境（pytest 最先加载本文件，早于任何 app.* 导入）。

**凭证隔离**：测试进程**强制**使用固定的测试口令，绝不继承部署环境里那个随机
ACCESS_PASSWORD。理由：
  - 部署口令是随机生成的，集成用例若继承它，同一份用例在本地与服务器上走的是
    不同凭证，断言失败时分不清是「代码错」还是「环境串味」；
  - 本文件在 pytest 启动时即写入 os.environ，且早于 `app.core.config.get_settings()`
    的首次调用（lru_cache 单例），因此进程内所有组件看到的是同一个测试口令。

数据库连接串**不在这里覆盖**：集成测试必须连真实 PostgreSQL，由运行环境注入。
"""

from __future__ import annotations

import os

# 唯一的凭证来源：测试模块与集成夹具都读它，不再各自硬编码。
TEST_ACCESS_PASSWORD = "test-passphrase"

# 必须用下标赋值（覆盖），不能用 setdefault——后者会在服务器上被部署口令顶掉。
os.environ["ACCESS_PASSWORD"] = TEST_ACCESS_PASSWORD
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"

# 断言依赖这些默认值，写明比依赖 config.py 的默认值更稳
os.environ.setdefault("ACCESS_MAX_FAILED", "5")
os.environ.setdefault("ACCESS_LOCK_WINDOW_SECONDS", "900")
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")
os.environ.setdefault("APP_ENV", "test")
