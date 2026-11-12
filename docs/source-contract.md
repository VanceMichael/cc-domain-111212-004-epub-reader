# 来源格式与业务语义

夹具是可解包的 EPUB 3 容器，当前只查看资源。目标采集限定 XHTML 内容、package manifest/spine、nav 与注释引用，支持本地 fallback 链并限制循环与解压尺寸。扩展练习可调整 spine 的 linear、资源 media-type 和链接锚点；不要求 DRM、脚本执行或完整排版。定位使用出版物摘要、资源路径、节点路径三元组，不用临时解包路径充当身份。

本地演练夹具由 `sampledata.py` 生成，均为虚构业务数据。`sample` 是当前可查看输入，`invalid` 是边界失败输入，其余用于对照来源变体。生成不会下载资源。

本地 HTTP 演练器采用方法与原始路径作为路由键，值为按调用次数返回的响应数组，耗尽后维持最后一项。响应可定义 status、headers、text/base64、require_headers、chunk_bytes、disconnect_after。每次请求保留方法、路径、头与正文摘要表示，便于核对实际访问；演练器只监听回环地址。

原始输入上限 16 MiB 是现有查看入口的保护值，不代表未来持续采集需一次读完整来源。格式含义和截断错误不能被 HTTP 200 覆盖。
