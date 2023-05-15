import os
from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext
import subprocess


# I have no idea what the fuck this is or why it's needed. It took
# literally hours to figure out how to just compile a damn binary for
# my Python package. This system couldn't be made more confusing if
# there were a dedicated committee on the task.
#
# If you know the magic incantations that one is supposed to use in
# order to get a compiled binary to show up on $PATH when a Python
# package is installed - please, fix this. But I've wasted enough of
# my life on this shit for now.
class my_build_ext(build_ext):
    def run(self):
        build_dir = self.get_finalized_command("build_py").build_lib  # type: ignore
        subprocess.run(
            ["go", "build", "."],
            cwd=build_dir,
            check=True,
        )
        os.remove(f"{build_dir}/go.mod")
        os.remove(f"{build_dir}/go.sum")
        os.remove(f"{build_dir}/curlinate.go")


setup(
    name="curlinate",
    version="0.0.1",
    packages=["."],
    ext_modules=[Extension("curlinate", sources=["curlinate.go"])],
    entry_points={
        "console_scripts": [
            "curlinate = curlinate_bullshit_to_work_around_setuptools_being_awful:main",
        ],
    },
    cmdclass={
        "build_ext": my_build_ext,
    },
    include_package_data=True,
)
