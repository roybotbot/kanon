import pytest
from click.testing import CliRunner
from kanon.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


class TestCLI:
    def test_graph_command(self, runner):
        result = runner.invoke(cli, ["graph"])
        assert result.exit_code == 0
        assert "Knowledge Graph" in result.output

    def test_graph_concept(self, runner):
        result = runner.invoke(cli, ["graph", "--concept", "tool_use"])
        assert result.exit_code == 0
        assert "Tool Use" in result.output

    def test_graph_nonexistent_concept(self, runner):
        result = runner.invoke(cli, ["graph", "--concept", "nonexistent"])
        assert result.exit_code == 0
        assert "not found" in result.output

    def test_graph_gaps(self, runner):
        result = runner.invoke(cli, ["graph", "--gaps"])
        assert result.exit_code == 0

    def test_status_command(self, runner):
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0

    def test_generate_dry_run(self, runner):
        result = runner.invoke(cli, [
            "generate",
            "--type", "setup_guide",
            "--concepts", "tool_use",
            "--audience", "enterprise_developer",
            "--dry-run"
        ])
        assert result.exit_code == 0
        assert "Tool Use" in result.output

    def test_generate_bad_concept(self, runner):
        result = runner.invoke(cli, [
            "generate",
            "--type", "setup_guide",
            "--concepts", "nonexistent",
            "--audience", "enterprise_developer",
            "--dry-run"
        ])
        assert result.exit_code == 0
        assert "Error" in result.output

    def test_drift_command(self, runner):
        result = runner.invoke(cli, [
            "drift",
            "--evidence", "anthropic_tool_use_docs",
            "--change", "Tool schema format updated"
        ])
        assert result.exit_code == 0
        assert "Drift Report" in result.output
