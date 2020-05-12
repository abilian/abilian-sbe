import nox

PYTHON_VERSIONS = ["3.6", "3.7", "3.8"]
PACKAGE = "abilian"


@nox.session(python="python3.6")
def lint(session):
    session.run("poetry", "install", "-q")
    session.install("poetry", "psycopg2-binary")
    session.run("yarn", external="True")

    session.run("make", "lint-ci")


@nox.session(python=PYTHON_VERSIONS)
def pytest(session):
    session.run("poetry", "install", external="True")
    session.install("psycopg2-binary")
    session.run("yarn", external="True")

    session.run("pip", "check")
    session.run("pytest", "-q")


@nox.session(python="3.8")
def typeguard(session):
    session.install("psycopg2-binary")
    session.run("poetry", "install", "-q", external="True")
    session.run("yarn", external="True")

    session.run("pytest", f"--typeguard-packages={PACKAGE}")
