# Yeah, I wrote my own fucking PEP517 build backend. Because after
# spending too many goddamn hours figuring out how to coax setuptools
# into installing binaries properly it turned out to be less work to
# reimplement the entire fucking thing. https://xkcd.com/1987/ seems
# to be as true as ever. And don't even get me started on trying to do
# it with Poetry, that managed to be even worse.
#
# I will say the folks who wrote https://peps.python.org/pep-0517/ did
# a great job though. That was the only sane document I read in this
# entire many-hour journey. And https://pypa-build.readthedocs.io/en/stable/
# is great too.

import base64
import hashlib
import os
import pathlib
import shlex
import shutil
import subprocess
import tarfile
import tempfile


VERSION = "0.0.1"
TAG = "py3-none-manylinux2014"


def _get_pkg_info():
    return (
        f"""
Metadata-Version: 2.1
Name: curlinate
Version: {VERSION}
Summary: Command-line utility and Python library to simplify TLS fingerprint forgery
Home-page: https://github.com/radian-software/curlinate
Author: Radian LLC
Maintainer: Radian LLC
Maintainer-email: contact+curlinate@radian.codes
License: MIT
Download-URL: https://pypi.python.org/pypi/curlinate
Project-URL: Bug Tracker, https://github.com/radian-software/curlinate/issues
Project-URL: Documentation, https://github.com/radian-software/curlinate
Project-URL: Source Code, https://github.com/radian-software/curlinate
Requires-Python: >=3.8,<4.0
            """.strip()
        + "\n"
    )


def build_sdist(sdist_directory, *_):
    with tempfile.TemporaryDirectory() as tmpdir:
        workdir = pathlib.Path(tmpdir) / f"curlinate-{VERSION}"
        workdir.mkdir()
        for fname in (
            "pyproject.toml",
            "pybuild/build.py",
            "curlinate.py",
            "curlinate.go",
            "go.mod",
            "go.sum",
        ):
            (workdir / fname).parent.mkdir(exist_ok=True, parents=True)
            shutil.copyfile(fname, workdir / fname)
        with open(workdir / "PKG-INFO", "w") as f:
            f.write(_get_pkg_info())
        tar_path = pathlib.Path(sdist_directory) / f"curlinate-{VERSION}.tar.gz"
        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(workdir, arcname=workdir.name)
        return tar_path.name


def walk(root: pathlib.Path):
    yield root
    if root.is_dir():
        for child in root.iterdir():
            yield from walk(child)


def hash_file(fname: os.PathLike):
    h = hashlib.sha256()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return base64.urlsafe_b64encode(h.digest()).decode().rstrip("=")


def build_wheel(wheel_directory, *_, editable=False):
    with tempfile.TemporaryDirectory() as tmpdir:
        workdir = pathlib.Path(tmpdir)
        dist_info = workdir / f"curlinate-{VERSION}.dist-info"
        dist_info.mkdir()
        scripts_dir = workdir / f"curlinate-{VERSION}.data" / "scripts"
        scripts_dir.mkdir(parents=True)
        if editable:
            with open(workdir / "curlinate_editable.pth", "w") as f:
                f.write(os.getcwd() + "\n")
            subprocess.run(["go", "build", "."], check=True)
            with open(scripts_dir / "curlinate", "w") as f:
                f.write(
                    f"""
#!/bin/sh
exec {shlex.quote(os.getcwd())}/curlinate "$@"
                """.strip()
                    + "\n"
                )
            (scripts_dir / "curlinate").chmod(0o755)
        else:
            shutil.copy("curlinate.py", workdir / "curlinate.py")
            subprocess.run(
                ["go", "build", "-o", scripts_dir / "curlinate", "."], check=True
            )
        with open(dist_info / "METADATA", "w") as f:
            f.write(_get_pkg_info())
        with open(dist_info / "WHEEL", "w") as f:
            f.write(
                f"""
Wheel-Version: 1.0
Generator: some horrifying bullshit you do not want to know about
Root-Is-Purelib: false
Tag: {TAG}
            """.strip()
                + "\n"
            )
        with open(dist_info / "RECORD", "w") as f:
            for item in walk(workdir):
                if not item.is_file():
                    continue
                if item.name == "RECORD":
                    continue
                f.write(
                    ",".join(
                        [
                            str(item.relative_to(workdir)),
                            "sha256=" + hash_file(item),
                            str(item.stat().st_size),
                        ]
                    )
                    + "\n"
                )
            f.write(f"{dist_info.relative_to(workdir)}/RECORD,,\n")
        zip_base = pathlib.Path(wheel_directory) / f"curlinate-{VERSION}-{TAG}"
        shutil.make_archive(str(zip_base), "zip", workdir)
        # No way to set the output filename for shutil, must rename
        # afterwards.
        zip_path = zip_base.with_name(zip_base.name + ".zip")
        whl_path = zip_base.with_name(zip_base.name + ".whl")
        zip_path.rename(whl_path)
        return whl_path.name


def build_editable(wheel_directory, *args, **kwargs):
    return build_wheel(wheel_directory, *args, **kwargs, editable=True)
