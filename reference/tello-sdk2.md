# Tello SDK 2.0 コマンド一次情報

Claude Code はコマンド文字列を**記憶で書かず、この表を参照すること**。
出典: Ryze Tech 公式「Tello SDK 2.0 User Guide」および djitellopy ドキュメント。

> 公式 PDF: https://dl-cdn.ryzerobotics.com/downloads/Tello/Tello%20SDK%202.0%20User%20Guide.pdf
> djitellopy: https://djitellopy.readthedocs.io/

## 通信仕様

| 用途 | 方向 | ポート |
| --- | --- | --- |
| コマンド送信 / 応答 | PC → Tello（UDP, IP 192.168.10.1 ※直 Wi-Fi 時） | 8889 |
| ステート受信 | Tello → PC（UDP） | 8890 |
| 映像ストリーム | Tello → PC（UDP, `streamon` 後） | 11111 |

- コマンドは UDP テキスト。多くは `ok` / `error` を返す。
- **`rc` は応答を返さない（fire-and-forget）。** ACK を待たないこと。
- コマンドが 15 秒間来ないと Tello は自動着陸する（本アプリのウォッチドッグはこれより
  短い猶予で安全側に倒す。`docs/safety.md` S-4 参照）。
- ステーションモードで自宅 LAN に接続した場合、IP は機体に割り当てられたものを使う
  （`.env` の `TELLO_IP`）。

## 制御コマンド

| コマンド | 意味 | 備考 |
| --- | --- | --- |
| `command` | SDK モードに入る | 最初に必ず送る |
| `takeoff` | 自動離陸 | 人間の明示操作を起点とする |
| `land` | 自動着陸 | |
| `streamon` | 映像ストリーム開始 | `Unknown command` ならファーム更新が必要 |
| `streamoff` | 映像ストリーム停止 | |
| `emergency` | モーター即時停止 | **落下する。通常の緊急着陸は `land` を使う** |
| `up x` | 上昇 x cm | x: 20–500 |
| `down x` | 下降 x cm | x: 20–500 |
| `left x` | 左移動 x cm | x: 20–500 |
| `right x` | 右移動 x cm | x: 20–500 |
| `forward x` | 前進 x cm | x: 20–500 |
| `back x` | 後退 x cm | x: 20–500 |
| `cw x` | 時計回り x 度 | x: 1–360 |
| `ccw x` | 反時計回り x 度 | x: 1–360 |
| `flip x` | x 方向にフリップ | x: l/r/f/b（追従用途では基本使わない） |
| `go x y z speed` | 座標 (x,y,z) へ speed(cm/s) で移動 | |
| `stop` | その場でホバリング | **いつでも有効** |
| `rc a b c d` | 4ch のリモート制御 | 各 -100〜100。連続送信向け。応答なし |
| `speed x` | 速度を x cm/s に設定 | x: 10–100 |

`rc a b c d` の各チャンネル:

| ch | 引数 | 意味 | 正の向き |
| --- | --- | --- | --- |
| a | 左右（roll） | left/right | 右 |
| b | 前後（pitch） | forward/backward | 前 |
| c | 上下（throttle） | up/down | 上 |
| d | 旋回（yaw） | rotate | 時計回り |

> 追従制御は基本的に `rc` で行い、ホバリングへのフォールバックは `rc 0 0 0 0`。

## 取得（Read）コマンド

| コマンド | 取得内容 |
| --- | --- |
| `battery?` | 電池残量（%） |
| `speed?` | 現在速度（cm/s） |
| `time?` | 飛行時間（s） |
| `wifi?` | Wi-Fi SNR |
| `sdk?` | SDK バージョン |
| `sn?` | シリアル番号 |
| `height?` | 高度（cm） |
| `tof?` | TOF 距離（cm） |
| `baro?` | 気圧高度（cm） |
| `attitude?` | IMU 姿勢（pitch/roll/yaw） |

## ステート（:8890 で常時受信）

`pitch:..;roll:..;yaw:..;vgx:..;...;bat:..;h:..;tof:..;` のような `;` 区切り文字列。
parse して電池残量・高度などを UI に反映する（djitellopy なら `get_*` で取得可）。

## EDU 限定コマンド

### ステーションモード（自宅 LAN 接続）

| コマンド | 意味 |
| --- | --- |
| `ap [SSID] [PASSWORD]` | 指定 AP に接続するステーションモードに切替（送信後リブート） |

> ステーションモードでは直 Wi-Fi 時の映像可否がファームに依存する場合がある。
> 接続後に `streamon` で映像が取れるかを初期検証で確認すること。
> Wi-Fi 設定をリセットしたい場合は、電源 ON 状態で電源ボタンを 5 秒長押し。

### ミッションパッド（EDU のみ・明るい環境が必要）

| コマンド | 意味 |
| --- | --- |
| `mon` | ミッションパッド検出を有効化 |
| `moff` | ミッションパッド検出を無効化 |
| `mdirection x` | 検出方向設定（`mon` の後）。0:下 / 1:前 / 2:両方 |

> 本プロジェクト初版ではミッションパッドはスコープ外（`README.md`）。将来の位置認識用に
> 情報のみ残す。

## djitellopy 対応関係（参考）

```python
from djitellopy import Tello

tello = Tello(host="192.168.1.50")   # ステーションモード機の IP を指定
tello.connect()                       # = "command"。以後 get_battery() などが使える
tello.streamon()                      # = "streamon"
frame = tello.get_frame_read().frame  # OpenCV の BGR ndarray
tello.send_rc_control(a, b, c, d)     # = "rc a b c d"（内部で送信間隔を調整）
tello.land()                          # = "land"
```

- `send_rc_control` は `TIME_BTW_RC_CONTROL_COMMANDS` 間隔で送信される。追従ループの
  レート制限（`docs/safety.md` S-2）と整合させること。
- ステーションモード接続・ミッションパッドは EDU のみ対応。
