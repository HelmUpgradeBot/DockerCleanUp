import pytest
import argparse
from unittest.mock import patch
from docker_bot.cli import check_parser, parse_args


def test_check_parser():
    test_args = argparse.Namespace(dry_run=True, purge=True)

    with pytest.raises(ValueError):
        check_parser(test_args)


def test_check_parser_both_false():
    test_args = argparse.Namespace(dry_run=False, purge=False)

    try:
        check_parser(test_args)
    except:  # noqa: E722
        pytest.fail("Unexpected error")


def test_check_parser_alternate_values():
    test_args1 = argparse.Namespace(dry_run=True, purge=False)
    test_args2 = argparse.Namespace(dry_run=False, purge=True)

    try:
        check_parser(test_args1)
        check_parser(test_args2)
    except:  # noqa: E722
        pytest.fail("Unexpected error")


@patch(
    "argparse.ArgumentParser.parse_args",
    return_value=argparse.Namespace(name="test_acr", max_age=90, limit=2.0,),
)
def test_parser_run_basic(mock_args):
    parser = parse_args("test_acr")

    assert parser.name == "test_acr"
    assert parser.max_age == 90
    assert parser.limit == 2.0
    assert mock_args.call_count == 1


@patch(
    "argparse.ArgumentParser.parse_args",
    return_value=argparse.Namespace(
        name="test_acr", identity=True, dry_run=True, purge=True, verbose=True
    ),
)
def test_parser_run_boolean(mock_args):
    parser = parse_args(
        ["test_acr", "--identity", "--dry_run", "--purge", "--verbose"]
    )

    assert parser.name == "test_acr"
    assert parser.identity
    assert parser.dry_run
    assert parser.purge
    assert parser.verbose
    assert mock_args.call_count == 1


@patch(
    "argparse.ArgumentParser.parse_args",
    return_value=argparse.Namespace(name="test_acr", max_age=10, limit=1.5),
)
def test_parser_run_options(mock_args):
    parser = parse_args(["test_acr", "--max-age", 10, "--limit", 1.5])

    assert parser.name == "test_acr"
    assert parser.max_age == 10
    assert parser.limit == 1.5
    assert mock_args.call_count == 1
