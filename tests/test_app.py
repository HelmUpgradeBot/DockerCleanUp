import pytest
import pandas as pd
from freezegun import freeze_time
from unittest.mock import call, patch
from pandas._testing import assert_frame_equal

from docker_bot.app import (
    check_acr_size,
    delete_image,
    login,
    pull_manifests,
    pull_image_age,
    pull_repos,
    purge_all,
    sort_image_df,
)


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
        "output": '[{"timestamp": "2020-07-30T19:56:00.0000000Z", "repo": "test_repo", "digest": "digest_image1"}, {"timestamp": "2020-07-29T19:57:00.0000000Z", "repo": "test_repo", "digest": "digest_image2"}]',
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
        == '[{"timestamp": "2020-07-30T19:56:00.0000000Z", "repo": "test_repo", "digest": "digest_image1"}, {"timestamp": "2020-07-29T19:57:00.0000000Z", "repo": "test_repo", "digest": "digest_image2"}]'
    )
    assert out == [
        {
            "timestamp": "2020-07-30T19:56:00.0000000Z",
            "repo": repo,
            "digest": "digest_image1",
        },
        {
            "timestamp": "2020-07-29T19:57:00.0000000Z",
            "repo": repo,
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


def test_pull_image_age():
    acr_name = "test_acr"
    repo = "test_repo"
    manifest = {
        "timestamp": "2020-07-30T21:12:00.0000000Z",
        "digest": "image_digest",
        "repo": "test_repo",
    }

    with freeze_time("2020-08-01T09:30:00.0000000Z"):
        out = pull_image_age(acr_name, manifest)

        assert out[0] == f"{repo}@{manifest['digest']}"
        assert out[1] == 1


@patch(
    "docker_bot.app.run_cmd",
    return_value={"returncode": 0, "output": "repo1\nrepo2\nrepo3"},
)
def test_pull_repos(mock_args):
    acr_name = "test_acr"
    expected_call = call(
        ["az", "acr", "repository", "list", "-n", acr_name, "-o", "tsv"]
    )

    out = pull_repos(acr_name)

    assert mock_args.call_count == 1
    assert mock_args.call_args == expected_call
    assert mock_args.return_value == {
        "returncode": 0,
        "output": "repo1\nrepo2\nrepo3",
    }
    assert out == ["repo1", "repo2", "repo3"]


@patch(
    "docker_bot.app.run_cmd",
    return_value={"returncode": 1, "err_msg": "Could not run command"},
)
def test_pull_repos_exception(mock_args):
    acr_name = "test_acr"
    expected_call = call(
        ["az", "acr", "repository", "list", "-n", acr_name, "-o", "tsv"]
    )

    with mock_args as mock, pytest.raises(RuntimeError):
        pull_repos(acr_name)

        assert mock.call_count == 1
        assert mock.call_args == expected_call
        assert mock.return_value == {
            "returncode": 1,
            "err_msg": "Could not run command",
        }


def test_sort_image_df_all_match():
    max_age = 2
    test_df = pd.DataFrame(
        {
            "image_name": ["image1", "image2"],
            "age_days": [3, 4],
            "size_gb": [1.0, 1.5],
        }
    )

    sorted_df = sort_image_df(test_df, max_age)

    assert_frame_equal(test_df, sorted_df)


def test_sort_image_df_no_match():
    max_age = 2
    test_df = pd.DataFrame(
        {
            "image_name": ["image1", "image2"],
            "age_days": [0, 1],
            "size_gb": [1.0, 1.5],
        }
    )

    sorted_df = sort_image_df(test_df, max_age)

    assert sorted_df.empty


def test_sort_image_df_partial_match():
    max_age = 2
    test_df = pd.DataFrame(
        {
            "image_name": ["image1", "image2", "image3"],
            "age_days": [1, 2, 3],
            "size_gb": [1.0, 1.5, 2.0],
        }
    )
    expected_df = pd.DataFrame(
        {
            "image_name": ["image2", "image3"],
            "age_days": [2, 3],
            "size_gb": [1.5, 2.0],
        }
    )

    sorted_df = sort_image_df(test_df, max_age)

    assert_frame_equal(sorted_df, expected_df)
    assert len(sorted_df) == 2


@patch("docker_bot.app.run_cmd", return_value={"returncode": 0})
def test_delete_image(mock_args):
    acr_name = "test_acr"
    image_name = "test_image"
    expected_call = call(
        [
            "az",
            "acr",
            "repository",
            "delete",
            "-n",
            acr_name,
            "--image",
            image_name,
            "--yes",
        ]
    )

    delete_image(acr_name, image_name)

    assert mock_args.call_count == 1
    assert mock_args.return_value == {"returncode": 0}
    assert mock_args.call_args == expected_call


@patch(
    "docker_bot.app.run_cmd",
    return_value={"returncode": 1, "err_msg": "Could not run command"},
)
def test_delete_image_exception(mock_args):
    acr_name = "test_acr"
    image_name = "test_image"
    expected_call = call(
        [
            "az",
            "acr",
            "repository",
            "delete",
            "-n",
            acr_name,
            "--image",
            image_name,
            "--yes",
        ]
    )

    with mock_args as mock, pytest.raises(RuntimeError):
        delete_image(acr_name, image_name)

        assert mock.call_count == 1
        assert mock.return_value == {
            "returncode": 1,
            "err_msg": "Could not run command",
        }
        assert mock.call_args == expected_call


@patch("docker_bot.app.run_cmd")
def test_login_basic(mock_args):
    acr_name = "test_acr"

    mock_args.side_effect = [
        {"returncode": 0},
        {"returncode": 0, "output": "login succeeded"},
    ]
    expected_calls = [
        call(["az", "login"]),
        call(["az", "acr", "login", "-n", acr_name]),
    ]

    login(acr_name)

    assert mock_args.call_count == 2
    assert mock_args.call_args_list == expected_calls


@patch("docker_bot.app.run_cmd")
def test_login_identity(mock_args):
    acr_name = "test_acr"

    mock_args.side_effect = [
        {"returncode": 0},
        {"returncode": 0, "output": "login succeeded"},
    ]
    expected_calls = [
        call(["az", "login", "--identity"]),
        call(["az", "acr", "login", "-n", acr_name]),
    ]

    login(acr_name, identity=True)

    assert mock_args.call_count == 2
    assert mock_args.call_args_list == expected_calls


@patch("docker_bot.app.run_cmd")
def test_login_exception(mock_args):
    acr_name = "test_acr"

    mock_args.side_effect = [
        {"returncode": 1, "err_msg": "Could not run command"},
        {"returncode": 1, "err_msg": "Could not run command"},
    ]
    expected_calls = [
        call(["az", "login"]),
        call(["az", "acr", "login", "-n", acr_name]),
    ]

    with mock_args as mock, pytest.raises(RuntimeError):
        login(acr_name)

        assert mock.call_count == 2
        assert mock.call_args_list == expected_calls


@patch("docker_bot.app.run_cmd")
def test_purge_all(mock_args):
    acr_name = "test_acr"
    test_df = pd.DataFrame(
        {"image_name": ["image1", "image2"], "age_days": [67, 53]}
    )
    test_df.set_index("image_name", inplace=True)
    expected_calls = [
        call(
            [
                "az",
                "acr",
                "repository",
                "delete",
                "-n",
                acr_name,
                "--image",
                "image1",
                "--yes",
            ]
        ),
        call(
            [
                "az",
                "acr",
                "repository",
                "delete",
                "-n",
                acr_name,
                "--image",
                "image2",
                "--yes",
            ]
        ),
    ]

    mock_args.side_effect = [{"returncode": 0}, {"returncode": 0}]

    purge_all(acr_name, test_df)

    assert mock_args.call_count == 2
    assert mock_args.call_args_list == expected_calls


@patch(
    "docker_bot.app.run_cmd",
    return_value={"returncode": 1, "err_msg": "Could not run command"},
)
def test_purge_all(mock_args):
    acr_name = "test_acr"
    test_df = pd.DataFrame(
        {"image_name": ["image1", "image2"], "age_days": [67, 53]}
    )
    test_df.set_index("image_name", inplace=True)
    expected_call = call(
        [
            "az",
            "acr",
            "repository",
            "delete",
            "-n",
            acr_name,
            "--image",
            "image1",
            "--yes",
        ]
    )

    with mock_args as mock, pytest.raises(RuntimeError):
        purge_all(acr_name, test_df)

        assert mock.call_count == 1
        assert mock.call_args == expected_call
