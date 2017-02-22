import pytest

def pytest_addoption(parser):
    parser.addoption("--db_file", action="store", default="test.db",
        help="db file, generally set it to 'play.db' or 'test.db'")
    parser.addoption("--browser", action="store", default="phantom",
        help="Set which browser driver to use in the browser tests, chrome or firefox, default is phantom")
