import os

import pytest

from utils.edge_image_config import reset_edge_node_image_config_for_tests


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def reset_edge_node_image_config():
    reset_edge_node_image_config_for_tests()
    yield
    reset_edge_node_image_config_for_tests()
