import pytest
from unittest.mock import call, patch

from docker_bot.app import check_acr_size, pull_manifests


@patch(
    "docker_bot.app.run_cmd",
    return_value={"returncode": 0, "output": 1000000000.0},
)
def test_check_acr_size_smaller_than(mock_args):
    name = "test_acr"
    limit = 2.0

    out = check_acr_size(name, limit)

    mock_args.assert_called_once()
    mock_args.assert_called_once_with(
        [
            "az",
            "acr",
            "show-usage",
            "-n",
            name,
            "--query",
            "{}".format("value[?name=='Size'].currentValue"),
            "-o",
            "tsv",
        ]
    )
    assert mock_args.return_value == {"returncode": 0, "output": 1000000000.0}
    assert out[0] == 1.0
    assert not out[1]


@patch(
    "docker_bot.app.run_cmd",
    return_value={"returncode": 0, "output": 5000000000000.0},
)
def test_check_acr_size_greater_than(mock_args):
    name = "test_acr"
    limit = 2.0

    out = check_acr_size(name, limit)

    mock_args.assert_called_once()
    mock_args.assert_called_once_with(
        [
            "az",
            "acr",
            "show-usage",
            "-n",
            name,
            "--query",
            "{}".format("value[?name=='Size'].currentValue"),
            "-o",
            "tsv",
        ]
    )
    assert mock_args.return_value == {
        "returncode": 0,
        "output": 5000000000000.0,
    }
    assert out[0] == 5000.0
    assert out[1]


@patch(
    "docker_bot.app.run_cmd",
    return_value={
        "returncode": 1,
        "output": "",
        "err_msg": "Could not run command",
    },
)
def test_check_acr_size_exception(mock_args):
    name = "test_acr"
    limit = 2.0

    with mock_args as mock, pytest.raises(RuntimeError):
        check_acr_size(name, limit)

        mock.assert_called_once()
        mock.assert_called_once_with(
            [
                "az",
                "acr",
                "show-usage",
                "-n",
                name,
                "--query",
                "{}".format("value[?name=='Size'].currentValue"),
                "-o",
                "tsv",
            ]
        )
        assert mock.return_value == {
            "returncode": 1,
            "output": "",
            "err_msg": "Could not run command",
        }


@patch(
    "docker_bot.app.run_cmd",
    return_value={
        "returncode": 0,
        "output": '[{"timestamp": "2020-07-30T19:56:00.0000000Z", "digest": "digest_image1"}, {"timestamp": "2020-07-29T19:57:00.0000000Z", "digest": "digest_image2"}]',
    },
)
def test_pull_manifests(mock_args):
    acr_name = "test_acr"
    repo = "test_repo"

    out = pull_manifests(acr_name, repo)

    mock_args.assert_called_once()
    mock_args.assert_called_once_with(
        [
            "az",
            "acr",
            "repository",
            "show-manifests",
            "-n",
            acr_name,
            "--repository",
            repo,
        ]
    )
    assert mock_args.return_value["returncode"] == 0
    assert (
        mock_args.return_value["output"]
        == '[{"timestamp": "2020-07-30T19:56:00.0000000Z", "digest": "digest_image1"}, {"timestamp": "2020-07-29T19:57:00.0000000Z", "digest": "digest_image2"}]'
    )
    assert out == [
        {
            "timestamp": "2020-07-30T19:56:00.0000000Z",
            "digest": "digest_image1",
        },
        {
            "timestamp": "2020-07-29T19:57:00.0000000Z",
            "digest": "digest_image2",
        },
    ]


@patch(
    "docker_bot.app.run_cmd",
    return_value={"returncode": 1, "err_msg": "Could not run command"},
)
def test_pull_manifests_exception(mock_args):
    acr_name = "test_acr"
    repo = "test_repo"

    with mock_args as mock, pytest.raises(RuntimeError):
        pull_manifests(acr_name, repo)

        mock.assert_called_once()
        mock.assert_called_once_with(
            [
                "az",
                "acr",
                "repository",
                "show-manifests",
                "-n",
                acr_name,
                "--repository",
                repo,
            ]
        )
        assert mock.return_value["returncode"] == 1
        assert mock.return_value["err_msg"] == "Could not run command"
