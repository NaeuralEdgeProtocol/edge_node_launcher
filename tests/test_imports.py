def test_core_entrypoints_import_without_starting_event_loop():
    import launcher  # noqa: F401
    import main  # noqa: F401


def test_main_window_class_imports():
    from app_forms.frm_main import EdgeNodeLauncher

    assert EdgeNodeLauncher.__name__ == "EdgeNodeLauncher"
