# epub-reader

电子手册正文与注释的阅读序采集所用的来源检查与原件留存工具。

## 当前能力

`source.py` 查看来源的现有结构，不把检查结果冒充完整业务采集。
`collect.py` 按出版物语义采集正文：以 container 指向的 package、manifest 与 spine 决定主阅读序，不按 ZIP 文件名排序；非线性资源、导航文档与可复用注释分别归位，相对链接、锚点、行间注音与语言切换保留为可解释结构；脚注被多章引用时只采集一次并保留回跳；fallback 链限深并检测循环，缺资源或循环记入缺失报告；固定版式明确报告 declined，不重排文本；每个段落携带出版物摘要、资源路径、节点路径三元组，去重只针对同一资源的重复引用。
`storage.py` 将原始字节、来源标识、摘要和检查结果一起保存在本地 SQLite，重复原件保留同一收件编号。
`sampledata.py` 构造可重复的本地数据；`transport.py` 提供独立的回环 HTTP 演练源与请求记录。
解释范围和来源变体见 `docs/source-contract.md`，当前检查测试与将来新增业务能力的测试应分开保留。

## 环境

Python 3.11 或以上，仅标准库，无需凭据和外部数据。使用容器时可执行 `docker build -t epub-reader .`，依赖及镜像须在正式运行前准备。
运行入口、测试与演示均不安装包，不访问公网。数据库使用临时路径，不向代码目录写入业务文件。

## 测试与构建

构建工具版本固定在 `requirements-build.txt`，在环境准备阶段执行 `python3 -m pip install -r requirements-build.txt`；容器构建已包含此步骤。应用运行仍仅使用标准库，测试及演示不安装依赖。

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q app.py collect.py source.py sampledata.py storage.py transport.py scenario.py
python3 -m build --wheel --no-isolation
```

## 快速演示

```sh
python3 app.py demo
python3 app.py collect-demo
```

`demo` 真实启动本地来源、领取原件、执行检查并保存临时数据库，展示检查结果与重复收件身份，退出后自动清理。
`collect-demo` 经本地回环来源领取虚构手册（含非线性附录、重复脚注、损坏链接与 fallback 链），输出按 spine 排列的阅读结果与缺失报告。
两者正常在数秒内完成，不以预录日志代替执行，不执行书内脚本，不访问外站。

## 单独检查与收件

```sh
python3 app.py fixtures /tmp/epub-reader-fixtures
python3 app.py inspect /tmp/epub-reader-fixtures/sample.epub
python3 app.py collect /tmp/epub-reader-fixtures/manual.epub
python3 app.py capture /tmp/epub-reader-fixtures/sample.epub --database /tmp/epub-reader.sqlite3 --source local-partner
python3 app.py list --database /tmp/epub-reader.sqlite3
```

生成夹具不会覆盖已有文件。运行错误以 JSON 输出到标准错误并返回退出码 2；原始输入无效时不生成成功收件。内部原件与任何对外展示副本应分开管理，不写入真实个人数据。
