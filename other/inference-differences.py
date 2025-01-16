def pycon():
    return "PyCon PL "


def pycon_this_year():
    return pycon() + 2025  # mypy: OK, pyright: error, pytype: error
