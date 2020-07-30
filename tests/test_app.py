import pytest
from unittest.mock import call, patch

from docker_bot.app import check_acr_size

@patch("docker_bot.app.run_cmd", return_value={"returncode": 0, "output": 1000000000.0})
def test_check_acr_size(mock_args):
    name = "test_acr"
    limit = 2.0

    out = check_acr_size(name, limit)

    mock_args.assert_called_once()
    mock_args.assert_called_once_with(["az", "acr", "show-usage", "-n", name, "--query", "{}".format("value[?name=='Size'].currentValue"), "-o", "tsv"])
    assert mock_args.return_value == {"returncode": 0, "output": 1000000000.0}
    assert out[0] == 1.0
    assert not out[1]
