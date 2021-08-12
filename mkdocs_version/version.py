from subprocess import check_output
from string import digits
from itertools import takewhile
from typing import List

from cool import F


def get_current_branch() -> str:
    output: bytes = check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    return output.decode("utf8").strip()


def get_all_tags() -> List[str]:
    output: bytes = check_output(["git", "tag"])
    return (
        output.decode("utf8").strip().splitlines()
        | F(
            sorted,
            ...,
            key=lambda tag: int(
                "".join(
                    takewhile(lambda x: x in digits, tag.split(".")[2])
                )  # 有可能出现 rc\beta\alpha
            ),
        )
        | F(sorted, ..., key=lambda tag: int(tag.split(".")[1]))
        | F(sorted, ..., key=lambda tag: int(tag.lstrip("v").split(".")[0]))
    )


def get_stable_tag() -> str:
    return list(
        get_all_tags()
        | F(
            filter,
            lambda tag: (
                (tag.split(".")[2] | F(takewhile, lambda x: x in digits) | F("".join))
                == tag.split(".")[2]
            ),
        )
    )[-1]
