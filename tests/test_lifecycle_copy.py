from utils.lifecycle_copy import (
    launch_dialog_copy,
    launch_success_notification,
    new_node_success_notification,
    stop_dialog_copy,
    stop_success_notification,
)


def test_launch_dialog_copy_preserves_alias_and_default_messages():
    assert launch_dialog_copy("alpha").title == "Launching Node"
    assert launch_dialog_copy("alpha").message == "Please wait while node 'alpha' is being launched..."
    assert launch_dialog_copy(None).message == "Please wait while Edge Node is being launched..."


def test_new_node_dialog_copy_uses_starting_title_and_new_node_default():
    assert launch_dialog_copy("beta", is_new_node=True).title == "Starting Node"
    assert launch_dialog_copy("beta", is_new_node=True).message == "Please wait while node 'beta' is being launched..."
    assert launch_dialog_copy(None, is_new_node=True).message == "Please wait while new Edge Node is being launched..."


def test_stop_dialog_copy_preserves_alias_and_default_messages():
    assert stop_dialog_copy("alpha").title == "Stopping Node"
    assert stop_dialog_copy("alpha").message == "Please wait while node 'alpha' is being stopped..."
    assert stop_dialog_copy(None).message == "Please wait while Edge Node is being stopped..."


def test_lifecycle_success_notifications_match_existing_copy():
    assert launch_success_notification("alpha") == "Node 'alpha' launched successfully"
    assert launch_success_notification(None) == "Edge Node launched successfully"
    assert stop_success_notification("alpha") == "Node 'alpha' stopped successfully"
    assert stop_success_notification(None) == "Edge Node stopped successfully"
    assert new_node_success_notification("beta") == "New Node 'beta' created successfully"
    assert new_node_success_notification(None) == "New Edge Node created successfully"
