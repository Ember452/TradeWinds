# JWT 在无状态 API 中的使用

## 这个知识点是什么

JWT(JSON Web Token)是一段自带签名的、可自验证的字符串,形如 `header.payload.signature`。服务端把"这个用户是谁、凭证何时过期"写进 payload,用只有自己知道的密钥签出 signature;之后每次请求客户端带上它,服务端**只需用密钥验签**就能确认身份,不需要查任何会话存储——这就是"无状态认证"。

类比:传统 session 像寄存行李——每次来商场都要去服务台核对寄存牌(查库);JWT 像盖了防伪章的门票——检票时看章是真的、日期没过期就放行,不用打电话回总部核实。

## TradeWinds 为什么需要它

TradeWinds 的 API 计划包含 REST + SSE 流式接口,未来还会多容器部署(api、worker 分离)。如果用服务端 session,就得引入 sticky session 或共享会话存储,增加状态与运维负担;JWT 验签只依赖配置里的密钥,任何容器都能独立验证,天然契合"单 VPS、多容器、无状态 API"的架构。

## 本项目怎么实现的

关键代码在 [core/security.py](../../src/tradewinds/core/security.py) 与 [services/auth_service.py](../../src/tradewinds/services/auth_service.py):

- **签发**:`create_access_token(user_id, ...)` 把 `sub`(user_id 字符串)、`iat`、`exp` 三个标准声明用 HS256 签名;密钥与有效期来自 `Settings`(`TRADEWINDS_JWT_SECRET` / `TRADEWINDS_JWT_EXPIRE_MINUTES`),不硬编码;
- **校验**:`decode_access_token` 统一捕获 `jwt.InvalidTokenError`(过期、签名不符、格式错误都是它的子类)转成业务异常 `AuthError` → 全局异常处理器输出 401 `{code: "auth_failed", message: ...}`,前端拿到统一错误体;
- **依赖注入**:`get_current_user`([api/deps.py](../../src/tradewinds/api/deps.py))解析 `Authorization: Bearer <token>`,验签后**仍从数据库加载用户**——JWT 本身无状态,但用户可能已被删除,回查一次保证凭证随时可吊销;
- **不泄露存在性**:登录失败不区分"用户不存在"与"密码错误",一律 401 同一错误体;注册邮箱冲突则用 409 语义(`AuthError` 默认 401、可覆盖 status_code),这是"错误码稳定、信息不外泄"的取舍;
- **测试**:JWT 相关全部纯单元测试(往返、过期、篡改、错密钥),不碰网络;全链路(注册→登录→带 token 访问→篡改 401)放在标记 `integration` 的集成测试里由 CI 跑真库。

## 踩过的坑

1. **jwt 过期异常的捕获范围**:容易写成只捕获 `ExpiredSignatureError`,漏掉签名不符等其他 `InvalidTokenError` 子类;统一捕获父类再转 `AuthError` 更稳。
2. **并发注册的兜底**:先 `SELECT` 再 `INSERT` 在并发下有窗口,靠 users 表 email 唯一约束兜底,捕获 `IntegrityError` 也转成 409 `AuthError`,避免 500。
3. **bcrypt 哈希是 `str` 还是 `bytes`**:`bcrypt.hashpw` 返回 bytes、接收 bytes,存库前要 `decode("utf-8")`,校验时再 `encode`,忘记转换会抛编码错误。

## 延伸阅读

- [RFC 8725:JWT 最佳实践](https://datatracker.ietf.org/doc/html/rfc8725)
- [PyJWT 文档](https://pyjwt.readthedocs.io/)
- [bcrypt 包文档](https://github.com/pyca/bcrypt/)
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
