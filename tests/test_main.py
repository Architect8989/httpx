import os
import typing

from click.testing import CliRunner

import httpx


def splitlines(output: str) -> typing.Iterable[str]:
    return [line.strip() for line in output.splitlines()]


def remove_date_header(lines: typing.Iterable[str]) -> typing.Iterable[str]:
    return [line for line in lines if not line.lower().startswith("date:")]


def has_header(lines: typing.Iterable[str], expected_line: str) -> bool:
    """Check if a header line exists in the output, with case-insensitive name matching."""
    expected_name, _, expected_value = expected_line.partition(": ")
    for line in lines:
        line_name, _, line_value = line.partition(": ")
        if line_name.lower() == expected_name.lower() and line_value == expected_value:
            return True
    return False


def test_help():
    runner = CliRunner()
    result = runner.invoke(httpx.main, ["--help"])
    assert result.exit_code == 0
    assert "A next generation HTTP client." in result.output


def test_get(server):
    url = str(server.url)
    runner = CliRunner()
    result = runner.invoke(httpx.main, [url])
    assert result.exit_code == 0
    lines = remove_date_header(splitlines(result.output))
    assert "HTTP/1.1 200 OK" in lines
    assert has_header(lines, "content-type: text/plain")
    assert "Hello, world!" in lines


def test_json(server):
    url = str(server.url.copy_with(path="/json"))
    runner = CliRunner()
    result = runner.invoke(httpx.main, [url])
    assert result.exit_code == 0
    lines = remove_date_header(splitlines(result.output))
    assert "HTTP/1.1 200 OK" in lines
    assert has_header(lines, "content-type: application/json")
    assert '"Hello": "world!"' in lines


def test_binary(server):
    url = str(server.url.copy_with(path="/echo_binary"))
    runner = CliRunner()
    content = "Hello, world!"
    result = runner.invoke(httpx.main, [url, "-c", content])
    assert result.exit_code == 0
    lines = remove_date_header(splitlines(result.output))
    assert "HTTP/1.1 200 OK" in lines
    assert has_header(lines, "content-type: application/octet-stream")
    assert f"<{len(content)} bytes of binary data>" in lines


def test_redirects(server):
    url = str(server.url.copy_with(path="/redirect_301"))
    runner = CliRunner()
    result = runner.invoke(httpx.main, [url])
    assert result.exit_code == 1
    lines = remove_date_header(splitlines(result.output))
    assert "HTTP/1.1 301 Moved Permanently" in lines
    assert has_header(lines, "location: /")


def test_follow_redirects(server):
    url = str(server.url.copy_with(path="/redirect_301"))
    runner = CliRunner()
    result = runner.invoke(httpx.main, [url, "--follow-redirects"])
    assert result.exit_code == 0
    lines = remove_date_header(splitlines(result.output))
    assert "HTTP/1.1 301 Moved Permanently" in lines
    assert has_header(lines, "location: /")
    assert "HTTP/1.1 200 OK" in lines
    assert has_header(lines, "content-type: text/plain")
    assert "Hello, world!" in lines


def test_post(server):
    url = str(server.url.copy_with(path="/echo_body"))
    runner = CliRunner()
    result = runner.invoke(httpx.main, [url, "-m", "POST", "-j", '{"hello": "world"}'])
    assert result.exit_code == 0
    lines = remove_date_header(splitlines(result.output))
    assert "HTTP/1.1 200 OK" in lines
    assert has_header(lines, "content-type: text/plain")
    assert '{"hello":"world"}' in lines


def test_verbose(server):
    url = str(server.url)
    runner = CliRunner()
    result = runner.invoke(httpx.main, [url, "-v"])
    assert result.exit_code == 0
    lines = remove_date_header(splitlines(result.output))
    assert "GET / HTTP/1.1" in lines
    assert "HTTP/1.1 200 OK" in lines
    assert has_header(lines, "content-type: text/plain")
    assert "Hello, world!" in lines


def test_auth(server):
    url = str(server.url)
    runner = CliRunner()
    result = runner.invoke(httpx.main, [url, "-v", "--auth", "username", "password"])
    print(result.output)
    assert result.exit_code == 0
    lines = remove_date_header(splitlines(result.output))
    assert "GET / HTTP/1.1" in lines
    assert "Authorization: Basic" in result.output  # check auth header exists in raw output
    assert "HTTP/1.1 200 OK" in lines
    assert has_header(lines, "content-type: text/plain")
    assert "Hello, world!" in lines


def test_download(server):
    url = str(server.url)
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(httpx.main, [url, "--download", "index.txt"])
        assert os.path.exists("index.txt")
        with open("index.txt", "r") as input_file:
            assert input_file.read() == "Hello, world!"


def test_errors():
    runner = CliRunner()
    result = runner.invoke(httpx.main, ["invalid://example.org"])
    assert result.exit_code == 1
    assert splitlines(result.output) == [
        "UnsupportedProtocol: Request URL has an unsupported protocol 'invalid://'.",
    ]
