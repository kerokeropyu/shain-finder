# 社員検索ツール (shain-finder)

氏名・支店で社員を検索し、結果セルをクリックしてクリップボードにコピーできるデスクトップアプリ。

## セットアップ

### 1. 仮想環境の作成と依存パッケージのインストール

```bash
uv venv
uv pip install -r requirements.txt
```

### 2. 接続設定ファイルの作成

`config.ini.example` をコピーして `config.ini` を作成し、実環境の値を記入する。

```bash
copy config.ini.example config.ini
```

```ini
[oracle]
host     = <DBホスト名またはIPアドレス>
port     = <ポート番号（通常1521）>
service  = <サービス名>
user     = <ユーザー名>
password = <パスワード>

[app]
company_code = <会社コード>
```

> `config.ini` には認証情報が含まれるため `.gitignore` に追加済み。絶対にコミットしないこと。

### 3. 起動

```bash
uv run main.py
```

または仮想環境をアクティベートして:

```bash
python main.py
```

## テーブル・カラム名について

`db.py` 内の SQL に使用しているテーブル名・カラム名はすべて**架空のもの**。  
実環境に合わせて `db.py` の以下の箇所を書き換えること。

| 架空の名前 | 置き換え先 |
|---|---|
| `mst_employees` | 実際の社員マスタテーブル名 |
| `mst_dept_members` | 実際の所属マスタテーブル名 |
| `mst_branches` | 実際の支店マスタテーブル名 |
| `employee_id`, `employee_name`, ... | 実際のカラム名 |

## python-oracledb のモードについて

デフォルトは **thin モード**（Oracle Instant Client 不要）。  
接続できない場合は thick モードが必要な可能性がある。その場合は `db.py` の `_connect()` を以下のように変更する。

```python
import oracledb
oracledb.init_oracle_client()  # Instant Client のパスが必要な場合は lib_dir= を指定
```
