"""把项目发布到 GitHub：创建仓库 → 推送 main → 建 Release 并上传 exe / apk。

设计要点
--------
- **令牌不出现在命令行/日志里**：从 git credential manager（``git credential fill``）读取，
  只用内存中的变量；脚本只打印账号与结果。
- **幂等**：仓库已存在则复用；Release 已存在则复用；同名资产已存在则先删除再上传。
- 只依赖标准库（urllib），不需要 requests。

用法::

    py tools/publish_github.py                       # 用默认参数发布
    py tools/publish_github.py --tag v1.2.0 --dry-run  # 只打印将要做什么

发布产物（默认）::

    dist/江苏高职提前招生.exe   → Release 附件
    dist/江苏高职提前招生.apk   → Release 附件
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPO = "jiangsu-vocational-early-admission"
DEFAULT_TAG = "v1.2.0"
DEFAULT_TITLE = "v1.2.0 — 首个公开版本"
DEFAULT_ASSETS = (
    PROJECT_ROOT / "dist" / "江苏高职提前招生.exe",
    PROJECT_ROOT / "dist" / "江苏高职提前招生.apk",
)
API = "https://api.github.com"
UPLOADS = "https://uploads.github.com"
USER_AGENT = "jsvoc-nav-publish"

RELEASE_NOTES = """## 江苏高职提前招生院校导航器 —— 首个公开版本

整理好的江苏省高职（专科）院校**提前招生**信息导航工具，提供 Windows 与 Android 两个独立版本。

### 下载哪个？

| 文件 | 平台 | 说明 |
| --- | --- | --- |
| `JiangsuVocationalEarlyAdmission-Windows.exe` | Windows 10/11 | 单文件绿色版，**双击即用**，无需安装 Python |
| `JiangsuVocationalEarlyAdmission-Android.apk` | Android 7.0+ | 原生应用（Kotlin + Jetpack Compose） |

> 两个版本**共用同一份数据**，功能与信息完全一致。下载后可直接重命名为中文名。

### 数据现状（2026 年度）

- 收录 **84 所**省内高职（专科）院校（公办 62 / 民办 22）
- 每所院校尽可能提供 7 类入口：提前招生简章/栏目、招生简章/章程、招生计划、录取结果、考试资料、学校官网、招生网
- 58 所可计算「到常州武进洛阳高级中学」的直线距离；缺坐标的显示「暂无距离数据」，不用猜测值填充

### 主要功能

- 搜索（校名 / 简称 / 城市 / 关键词）、城市与公办民办筛选、五种排序
- 详情页一键打开各类官方入口（用系统默认浏览器）
- 百度地图：生成「参照点 → 该校」驾车路线；缺坐标时退化为地点搜索
- 直线距离（Haversine），明确标注「直线距离」而非驾车距离
- 收藏、最近浏览、复制学校信息；深色模式跟随系统
- **数据与程序分离**：替换 `data/schools.json` 即可更新数据，无需重新打包

### 重要说明

- 数据为公开信息整理并逐校核验，但**本软件不是官方招生平台**，
  招生政策、计划与录取规则请以**江苏省教育考试院及各院校官方发布**为准；
