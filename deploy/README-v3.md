# TradingAgents 3.0 — jiechic 的 GHCR / Portainer 部署

## 构建和发布

源码来自上游 v3.0 提交 `51060a7682cf51810b4bc3a704829438d18cd8dc`，位于本 fork 的 `release/v3.0` 分支。
当前为 **v3.0.0-beta.4 测试版**。上游的 VERSION / package.json 与 BUILD_INFO 曾不一致，本 fork 已统一修正。

`VERSION` 是发布版本的唯一来源。前端构建从该文件注入显示版本，后端读取 VERSION 和镜像生成的 BUILD_INFO，OCI 镜像标签也使用同一版本。
向 `release/v3.0` 推送或合并代码会自动运行 GitHub Actions；也可以手动运行 **Publish TradingAgents versioned images**，选择 `release/v3.0`。
流程先检查各处版本一致，再在原生 AMD64 / ARM64 runner 构建，验证后端导入、前端在后端离线时仍能启动，再运行完整临时数据库、代理恢复、版本接口和登录检查。全部通过后才发布多架构版本标签。

下次合并上游新版本后，在同一个待发布提交中执行，例如：

```bash
python3 tools/release_version.py --set 3.0.0-beta.5
python3 tools/release_version.py
```

该命令同步 VERSION、Python/前端包信息、BUILD_INFO、部署模板和本指南。提交这些变更并合并到 `release/v3.0`，Actions 就会发布 `v3.0.0-beta.5`。版本号必须与实际合入的上游版本相符；同一上游版本的自有修订可使用 `3.0.0-beta.4` 之后的新预发布编号，明确记录对应上游提交。
已有版本绑定构建提交，不会被不同提交覆盖；不发布 `latest`、`v3` 等含糊标签。后续代码修改需要递增版本，不能把 beta 自动当成正式版。
默认 main 仍保留旧版应用；请在 release/v3.0 分支运行新版本工作流。

镜像：

- `ghcr.io/jiechic/tradingagents-v3-backend:v3.0.0-beta.4`
- `ghcr.io/jiechic/tradingagents-v3-frontend:v3.0.0-beta.4`

这是独立镜像名，不覆盖原来的 v1.0.1。不要改旧 Stack 的镜像来直接升级。
已验证两个镜像当前可匿名拉取，Portainer 无需额外 GHCR 凭据。若你以后把包改为私有，需要在 Portainer 的 Registries 中添加 GHCR 凭据（用户名 jiechic，Token 具备 read:packages），不要将 Token 写入 Stack。

上游 3.0 的应用层含专有许可条款，使用及分发范围请以仓库 LICENSE 为准。

## 首次部署：并行新实例

1. 在 TrueNAS 创建新目录 `/mnt/Data/Application/TradingAgents-CN-v3/data`，经 NFS 导出，并允许 `10.10.3.50` 读写。不要使用旧版 backend `/app` 目录；旧代码会覆盖镜像代码。
2. Portainer 创建新 Stack：`tradingagents-v3`，粘贴 `deploy/portainer-v3.yml`。
3. 在 Stack 的 Environment variables 填入 `deploy/portainer-v3.env.example` 中五项必需变量。可分别运行 `openssl rand -hex 24` 生成不同值。数据库密码使用十六进制，避免 Mongo URI 中特殊字符转义问题。管理员密码是 ADMIN_PASSWORD，不是 JWT_SECRET。
4. 确认宿主机 19111、19112 没被占用后部署。新数据库使用独立本地卷，数据不会混入旧 MongoDB 4.4；Redis 也独立。
5. 新 Stack 前后端连接普通 access bridge，数据库连接 internal bridge；不要删除 access 网络，否则无法发布宿主机端口。仅前后端注册 Consul。
6. 在 AdGuard Home 增加 `tradingagents-v3.jiechic.org → 10.10.3.1`（已有适用的通配记录则无需新增）。
7. Consul 查看 `docker-portainer-tradingagents-v3-backend` / `docker-portainer-tradingagents-v3-frontend`。预期后端 `10.10.3.50:19111`，前端 `10.10.3.50:19112`。
8. 打开 https://tradingagents-v3.jiechic.org，使用 admin / ADMIN_PASSWORD 登录。新空库会执行初始化。
9. 配置大模型密钥、行情数据，测试登录、模型配置、一次真实分析、实时进度及报告读取。构建验证不等于这些功能已在你的真实数据上验收。

