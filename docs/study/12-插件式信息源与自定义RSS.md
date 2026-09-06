# 插件式信息源:自定义 RSS 如何接入管道

## 这个知识点是什么

"插件式信息源"指新增一类信息源时,只写一个同构的客户端(实现 `search(plan, topic_id, seen_hashes) → list[CandidateItem]`),检索、评分、落库、推送的下游全部复用,管道其他部分零改动。自定义 RSS 是这个机制的用户侧兑现:用户贴一个订阅地址,系统校验健康度后把它当作该主题的第四类源(与 arXiv/HN/GitHub 并列)。

类比:USB 接口——管道定义了"源"的标准接口形状,arXiv 是出厂自带设备,RSS 是用户后插的U盘,插上就能用,不用拆机器。

## TradeWinds 为什么需要它

扩展计划把它列为与规模无关的能力之一:再聪明的 Planner 也覆盖不了长尾信息源(某个垂直领域博客、公司技术 Radar)。用户显式提交的源是**最强的意图信号**——不同于 Planner 的"推断",用户说"盯这个源"就必须被检索。同时它带来新的健壮性要求:用户提交的源质量不可控,必须有健康度校验与持续复检。

## 本项目怎么实现的

- **协议解耦**([tools/base.py](../../src/tradewinds/tools/base.py)):新增 `Limiter` 协议,`RateLimiter`(共享限速)与 `PassthroughLimiter`(探活直通)都是它的实现——`fetch_text` 等请求助手只认协议,不再绑定具体限速器;
- **RSS 客户端**([tools/rss.py](../../src/tradewinds/tools/rss.py)):标准库 ElementTree 同时解析 RSS 2.0(`channel/item`)与 Atom(`feed/entry`),双日期格式(RFC822/ISO8601)兜底;时间窗过滤与指纹去重与其他源完全一致;
- **按主题装配**([services/pipeline_service.py](../../src/tradewinds/services/pipeline_service.py)):`Retriever.collect` 增加 `extra_clients` 参数;`PipelineService.run_topic` 每次执行时从 `feed_sources` 表加载该主题的自定义源,用 `feed_client_factory` 现场构造 `RssClient` 并入并发队列;
- **健康度机制**([services/feed_service.py](../../src/tradewinds/services/feed_service.py)):创建即探活(不可解析 → 422 `invalid_feed`,重复 → 409 `duplicate_feed`);beat 每日复检更新 `healthy/broken`;broken 源**仍然参与抓取**——失败被 Retriever 的单源降级机制标注,而不是静默消失,用户能在日志与 Feed 的活跃度里看到它。

## 踩过的坑

1. **Atom 的 link 要挑 `rel="alternate"`**:Atom 条目可能有多个 link(self/alternate/enclosure),无脑取第一个会拿到 feed 自链接;RSS 2.0 的 `<link>` 是纯文本节点,两者解析方式不同;
2. **日期解析双格式**:RSS 2.0 用 RFC822(`email.utils.parsedate_to_datetime`),Atom 用 ISO8601(`fromisoformat`),先试前者再试后者,都不行返回 None(条目保留,只是不参与时间窗过滤);
3. **探活不能占用共享限速器**:创建/复检是一次性管理请求,和管道抓取共用 `RateLimiter` 会互相拖慢,所以抽出了 `PassthroughLimiter`——顺带催生了 `Limiter` 协议,反而让请求助手与限速实现解耦了。

## 延伸阅读

- [RSS 2.0 规范](https://www.rssboard.org/rss-specification)
- [Atom Syndication Format (RFC 4287)](https://datatracker.ietf.org/doc/html/rfc4287)
- [Python Protocol: 结构化子类型](https://docs.python.org/3/library/typing.html#typing.Protocol)——本迭代 Limiter 协议的语法基础