- 坐标来自 OpenStreetMap（ODbL 许可），非官方数据，仅供参考；
- 少数院校的提前招生入口是第三方转载页，数据中已明确标注。
"""

#: 资产名用 ASCII：GitHub 对 URL 里非 ASCII 的 name 参数处理不稳定，
#: 会出现资产名变成 default.exe 的情况。中文说明放到 label 里。
ASCII_ASSET_NAMES = {
    "江苏高职提前招生.exe": "JiangsuVocationalEarlyAdmission-Windows.exe",
    "江苏高职提前招生.apk": "JiangsuVocationalEarlyAdmission-Android.apk",
}
ASSET_LABELS = {
    "江苏高职提前招生.exe": "Windows 10/11 单文件绿色版，双击即用",
    "江苏高职提前招生.apk": "Android 7.0+ 原生应用",
}


# --------------------------------------------------------------------- 基础
def get_token() -> str:
    """从 git credential manager 取 GitHub 令牌（不打印）。"""
    proc = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    for line in proc.stdout.splitlines():
        if line.startswith("password="):
            return line[len("password=") :]
    raise SystemExit("未找到缓存的 GitHub 凭据，请先执行一次 git push 完成登录")


def request(
    method: str,
    url: str,
    token: str,
    *,
    payload: dict | None = None,
    raw_body: bytes | None = None,
    content_type: str | None = None,
    expect: tuple[int, ...] = (200, 201, 204),
) -> tuple[int, dict | list | None]:
    """发一个 API 请求，返回 (状态码, JSON)；不抛异常，由调用方判断。"""
    data = raw_body
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif content_type:
        headers["Content-Type"] = content_type

    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, (json.loads(body) if body.strip() else None)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"message": body[:300]}
        if exc.code in expect:
            return exc.code, parsed
        print(f"  ! HTTP {exc.code} {method} {url}: {parsed.get('message') if isinstance(parsed, dict) else parsed}")
        return exc.code, parsed


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        ["git", *args], cwd=PROJECT_ROOT, capture_output=True, text=True, encoding="utf-8"
    )
    if check and proc.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} 失败：{proc.stderr.strip()[:400]}")
    return proc


# --------------------------------------------------------------------- 步骤
def ensure_repo(token: str, owner: str, repo: str, description: str, private: bool, dry: bool) -> None:
    status, data = request("GET", f"{API}/repos/{owner}/{repo}", token, expect=(200, 404))
    if status == 200:
        print(f"[1/4] 仓库已存在：{owner}/{repo}")
        return
    print(f"[1/4] 创建仓库 {owner}/{repo}（{'私有' if private else '公开'}）")
    if dry:
        return
    status, data = request(
        "POST",
        f"{API}/user/repos",
        token,
        payload={
            "name": repo,
            "description": description,
            "private": private,
            "has_issues": True,
            "has_wiki": False,
            "auto_init": False,
        },
    )
    if status != 201:
        raise SystemExit(f"创建仓库失败：{data}")
    print(f"      OK 已创建 {data.get('html_url')}")


def push_main(owner: str, repo: str, dry: bool) -> None:
    remote = f"https://github.com/{owner}/{repo}.git"
    print(f"[2/4] 推送 main → {remote}")
    if dry:
        return
    existing = git("remote", check=False).stdout
    if "origin" in existing.split():
        git("remote", "set-url", "origin", remote)
    else:
        git("remote", "add", "origin", remote)
    git("push", "-u", "origin", "main")
    print("      OK 推送完成")


def ensure_release(token: str, owner: str, repo: str, tag: str, title: str, body: str, dry: bool) -> str:
    print(f"[3/4] 创建 Release {tag}")
    status, data = request("GET", f"{API}/repos/{owner}/{repo}/releases/tags/{tag}", token, expect=(200, 404))
    if status == 200 and isinstance(data, dict):
        print("      已存在，更新说明并复用")
        if not dry:
            request(
                "PATCH",
                f"{API}/repos/{owner}/{repo}/releases/{data['id']}",
                token,
                payload={"name": title, "body": body},
            )
        return data["upload_url"]
    if dry:
        return ""
    status, data = request(
        "POST",
        f"{API}/repos/{owner}/{repo}/releases",
        token,
        payload={
            "tag_name": tag,
            "name": title,
            "body": body,
            "draft": False,
            "prerelease": False,
        },
    )
    if status != 201 or not isinstance(data, dict):
        raise SystemExit(f"创建 Release 失败：{data}")
    print(f"      OK {data.get('html_url')}")
    return data["upload_url"]


def upload_assets(
    token: str,
    owner: str,
    repo: str,
    tag: str,
    upload_url: str,
    assets: tuple[Path, ...],
    dry: bool,
) -> None:
    base = upload_url.split("{")[0]

    if dry:
        for path in assets:
            print(f"[4/4] 将上传 {path.name}")
        return

    # 先清空该 Release 下的旧资产：既保证可重复执行，也避免残留历史错误命名的文件
    status, existing = request(
        "GET", f"{API}/repos/{owner}/{repo}/releases/tags/{tag}", token, expect=(200,)
    )
    if isinstance(existing, dict):
        for asset in existing.get("assets", []):
            request(
                "DELETE",
                f"{API}/repos/{owner}/{repo}/releases/assets/{asset['id']}",
                token,
                expect=(204,),
            )
            print(f"      已删除旧资产：{asset.get('name')}")

    for path in assets:
        if not path.exists():
            print(f"[4/4] 跳过（文件不存在）：{path}")
            continue
        name = path.name
        asset_name = ASCII_ASSET_NAMES.get(name, name)
        label = ASSET_LABELS.get(name, "")
        size_mb = path.stat().st_size / 1024 / 1024
        print(f"[4/4] 上传 {name} → 资产名 {asset_name}（{size_mb:.1f} MB）")

        boundary = "----jsvocnav" + uuid.uuid4().hex
        mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
        # multipart 里的 filename 必须是纯 ASCII：非 ASCII 会被 GitHub 降级成 default.exe。
        # 真正的资产名（可含中文）通过 ?name= 指定。
        safe_filename = "upload" + (path.suffix or ".bin")
        head = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{safe_filename}"\r\n'
            f"Content-Type: {mime}\r\n\r\n"
        ).encode("utf-8")
        tail = f"\r\n--{boundary}--\r\n".encode("utf-8")
        body = head + path.read_bytes() + tail

        url = f"{base}?" + urllib.parse.urlencode({"name": asset_name, "label": label})
        status, data = request(
            "POST",
            url,
            token,
            raw_body=body,
            content_type=f"multipart/form-data; boundary={boundary}",
        )
        if status in (200, 201):
            print(
                "      OK 上传成功："
                + (data.get("browser_download_url") if isinstance(data, dict) else "")
            )
        else:
            print(f"      ! 上传失败（HTTP {status}）")


# --------------------------------------------------------------------- 主流程
def main() -> int:
    parser = argparse.ArgumentParser(description="发布到 GitHub")
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--tag", default=DEFAULT_TAG)
    parser.add_argument("--title", default=DEFAULT_TITLE)
    parser.add_argument("--description", default="江苏省高职院校提前招生信息导航（Windows 桌面版 + Android 原生版）")
    parser.add_argument("--private", action="store_true", help="创建私有仓库（默认公开）")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--assets", nargs="*", type=Path, default=list(DEFAULT_ASSETS))
    args = parser.parse_args()

    token = get_token()
    status, user = request("GET", f"{API}/user", token)
    if status != 200 or not isinstance(user, dict):
        raise SystemExit("令牌无效或网络不可用")
    owner = user["login"]
    print(f"账号：{owner}　仓库：{args.repo}　标签：{args.tag}")
    print()

    ensure_repo(token, owner, args.repo, args.description, args.private, args.dry_run)
    push_main(owner, args.repo, args.dry_run)
    upload_url = ensure_release(
        token, owner, args.repo, args.tag, args.title, RELEASE_NOTES, args.dry_run
    )
    if upload_url:
        upload_assets(token, owner, args.repo, args.tag, upload_url, tuple(args.assets), args.dry_run)

    print()
    print(f"完成：https://github.com/{owner}/{args.repo}")
    print(f"发布页：https://github.com/{owner}/{args.repo}/releases/tag/{args.tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
