from services.app_deployment_models import AppResourceSpec, ContainerAppSpec, WorkerAppSpec
from services.app_deployment_validation import (
    ValidationIssue,
    validate_container_spec,
    validate_github_repo_url,
    validate_worker_spec,
)


NODE_ADDRESS = "0xai_A9OqTV_iFqmwj1SV7AKbdyr66NLkhSQHPpzp40c7jaLn"


def issue_fields(issues):
    return {issue.field for issue in issues}


def test_container_spec_validation_accepts_minimal_valid_car_payload():
    spec = ContainerAppSpec(
        app_name="car_runner",
        node_address=NODE_ADDRESS,
        image="nginx:alpine",
        port=8080,
        env={"PUBLIC_VALUE": "1"},
    )

    assert validate_container_spec(spec) == []


def test_container_spec_validation_reports_field_level_issues():
    spec = ContainerAppSpec(
        app_name="bad app name",
        node_address="0xeth_not_sdk",
        image="no spaces allowed:latest",
        port=70000,
        registry_server="docker",
        env={"BAD KEY": "x"},
        volumes={"cache": "relative/path"},
        resources=AppResourceSpec(cpu=0, memory="512"),
    )

    fields = issue_fields(validate_container_spec(spec))

    assert fields == {
        "app_name",
        "node_address",
        "image",
        "port",
        "registry_server",
        "resources.cpu",
        "resources.memory",
        "env",
        "volumes",
    }


def test_worker_spec_validation_accepts_github_url_and_commands():
    spec = WorkerAppSpec(
        app_name="worker_runner",
        node_address=NODE_ADDRESS,
        repo_url="https://github.com/Ratio1/example-app",
        commands=["npm install", "npm run build", "npm run start"],
    )

    assert validate_worker_spec(spec) == []


def test_worker_spec_validation_rejects_invalid_repo_and_duplicate_commands():
    spec = WorkerAppSpec(
        app_name="worker_runner",
        node_address=NODE_ADDRESS,
        repo_url="https://gitlab.com/Ratio1/example-app",
        commands=["npm install", "npm install"],
        vcs_poll_interval=1,
    )

    issues = validate_worker_spec(spec)

    assert ValidationIssue("repo_url", "Use a GitHub URL such as https://github.com/org/repo.") in issues
    assert any(issue.field == "commands" and "Duplicate command" in issue.message for issue in issues)
    assert ValidationIssue("vcs_poll_interval", "Poll interval must be between 5 seconds and 1 day.") in issues


def test_github_repo_validation_requires_owner_and_repo():
    assert validate_github_repo_url("https://github.com/Ratio1") == [
        ValidationIssue("repo_url", "GitHub URL must include owner and repository.")
    ]
