"""Generate a lock file from requirements.txt.
"""

__version__ = "0.1.0"

import dataclasses
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import typing

import packaging.utils
import packaging.version


@dataclasses.dataclass()
class Hash:
    alg: str
    val: str

    def __str__(self):
        return f"{self.alg}:{self.val}"


@dataclasses.dataclass()
class Candidate:
    name: str
    version: packaging.version.Version
    hashes: typing.List[Hash]
    parents: typing.List[str]


Candidates = typing.List[Candidate]


def _iter_candidate_lines(lines: typing.Iterator[str]) -> typing.Iterator[str]:
    curr = ""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.endswith("\\"):
            cont = True
            line = line[:-1]
        else:
            cont = False
        curr += line
        if not cont:
            if curr and curr[0] != "#":
                yield curr
            curr = ""


def _iter_parents(comment: str) -> typing.Iterator[str]:
    for parent in re.split(r", ", comment):
        if parent.startswith("-r"):
            yield ""
        else:
            yield packaging.utils.canonicalize_name(parent)


def _iter_candidates(lines: typing.Iterator[str]):
    for raw_line in _iter_candidate_lines(lines):
        hashes = []
        parsed = False
        line, _, comment = raw_line.partition("#")

        for part in line.split():
            if part.startswith("--hash="):
                alg, val = part.split("=", 1)[1].split(":", 1)
                hashes.append(Hash(alg, val))
            else:
                parsed = True
                name, vers = re.split(r"==", part, 1)
                version = packaging.version.Version(vers)
        assert parsed, f"No package parsed from {raw_line!r}"

        comment = comment.lstrip()
        if comment.startswith("via"):
            parents = set(_iter_parents(comment[3:].split("#", 1)[0].strip()))

        yield Candidate(name, version, hashes, parents)


def _read_candidates(path: pathlib.Path) -> Candidates:
    with tempfile.TemporaryDirectory() as td:
        output = pathlib.Path(td, "requirements.txt")
        args = [
            sys.executable,
            "-m",
            "piptools",
            "compile",
            "--allow-unsafe",
            "--generate-hashes",
            "--quiet",
            "--index-url",
            PYPI,
            "--output-file",
            str(output),
            str(path),
        ]
        subprocess.check_call(args)

        with output.open(encoding="utf-8") as f:
            candidates = list(_iter_candidates(f))

    return candidates


PYPI = "https://pypi.org/simple"


def _build_lock(candidates: Candidates) -> dict:
    lock: dict = {
        "sources": {"pypi": {"type": "simple", "url": PYPI}},
        "dependencies": {},
        "validations": {},
    }

    # Fill in Python distributions.
    for candidate in candidates:
        key = packaging.utils.canonicalize_name(candidate.name)
        lock["dependencies"][key] = {
            "python": {
                "name": candidate.name,
                "version": str(candidate.version),
                "source": "pypi",
            },
            "dependencies": {},
        }
        lock["validations"][key] = [str(h) for h in candidate.hashes]

    # Fill in dependency info.
    for candidate in candidates:
        key = packaging.utils.canonicalize_name(candidate.name)
        for parent in candidate.parents:
            if parent not in lock["dependencies"]:
                lock["dependencies"][parent] = {"dependencies": {}}
            lock["dependencies"][parent]["dependencies"][key] = None

    return lock


def _write_lock(data, path: pathlib.Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(
            data, f, ensure_ascii=False, indent=4, sort_keys=True,
        )


ROOT = pathlib.Path(__file__).resolve().parent


def main(argv=None):
    candidates = _read_candidates(ROOT.joinpath("requirements.in"))
    data = _build_lock(candidates)
    _write_lock(data, ROOT.joinpath("pyproject.lock.json"))


if __name__ == "__main__":
    main()
