from utils.docker_errors import extract_conflicting_container_id


def test_extract_conflicting_container_id_from_docker_conflict_message():
    error = (
        'Conflict. The container name "/r1node" is already in use by container '
        '"abc123deadbeef". You have to remove or rename that container.'
    )

    assert extract_conflicting_container_id(error) == "abc123deadbeef"


def test_extract_conflicting_container_id_returns_none_without_container_id():
    assert extract_conflicting_container_id("Conflict. Container name is already in use.") is None
    assert extract_conflicting_container_id("") is None
