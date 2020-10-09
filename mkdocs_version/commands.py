import os
import stat
import shutil
import time
import tempfile
import typing
import pathlib
import subprocess
import signal

import click

from .version import get_all_tags, get_stable_tag


@click.group()
def main():
    pass


def execute(*commands: str) -> None:
    process = subprocess.Popen(" ".join(commands), cwd=os.getcwd(), shell=True)

    def sigterm_handler(signo, frame):
        process.terminate()
        process.wait()

    signal.signal(signal.SIGTERM, sigterm_handler)

    while process.poll() is None:
        time.sleep(0.1)

    exit_code = process.poll()
    if exit_code != 0:
        raise SystemExit(exit_code)


def _rmtree(dirpath: str):
    for root, dirs, files in os.walk(dirpath, topdown=False):
        for name in files:
            filename = os.path.join(root, name)
            os.chmod(filename, stat.S_IWUSR)
            try:
                os.remove(filename)
            except OSError:
                pass
        for name in dirs:
            try:
                os.rmdir(os.path.join(root, name))
            except OSError:
                pass
    try:
        os.rmdir(dirpath)
    except OSError:
        pass


def generate_version_selector(
    current_version: str, versions: typing.List[str], current_link: str
) -> str:
    page = '<div id="version-select">'
    page += """
    <div class="version-select">
        Version: {current_version}
    </div>
    """.format(
        current_version=current_version.strip("v")
    )

    f = lambda version: """
        <div class="version-select">
            <a href="/{version}/{current_link}">{version}</a>
        </div>
    """.format(
        version=version.strip("v"),
        current_link=current_link.lstrip("/"),
    )
    page += "".join(
        reversed(list(map(f, versions)) + list(map(f, ("stable", "master"))))
    )

    page += """
        <style>
            #version-select {
                position: fixed;
                bottom: 10vh;
                right: 10vw;
                max-width: 80vw;
                max-height: 50vh;
                font-size: 16px;
                display: flex;
                flex-direction: row-reverse;
                flex-wrap: wrap-reverse;
            }

            .version-select {
                display: none;
                padding: 0.5em;
                color: aliceblue;
                background-color: rgb(64 81 181);
                border: aliceblue;
                border-radius: 5px;
                margin: 10px;
                white-space: nowrap;
            }

            #version-select div:first-of-type {
                display: block;
            }

            #version-select:hover .version-select {
                display: block;
            }
        </style>
        """
    page += "</div>"
    return page


def append_version_selector(
    dirpath: str, current_version: str, versions: typing.List[str]
) -> None:
    dirpath = pathlib.Path(dirpath)
    for html_path in dirpath.glob("**/*.html"):
        current_link = str(html_path.relative_to(dirpath)).replace("\\", "/")
        if current_link.endswith("index.html"):
            current_link = current_link[: -len("index.html")]

        html_path.write_text(
            html_path.read_text("utf8").replace(
                "</body>",
                generate_version_selector(current_version, versions, current_link)
                + "\n</body>",
            ),
            encoding="utf8",
        )


@main.command(help="Build multi version docs by mkdocs")
@click.option(
    "-V",
    "--version",
    multiple=True,
    type=click.Choice(get_all_tags()),
)
@click.option("--min-version", type=click.Choice(get_all_tags()))
@click.option("--minor", is_flag=True)
def build(version: typing.List[str], min_version: str, minor: bool):
    dirpath = tempfile.TemporaryDirectory().name
    try:
        here = os.getcwd()
        _all_tags = get_all_tags()
        tags = version or (
            _all_tags[_all_tags.index(min_version) :] if min_version else _all_tags
        )
        if minor:
            tags = {".".join(tag.split(".")[:-1]): tag for tag in tags}
        else:
            tags = {tag: tag for tag in tags}
        # 清理原始目录中的 site
        [_rmtree(os.path.join(here, "site")) for _ in range(3)]
        # 复制整个项目到临时目录
        shutil.copytree(here, os.path.join(dirpath, "src"))
        os.chdir(os.path.join(dirpath, "src"))
        os.makedirs("site", exist_ok=True)
        # 构建当前分支最新的文档
        execute("mkdocs build --clean --site-dir site/master")
        append_version_selector("site/master", "master", tags)
        # 构建所有 tag 的文档
        for v, tag in tags.items():
            execute(f"git checkout {tag}")
            execute(f"mkdocs build --clean --site-dir site/{v.strip('v')}")
            append_version_selector(f"site/{v.strip('v')}", v, tags)
        # 构建 stable 版本的文档
        execute(f"git checkout {get_stable_tag()}")
        execute("mkdocs build --clean --site-dir site/stable")
        append_version_selector("site/stable", "stable", tags)
        # 编写首页跳转
        with open("site/index.html", "w+") as file:
            file.write('<meta http-equiv="refresh" content="0; url=/stable/" />')

        shutil.copytree(
            os.path.join(dirpath, "src", "site"), os.path.join(here, "site")
        )
    finally:
        [_rmtree(dirpath) for _ in range(3)]
