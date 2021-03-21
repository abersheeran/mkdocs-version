import os
import pathlib
import re
import shutil
import signal
import stat
import subprocess
import tempfile
import time
import typing

import click

from .version import get_all_tags, get_stable_tag

parse_version = lambda version: version


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
        current_version=parse_version(current_version)
    )

    f = lambda version: """
        <div class="version-select">
            <a href="/{version}/{current_link}">{version}</a>
        </div>
    """.format(
        version=parse_version(version),
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
                color: var(--md-primary-bg-color);
                background-color: var(--md-primary-fg-color);
                border: var(--md-primary-bg-color);
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
@click.option("--version", multiple=True, type=click.Choice(get_all_tags()))
@click.option("--min-version", type=click.Choice(get_all_tags()))
@click.option("--minor", is_flag=True, help="Generate only minor version documents")
@click.option(
    "--version-regex",
    default=r"(?P<version>.*)",
    help='Parse version, like: "v(?P<version>.*)"',
)
@click.option("--base-dir", default=".", help="The directory where the mkdocs.yml")
def build(
    version: typing.List[str],
    min_version: str,
    minor: bool,
    version_regex: str,
    base_dir: str,
):
    here = os.getcwd()
    dirpath = tempfile.TemporaryDirectory().name
    v_pattern = re.compile(version_regex)
    global parse_version
    parse_version = lambda v: (
        v if v in ("stable", "master") else v_pattern.match(v).group("version")
    )
    try:
        _all_tags = get_all_tags()
        tags = version or (
            _all_tags[_all_tags.index(min_version) :] if min_version else _all_tags
        )
        if minor:
            tags = {".".join(tag.split(".")[:-1]): tag for tag in tags}
        else:
            tags = {tag: tag for tag in tags}
        # 清理原始目录中的 site
        [_rmtree(os.path.join(here, base_dir, "site")) for _ in range(3)]
        # 复制整个项目到临时目录
        shutil.copytree(here, os.path.join(dirpath, "src"))
        os.chdir(os.path.join(dirpath, "src", base_dir))
        os.makedirs("site", exist_ok=True)
        # 构建当前分支最新的文档
        execute("mkdocs build --clean --site-dir site/master")
        append_version_selector("site/master", "master", tags)
        # 构建所有 tag 的文档
        for v, tag in tags.items():
            execute(f"git checkout {tag}")
            execute(f"mkdocs build --clean --site-dir site/{v.strip('v')}")
            append_version_selector(f"site/{parse_version(v)}", v, tags)
        # 构建 stable 版本的文档
        execute(f"git checkout {get_stable_tag()}")
        execute("mkdocs build --clean --site-dir site/stable")
        append_version_selector("site/stable", "stable", tags)
        # 编写首页跳转
        with open("site/index.html", "w+") as file:
            file.write('<meta http-equiv="refresh" content="0; url=/stable/" />')

        shutil.copytree(
            os.path.join(dirpath, "src", base_dir, "site"),
            os.path.join(here, base_dir, "site"),
        )
    finally:
        [_rmtree(dirpath) for _ in range(3)]
