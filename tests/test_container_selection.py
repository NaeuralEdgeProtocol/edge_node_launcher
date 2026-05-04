from utils.container_selection import selected_container_from_combo, select_container_by_name


class FakeCombo:
    def __init__(self, items, current_index=0):
        self.items = items
        self.current_index = current_index

    def currentIndex(self):
        return self.current_index

    def itemData(self, index):
        return self.items[index][1]

    def currentText(self):
        return self.items[self.current_index][0]

    def count(self):
        return len(self.items)

    def setCurrentIndex(self, index):
        self.current_index = index


def test_selected_container_uses_item_data_as_identity_and_text_as_display():
    combo = FakeCombo([("friendly-node", "r1node")])

    selection = selected_container_from_combo(combo)

    assert selection.name == "r1node"
    assert selection.display_name == "friendly-node"
    assert selection.index == 0


def test_selected_container_returns_none_when_no_valid_item_is_selected():
    assert selected_container_from_combo(FakeCombo([("friendly-node", "r1node")], -1)) is None
    assert selected_container_from_combo(FakeCombo([("friendly-node", None)])) is None


def test_select_container_by_name_matches_item_data_not_display_text():
    combo = FakeCombo(
        [
            ("alpha", "r1node"),
            ("beta", "r1node2"),
        ]
    )

    assert select_container_by_name(combo, "r1node2")
    assert combo.current_index == 1

    assert not select_container_by_name(combo, "beta")
    assert combo.current_index == 1
