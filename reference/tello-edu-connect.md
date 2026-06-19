# Tello EDU WiFiルーター接続手順書（ステーションモード設定・解除）

Tello EDUドローンは、標準のアクセスポイント（AP）モードに加えて、既存のWiFiルーターに接続する「ステーションモード（Station Mode）」をサポートしています。このモードを利用することで、PCと同じネットワークにTello EDUを参加させ、次回以降の起動時に自動的にWiFiルーターへ接続させることが可能です。

本手順書では、Tello EDUをWiFiルーターに接続する設定手順と、元の状態（APモード）に戻す解除手順について解説します。

## 前提条件

*   **対象機種:** Tello EDU（※通常のTelloではステーションモードはサポートされていません）
*   **必要なもの:**
    *   Tello EDU 本体およびバッテリー
    *   PC（Windows / Mac / Linux）
    *   接続先のWiFiルーター（SSIDとパスワードが判明していること）
    *   Python環境（Python 3.x）

## 1. WiFiルーター接続設定（ステーションモードへの移行）

Tello EDUをWiFiルーターに接続するためには、PCからUDP通信を用いてSDKモードを有効にし、ルーターのSSIDとパスワードを指定するコマンドを送信します。

### 手順1: PCをTello EDUに接続する
1.  Tello EDUの電源ボタンを1回押して起動します。
2.  ステータスインジケーターが点滅し、WiFiの準備ができるのを待ちます。
3.  PCのWiFi設定を開き、Tello EDUのネットワーク（例: `TELLO-XXXXXX`）に接続します。

### 手順2: 設定用Pythonスクリプトの作成
PC上で以下のPythonスクリプトを作成し、保存します（例: `setup_station_mode.py`）。
このスクリプトは、Tello EDUに対してSDKモードへの移行コマンドと、WiFiルーターへの接続コマンドを送信します。

```python
import socket
import time

# 接続先WiFiルーターの情報（ご自身の環境に合わせて変更してください）
WIFI_SSID = "あなたのWiFiルーターのSSID"
WIFI_PASSWORD = "あなたのWiFiルーターのパスワード"

# TelloのデフォルトIPとポート
tello_ip = '192.168.10.1'
tello_port = 8889
tello_address = (tello_ip, tello_port)

# UDPソケットの作成
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

try:
    # 1. SDKモードの有効化
    print("SDKモードを有効化しています...")
    sock.sendto('command'.encode('utf-8'), tello_address)
    time.sleep(2)
    
    # 2. ステーションモード（APコマンド）の送信
    ap_command = f"ap {WIFI_SSID} {WIFI_PASSWORD}"
    print(f"WiFiルーターへ接続コマンドを送信しています: {ap_command}")
    sock.sendto(ap_command.encode('utf-8'), tello_address)
    
    print("コマンド送信完了。Tello EDUは再起動し、指定されたWiFiルーターに接続を試みます。")
    
except Exception as e:
    print(f"エラーが発生しました: {e}")
finally:
    sock.close()
```

### 手順3: スクリプトの実行と接続確認
1.  スクリプト内の `WIFI_SSID` と `WIFI_PASSWORD` を実際のルーター情報に書き換えます。
2.  ターミナル（コマンドプロンプト）を開き、スクリプトを実行します。
    ```bash
    python setup_station_mode.py
    ```
3.  コマンドが成功すると、Tello EDUは自動的に再起動します。
4.  再起動後、Tello EDUはPCとの直接接続（APモード）を終了し、指定したWiFiルーターの子機として接続されます。
5.  PCのWiFi接続を、Tello EDUが接続したのと同じWiFiルーターに切り替えます。
6.  ルーターの管理画面やネットワークスキャンツール（Fingなど）を使用して、Tello EDUに割り当てられた新しいIPアドレスを確認します。

> **注意:** 以降の操作（Pythonからの制御など）は、この新しく割り当てられたIPアドレスに対して行う必要があります。

## 2. 次回起動時の動作について

ステーションモードの設定が完了すると、Tello EDUは次回起動時から**最初から設定されたWiFiルーターに接続**しようと試みます。

*   ルーターが見つかった場合、自動的にルーターのネットワークに参加します。
*   もしルーターが見つからない場合や接続に失敗した場合は、一定時間後に通常のAPモード（`TELLO-XXXXXX` を発信する状態）に戻る場合があります。

## 3. 設定解除手順（元のAPモードへの復元）

Tello EDUをWiFiルーターから切断し、工場出荷時の状態（自身がWiFiアクセスポイントとなるAPモード）に戻すには、本体の電源ボタンを使用したハードウェアリセットを行います。

### 手順1: Tello EDUの起動
1.  Tello EDUの電源ボタンを1回押して電源を入れます。
2.  ステータスインジケーターが点滅を始めるまで待ちます。

### 手順2: 電源ボタンの長押し（ファクトリーリセット）
1.  起動した状態で、**電源ボタンを約5秒間長押し**します。
2.  ステータスインジケーターのランプが消灯するまで押し続けてから、ボタンを離します。
3.  インジケーターが黄色く点滅し始めると、リセットが完了した合図です。

### 手順3: 復元の確認
1.  Tello EDUが再起動します。
2.  PCやスマートフォンのWiFi設定画面を開き、再び `TELLO-XXXXXX` というネットワークが表示されることを確認します。
3.  これでWiFiルーターへの接続設定が解除され、購入時の状態に戻りました。

---
**参考資料**
* Tello SDK 2.0 User Guide (Ryze Tech)
* TelloEDUをNode-REDからstation modeにして操作するメモ
* Qiita: TelloEduをWifiルータに接続して、TellloをWifi子機にする方法
