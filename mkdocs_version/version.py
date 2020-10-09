from typing import List
from subprocess import check_output


def get_current_branch() -> str:
    output: bytes = check_output("git rev-parse --abbrev-ref HEAD")
    return output.decode("utf8").strip()


def get_all_tags() -> List[str]:
    output: bytes = check_output("git tag")
    return sorted(
        sorted(
            sorted(
                output.decode("utf8").strip().splitlines(),
                key=lambda tag: int(tag.split(".")[2]),
            ),
            key=lambda tag: int(tag.split(".")[1]),
        ),
        key=lambda tag: int(tag.lstrip("v").split(".")[0]),
    )


def get_stable_tag() -> str:
    return get_all_tags()[-1]
