# open-4wd-turn

Open4WD 的 STUN／TURN 節點公版 Template。服務本體為第三方開源
[coturn](https://github.com/coturn/coturn)（BSD）；本 repo 不自 build 服務程式，只提供設定、
部署 manifests 與驗證工具。

> 本專案仍在開發中；Open4WD 主遊戲尚未正式公開。本 repo 先提供可審查、可自行部署的
> 服務模板，不代表官方營運中的節點。

公版 repo 不代表任何部署、零 secrets。deploy workflow 僅供營運者 fork 手動 opt in，並受
`DEPLOY_ENABLED == true` 閘保護。

## 快速開始

Linux 主機的單機 Docker Compose：

```sh
git clone https://github.com/xjustloveux/open-4wd-turn.git
cd open-4wd-turn/deploy
cp .env.example .env
set -a; . ./.env; set +a
envsubst < ../config/turnserver.conf.tmpl > ./turnserver.conf
docker compose up -d
```

至少替換 `TURN_SHARED_SECRET`、`REALM`、`EXTERNAL_IP`；樣本 secret 不可用於正式部署。
`envsubst` 不會自己讀 `.env`，因此前置 export 不可省略。

## 操作與部署權威

根 README 只保留最短成功路徑。Kubernetes、TLS、REST credential、shared-secret 輪替、
防火牆、容器身分例外、smoke 與同步流程見：

- [repo 就地部署手冊](deploy/README.md)
- [open-4wd-specs 部署權威](https://github.com/xjustloveux/open-4wd-specs/blob/master/%E9%83%A8%E7%BD%B2%E8%B3%87%E8%A8%8A/open-4wd-turn.md)
- [coturn 設定模板](config/turnserver.conf.tmpl)
- [Docker Compose](deploy/docker-compose.yml)
- [Kubernetes manifests](deploy/k8s/)

Signaling 簽發 TURN 短期憑證時，其 `TURN_SHARED_SECRET` 必須與 coturn 部署完全同值。
只自架 STUN 仍要給 coturn 高熵 secret，但不得交給任何 signaling；需要完全關閉 TURN 時，
由營運者在渲染後設定 `stun-only`。切勿留空或使用公開樣本值。

## 驗證

```sh
python scripts/comment_quality.py
python scripts/comment_quality_self_test.py
python scripts/comment_hook_runner_self_test.py
python -m unittest discover -s deploy -p 'test_*.py'
node --test scripts/prepare-graphify-release.test.mjs
```

## Open4WD 生態

- [主遊戲](https://github.com/xjustloveux/open-4wd)
- [規格](https://github.com/xjustloveux/open-4wd-specs)
- [Signaling Template](https://github.com/xjustloveux/open-4wd-signaling)
- [Pinning Template](https://github.com/xjustloveux/open-4wd-pinning)

## 貢獻、安全與授權

一般貢獻請使用 GitHub Issue／Pull Request；安全弱點請依
[Open4WD Security Reporting](https://github.com/xjustloveux/open-4wd-specs/blob/master/%E8%B3%87%E5%AE%89%E8%A6%8F%E7%AF%84.md#101-reporting)
私下回報，不要公開揭露細節。

本 repo 的設定模板與 manifests 採 [MIT](LICENSE) 授權；coturn 本體為第三方 BSD 軟體。
