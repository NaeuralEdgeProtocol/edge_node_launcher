from services.sdk_operation_worker import SdkOperationThread


def test_sdk_operation_thread_emits_success(qtbot):
    thread = SdkOperationThread("refresh", lambda: {"ok": True})

    with qtbot.waitSignal(thread.operation_finished, timeout=1000) as blocker:
        thread.start()

    thread.wait(1000)

    assert blocker.args == ["refresh", {"ok": True}]


def test_sdk_operation_thread_emits_failure(qtbot):
    def fail():
        raise RuntimeError("sdk failed")

    thread = SdkOperationThread("launch", fail)

    with qtbot.waitSignal(thread.operation_failed, timeout=1000) as blocker:
        thread.start()

    thread.wait(1000)

    assert blocker.args == ["launch", "sdk failed"]