后端健康检查初次启动允许较长时间。若失败，先查看 backend 日志与 `/api/health`，不要直接关闭检查。独立 worker 不在此最小部署中，后端当前包含线程池 worker；有独立 worker 需求时再按功能验证。

## 数据与网络

- MongoDB 8 使用独立 Docker 本地卷；不要将它指向 MongoDB 4.4 的原始数据目录。
- NFS 只挂载 `/app/data`，代码留在镜像中。
- `/app/logs`、`/app/results` 使用独立本地卷，若有集中存储需求，可单独迁移这些目录。
- NFS DNS 使用 `infra-truenas-nfs.service.consul`，解析在 Docker 宿主机进行。确认实际 mount 的 `addr=`，不能仅凭 Compose 域名判断连接路径。
- MongoDB、Redis 不发布端口；后端有普通 access 网络用于下载行情和调用模型。
- 保留原有旧 Stack 与数据卷。不要执行 `docker compose down -v`。

## 可选：在新实例验证旧数据迁移

1. 先停止旧版前后端的写入任务，使用 MongoDB 4.4 容器的 mongodump 对 `tradingagentscn` 做一致性逻辑备份；同时保留 TrueNAS 快照与旧 Stack 文本。
2. 仅在新实例的副本上测试。停止新前后端，把备份恢复进 MongoDB 8 的 `tradingagentscn_v3` 数据库；不要覆盖旧库，也不要复制旧数据库物理文件。
3. 旧 MongoDB 4.4 到 MongoDB 8 的跨版本逻辑恢复，需要用匹配工具试验并核对索引、用户和数据类型；失败时不要强行忽略错误，也不在现有生产库上试。
4. 恢复完成后启动新版后端。它会执行 `migrations`；核对完整启动日志，并运行 `python -m migrations.cli status` 检查迁移状态。源代码会记录并跳过部分迁移错误，因此仅“容器 running”不足以表示迁移完成。
5. 验证原账号、配置、历史报告和真实分析。如未通过，继续用旧版，保留副本供排查。

## 切换正式域名与回退

验收后，在旧 Stack 停止入口服务，再将新版前后端的 SERVICE_*_TAGS 中测试域名替换为原来的 `tradingagents.cn.jiechic.org`；ALLOWED_ORIGINS 也同步替换。
旧版相同域名路由必须退出，避免新旧配置争抢请求。
该原域名不被 `*.jiechic.org` 覆盖，现有 cloudflare resolver 会按域名申请证书，应验证证书结果。

回退时停止新版前后端，恢复旧 Stack 的入口；旧数据库保持原样。升级后新产生的数据不会自动合并回旧数据库。


## 故障处理

- 后端出现 `JWT_SECRET is still the default value`：在 Portainer Stack 环境变量中填写不同的随机 JWT_SECRET / CSRF_SECRET，并确认 backend.environment 引用了它们，然后重新部署。仅重启旧容器不会更新环境变量；不要关闭生产密钥检查。
- 新镜像前端使用 Docker DNS 按请求解析 backend，后端离线时页面仍可打开，API 暂时返回 502，恢复后自动重连。
- 前后端必须共享普通 access 网络，backend 另接 internal 数据库网络。仅 internal 网络会导致宿主机映射端口不可用。
- 首次 NFS 挂载出现 no such file or directory：先在 TrueNAS 创建上述导出目录并授权；Compose 不会替你创建远端目录。

## 误发正式版的处理

旧 `v3.0.0` 是误标记，已由 beta.4 镜像替代。专用手动工作流 **Remove mistaken v3.0.0 package versions** 仅清理两个包里的误标正式版及其架构标签；先确认 beta.4 已存在，并拒绝删除与其他标签共享的 digest。
删除远端镜像版本不会更新已运行的容器。请将 Stack 镜像改为本指南 beta.4 标签，并重新拉取部署。
