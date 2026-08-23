# TURN 營運者 fork 部署手冊

本目錄是 `open-4wd-turn` 的就地操作手冊與 manifests；規範值及跨 repo 契約仍以
[open-4wd-specs 部署資訊](https://github.com/xjustloveux/open-4wd-specs/blob/master/%E9%83%A8%E7%BD%B2%E8%B3%87%E8%A8%8A/open-4wd-turn.md)
為權威。公版 workflow 不自動部署，營運者 fork 必須明示設定 `DEPLOY_ENABLED=true`。

## Kubernetes 與 secrets

營運者 fork 在 Actions secrets 設 `KUBE_CONFIG`、`TURN_SHARED_SECRET`，在 variables 設
`REALM`、`EXTERNAL_IP`、`TURN_URLS`。四個執行值任一缺席時 workflow fail closed；
`TURN_SHARED_SECRET` 必須與配對的 signaling 部署同值。渲染後的 `turnserver.conf` 含 shared
secret 真值，workflow 以 Secret `open4wd-turn-conf` 承載整份檔案並掛成
`/etc/coturn/turnserver.conf`，不使用 ConfigMap；repo 內 `k8s/secret.yaml` 只描述 TLS 鍵名
形狀，不承載正式值，也不由 workflow apply。

`hostNetwork: true` 與 relay 埠段會直接占用節點網路；多節點必須由營運者 overlay 以
nodeSelector 綁定持有 `EXTERNAL_IP` 的節點。部署後必須完成 STUN binding 與一次有認證的
TURN allocate smoke。

## 容器執行身分例外

公版 manifest 釘定 `coturn/coturn:4.14.0`，並設定 `allowPrivilegeEscalation: false`、移除
全部 Linux capabilities 與 `RuntimeDefault` seccomp。模板沒有跨平台可信的數字 UID，
因此不猜測 `runAsUser`，也不直接宣稱 `runAsNonRoot` 已成立。

正式部署前須檢查同一釘版映像：

```sh
docker image inspect coturn/coturn:4.14.0 --format '{{json .Config.User}}'
```

取得並驗證數字 UID/GID、完成 STUN 與 TURN allocate 後，營運者 overlay 才加入數字
`runAsUser`、`runAsGroup` 與 `runAsNonRoot: true`。無法驗證時應阻擋正式上線。

## TLS、網路與同步

TURN over TLS 由 coturn 終止；憑證掛載在 `/etc/coturn-tls`，不放入 configMap。防火牆需
開放 3478 UDP/TCP、選配 5349 TCP 與設定的 UDP relay 埠段。`denied-peer-ip` 預設封鎖
內網、loopback、link-local、CGNAT 與對應 IPv6 範圍，避免 relay 被用來打入內網。

營運者 fork 可定期同步公版：

```sh
git remote add upstream https://github.com/xjustloveux/open-4wd-turn.git
git fetch upstream
git merge upstream/master --allow-unrelated-histories
```

只有由 GitHub template 產生、與公版沒有共同祖先的副本需要第一次
`--allow-unrelated-histories`；後續同步使用一般受審查 merge。
