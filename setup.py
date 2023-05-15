from os import (
    remove as use_shitty_workaround_to_delete_file_that_should_not_be_here_in_the_first_place,
)
from os.path import exists as use_horrifyingly_janky_and_unreliable_file_existence_check
from setuptools import setup as do_various_packaging_related_shit_that_may_or_not_work
from setuptools.command.build_py import (
    build_py as random_fucking_internal_class_that_we_have_to_import,
)
from subprocess import (
    run as run_a_single_shell_command_which_is_all_this_entire_pile_of_shit_should_be_doing,
)


# I have no idea what the fuck is going on here or why it's needed. It
# took literally hours to figure out how to just compile a damn binary
# for my Python package. This system couldn't be made more confusing
# if there were a dedicated committee on the task.
#
# If you know the magic incantations that one is *supposed* to use in
# order to get a compiled binary to show up on $PATH when a Python
# package is installed - please, fix this. But I've wasted enough of
# my life on this shit for now.
class incredibly_fucking_scuffed_build_subclass(
    random_fucking_internal_class_that_we_have_to_import
):
    def run(self):
        # Have to call the superclass first and install everything so
        # we can clean up the mess after it returns, instead of just
        # compiling shit in the source directory like a normal package
        # manager
        super().run()
        # Execute compilation command in the wrong directory because
        # otherwise the artifacts get ignored
        run_a_single_shell_command_which_is_all_this_entire_pile_of_shit_should_be_doing(
            ["go", "build", "."],
            check=True,
            cwd=self.build_lib,
        )
        # self.editable_mode doesn't exist in older setuptools so...
        awful_fucking_heuristic_of_whether_editable_mode_is_enabled = (
            use_horrifyingly_janky_and_unreliable_file_existence_check(
                f"{self.build_lib}/.git"
            )
        )
        # Have to avoid deleting files out of the source repository in
        # case of editable install
        if not awful_fucking_heuristic_of_whether_editable_mode_is_enabled:
            # Cannot for the life of me figure out how to just have
            # any modicum of actual control over what files are copied
            # in the first place, have to manually delete them
            # afterwards
            for filename_from_manual_list_that_will_probably_get_out_of_date in (
                "go.mod",
                "go.sum",
                "curlinate.go",
            ):
                use_shitty_workaround_to_delete_file_that_should_not_be_here_in_the_first_place(
                    f"{self.build_lib}/{filename_from_manual_list_that_will_probably_get_out_of_date}"
                )


do_various_packaging_related_shit_that_may_or_not_work(
    name="curlinate",
    version="0.0.1",
    packages=["."],
    entry_points={
        "console_scripts": [
            "curlinate = curlinate_bullshit_to_work_around_setuptools_being_awful:main",
        ],
    },
    cmdclass={
        "build_py": incredibly_fucking_scuffed_build_subclass,
    },
    include_package_data=True,
)
