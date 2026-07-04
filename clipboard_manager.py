#!/usr/bin/env python3
"""剪贴板历史管理器入口。

代码已模块化拆分到 clipman/ 包,本文件只保留启动入口,
保证 run.sh / toggle.sh / 开机自启的调用方式不变。
"""

from clipman.app import main

if __name__ == "__main__":
    main()
