import importlib


def test_import():
    assert importlib.import_module("zabbix_ro")
