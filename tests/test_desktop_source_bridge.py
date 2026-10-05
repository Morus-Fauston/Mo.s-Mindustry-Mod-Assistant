"""Source editing through the real workspace protocol and core session."""

from itertools import count
import json

import pytest

from app.desktop.workspace import WorkspaceService


PATH = "content/blocks/wall.json"


class SourceProbe:
    def __init__(self, root):
        self.service = WorkspaceService("metadata")
        self.ids, self.sid = count(), None
        self.sid = self.call("open_project", path=str(root))["sessionId"]

    def envelope(self, action, **payload):
        return {"protocolVersion": 1, "requestId": f"source-{next(self.ids)}",
                "sessionId": self.sid, "action": action, "payload": payload}

    def response(self, action, **payload):
        return self.service.request(self.envelope(action, **payload))

    def call(self, action, **payload):
        result = self.response(action, **payload)
        assert result["ok"], result
        return result["data"]

    def state(self):
        return self.call("editing_state")

    def change(self, action, **payload):
        return self.call(action, expectedRevision=self.state()["revision"], **payload)

    def document(self):
        return next(row for row in self.state()["documents"] if row["path"] == PATH)


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "source-project"
    (root / "content/blocks").mkdir(parents=True)
    (root / "mod.json").write_text('{"name":"probe"}', encoding="utf-8")
    (root / PATH).write_text('{"type":"Wall","health":137}', encoding="utf-8")
    return root


def test_first_bad_json_opens_without_fake_data_and_repair_undo_redo(project):
    raw = '{\r\n  "health":\r\n}'
    (project / PATH).write_bytes(raw.encode("utf-8"))
    probe = SourceProbe(project)
    opened = probe.call("read_document", path=PATH)
    assert opened["validData"] is False
    assert opened["data"] is None and opened["form"] is None
    assert opened["sourceText"] == raw and opened["dirty"] is False
    assert opened["sourceError"]["line"] == 3
    assert not probe.state()["history"]["canUndo"]
    repaired = probe.change("set_source", path=PATH, text='{"type":"Wall","health":251}')
    assert repaired["documents"][0]["data"]["health"] == 251
    assert repaired["documents"][0]["dirty"] is True
    assert (project / PATH).read_bytes() == raw.encode("utf-8")
    probe.change("undo")
    assert probe.document()["validData"] is False and not probe.document()["dirty"]
    probe.change("redo")
    assert probe.document()["data"]["health"] == 251


def test_preview_read_does_not_open_a_tab_or_change_revision_and_later_open_uses_same_object(project):
    probe = SourceProbe(project)
    before = probe.state()
    probe.call("preview_scene", path=PATH)
    assert probe.state() == before
    preview_content = probe.service._session.read_content("blocks/wall.json")
    probe.call("read_document", path=PATH)
    probe.change("set_source", path=PATH, text='{"type":"Wall","health":300}')
    assert probe.service._session.read_content("blocks/wall.json") is preview_content
    assert preview_content.data["health"] == 300


def test_repair_form_history_save_undo_raw_guards_and_discard_keep_object_identity(project):
    (project / PATH).write_text('{"health":', encoding="utf-8")
    probe = SourceProbe(project)
    probe.call("read_document", path=PATH)
    probe.change("set_source", path=PATH, text='{"type":"Wall","health":211}')
    content = probe.service._session.read_content("blocks/wall.json")
    identity = content.data
    probe.change("set_field", path=PATH, field="health", text="312")
    probe.change("undo")
    assert probe.document()["data"]["health"] == 211
    probe.change("undo")
    assert probe.document()["validData"] is False
    probe.change("redo")
    probe.change("redo")
    assert content.data is identity and probe.document()["data"]["health"] == 312
    probe.change("save_opened")
    assert json.loads((project / PATH).read_text(encoding="utf-8"))["health"] == 312
    probe.change("undo")
    probe.change("undo")
    assert probe.document()["validData"] is False and probe.document()["dirty"] is True
    for action, payload in (("preview_scene", {}), ("sprite_targets", {}),
                            ("set_field", {"field": "health", "text": "1"}),
                            ("add_field", {"field": "health"}), ("reference_candidates", {"field": "itemDrop"})):
        result = probe.response(action, path=PATH, expectedRevision=probe.state()["revision"], **payload)
        assert not result["ok"] and result["error"]["code"] == "SOURCE_INVALID", result
    assert not probe.response("save_opened", expectedRevision=probe.state()["revision"])["ok"]
    assert probe.call("read_document", path=PATH)["validData"] is False
    probe.change("close_documents", paths=[PATH], decision="discard")
    assert probe.state()["documents"] == []
    assert probe.call("read_document", path=PATH)["data"]["health"] == 312
    assert content.data is identity and probe.service._session.read_content("blocks/wall.json") is content
    probe.change("undo")
    assert probe.document()["validData"] is False


def test_discard_unsaved_repair_returns_raw_and_undo_reopens_same_valid_object(project):
    raw = '{bad json}'
    (project / PATH).write_text(raw, encoding="utf-8")
    probe = SourceProbe(project)
    probe.call("read_document", path=PATH)
    probe.change("set_source", path=PATH, text='{"type":"Wall","health":456}')
    content = probe.service._session.read_content("blocks/wall.json")
    identity = content.data
    probe.change("close_documents", paths=[PATH], decision="cancel")
    assert probe.document()["data"]["health"] == 456
    probe.change("close_documents", paths=[PATH], decision="discard")
    assert not probe.state()["documents"]
    probe.change("undo")
    assert probe.document()["data"]["health"] == 456 and content.data is identity
    assert probe.service._session.read_content("blocks/wall.json") is content
    assert (project / PATH).read_text(encoding="utf-8") == raw


def test_valid_source_roundtrip_large_integer_unknown_data_format_noop_and_invalid_error(project):
    probe = SourceProbe(project)
    probe.call("read_document", path=PATH)
    text = '{"type":"Wall","health":137,"future":{"number":9007199254740993}}'
    probe.change("set_source", path=PATH, text=text)
    before = probe.state()
    assert "9007199254740993" in probe.document()["sourceText"]
    formatted = probe.change("format_source", path=PATH, text=text)
    assert formatted["text"] == '{\n  "type": "Wall",\n  "health": 137,\n  "future": {\n    "number": 9007199254740993\n  }\n}'
    assert probe.state() == before
    probe.change("set_source", path=PATH, text=formatted["text"])
    assert probe.state() == before
    bad = probe.response("set_source", path=PATH, text='{\n"health":\n}', expectedRevision=before["revision"])
    assert bad["error"]["code"] == "SOURCE_INVALID"
    assert bad["error"]["line"] == 3 and bad["error"]["column"] == 1
    assert probe.state() == before
    probe.change("save_opened")
    assert json.loads((project / PATH).read_text(encoding="utf-8"))["future"]["number"] == 9007199254740993


def test_large_source_request_replay_conflict_and_session_isolation(project):
    probe = SourceProbe(project)
    probe.call("read_document", path=PATH)
    text = json.dumps({"type": "Wall", "custom": "源" * 20_000}, ensure_ascii=False)
    envelope = probe.envelope("set_source", path=PATH, text=text, expectedRevision=probe.state()["revision"])
    result = probe.service.request(envelope)
    assert result["ok"], result
    assert probe.service.request(envelope) == result
    assert probe.service.request_result(envelope["requestId"])["response"] == result
    assert probe.state()["revision"] == result["data"]["revision"]
    conflict = {**envelope, "payload": {**envelope["payload"], "text": '{}'}}
    assert probe.service.request(conflict)["error"]["code"] == "REQUEST_CONFLICT"
    probe.change("undo")
    assert probe.document()["data"] == {"type": "Wall", "health": 137}
    assert not probe.state()["history"]["canUndo"]
    probe.call("open_project", path=str(project))
    assert probe.service.request(envelope)["error"]["code"] == "STALE_SESSION"


@pytest.mark.parametrize("raw", ['[]', 'null', '{"health":NaN}', '{"health":1e400}', '{"x":"\\ud800"}'])
def test_invalid_source_initial_open_is_raw_and_unchanged_raw_can_close(project, raw):
    (project / PATH).write_text(raw, encoding="utf-8")
    probe = SourceProbe(project)
    document = probe.call("read_document", path=PATH)
    assert document["sourceText"] == raw and document["data"] is None
    assert not document["dirty"] and probe.service._session.loaded_content("blocks/wall.json") is None
    failed = probe.response("save_opened", expectedRevision=probe.state()["revision"])
    assert failed["error"]["code"] == "SOURCE_INVALID"
    probe.change("close_documents", paths=[PATH], decision="discard")
    assert probe.state()["documents"] == [] and not probe.state()["history"]["canUndo"]
    assert (project / PATH).read_text(encoding="utf-8") == raw


@pytest.mark.parametrize("data", [b'\xff\xfe\x00', b'{\x00}', b'x' * (4 * 1024 * 1024 + 1)],
                         ids=["invalid-encoding", "binary-null", "oversize"])
def test_binary_invalid_encoding_and_oversize_are_read_errors_not_raw_documents(project, data):
    (project / PATH).write_bytes(data)
    probe = SourceProbe(project)
    result = probe.response("read_document", path=PATH)
    assert not result["ok"] and result["error"]["code"] == "DOCUMENT_READ_FAILED"
    assert probe.state()["documents"] == []


@pytest.mark.parametrize("undo", [False, True])
def test_raw_transition_sidecar_failure_rolls_back_registration_and_history(project, monkeypatch, undo):
    (project / PATH).write_text('{broken}', encoding="utf-8")
    probe = SourceProbe(project)
    probe.call("read_document", path=PATH)
    if undo:
        probe.change("set_source", path=PATH, text='{"type":"Wall","health":190}')
    before = probe.state()
    registered = probe.service._session.loaded_content("blocks/wall.json")
    restore, calls = probe.service._editing.nested.restore, []

    def fail_once(path, state):
        restore(path, state)
        calls.append(path)
        if len(calls) == 1:
            raise ValueError("表单状态故障")

    monkeypatch.setattr(probe.service._editing.nested, "restore", fail_once)
    failed = probe.response("undo" if undo else "set_source", path=PATH,
                            text='{"type":"Wall","health":190}', expectedRevision=before["revision"])
    assert not failed["ok"]
    assert probe.state() == before
    assert probe.service._session.loaded_content("blocks/wall.json") is registered


def test_registration_failure_does_not_move_raw_state_or_history(project, monkeypatch):
    (project / PATH).write_text('{broken}', encoding="utf-8")
    probe = SourceProbe(project)
    probe.call("read_document", path=PATH)
    before = probe.state()

    def fail_attach(*_args):
        raise ValueError("注册失败")

    monkeypatch.setattr(probe.service._session, "attach_content", fail_attach)
    result = probe.response("set_source", path=PATH, text='{"type":"Wall"}', expectedRevision=before["revision"])
    assert not result["ok"] and probe.state() == before
    assert probe.service._session.loaded_content("blocks/wall.json") is None


def test_save_failure_keeps_repair_dirty_and_save_all_prechecks_raw(project, monkeypatch):
    (project / PATH).write_text('{broken}', encoding="utf-8")
    other = "content/blocks/other.json"
    (project / other).write_text('{broken}', encoding="utf-8")
    probe = SourceProbe(project)
    probe.call("read_document", path=PATH)
    probe.change("set_source", path=PATH, text='{"type":"Wall","health":411}')
    probe.call("read_document", path=other)
    refused = probe.response("save_opened", expectedRevision=probe.state()["revision"])
    assert refused["error"]["code"] == "SOURCE_INVALID"
    assert (project / PATH).read_text(encoding="utf-8") == '{broken}'
    probe.change("close_documents", paths=[other], decision="discard")
    before = probe.state()

    def failed_save(_content):
        raise OSError("文件被占用")

    monkeypatch.setattr(probe.service._session, "save_content", failed_save)
    failed = probe.response("save_opened", expectedRevision=before["revision"])
    assert failed["error"]["code"] == "SAVE_FAILED" and failed["error"]["path"] == PATH
    assert probe.state() == before and probe.document()["dirty"]


def test_source_limit_depth_nodes_and_stale_revision_are_rejected_without_history(project):
    probe = SourceProbe(project)
    probe.call("read_document", path=PATH)
    before = probe.state()
    for text in ('{"text":"' + 'x' * (4 * 1024 * 1024) + '"}',
                 '{"x":' + '[' * 64 + '0' + ']' * 64 + '}',
                 '{"x":[' + ','.join('0' for _ in range(100_000)) + ']}'):
        result = probe.response("set_source", path=PATH, text=text, expectedRevision=before["revision"])
        assert not result["ok"] and result["error"]["code"] == "SOURCE_INVALID"
    for action in ("set_source", "format_source"):
        result = probe.response(action, path=PATH, text='{}', expectedRevision=before["revision"] - 1)
        assert result["error"]["code"] == "STALE_REVISION"
    assert probe.state() == before


def test_cache_evicts_large_old_results_but_keeps_tombstones_and_latest_mutation(project, monkeypatch):
    probe = SourceProbe(project)
    probe.call("read_document", path=PATH)
    monkeypatch.setattr(probe.service, "MAX_RESULT_CACHE_BYTES", 400_000)
    envelopes, results = [], []
    revision = probe.state()["revision"]
    for number in range(6):
        text = json.dumps({"type": "Wall", "custom": str(number) * 70_000})
        envelope = probe.envelope("set_source", path=PATH, text=text, expectedRevision=revision)
        result = probe.service.request(envelope)
        assert result["ok"], result
        envelopes.append(envelope)
        results.append(result)
        revision = result["data"]["revision"]
    assert probe.service.request_result(envelopes[-1]["requestId"])["response"] == results[-1]
    expired = probe.service.request_result(envelopes[0]["requestId"])["response"]
    assert expired["error"]["code"] == "RESULT_EXPIRED"
    assert probe.service.request(envelopes[0]) == expired
    assert probe.state()["revision"] == revision
    assert probe.service._result_bytes <= probe.service.MAX_RESULT_CACHE_BYTES
    assert all(len(digest) == 64 for digest, _ in probe.service._results.values())


def test_source_then_nested_form_undo_redo_reaches_current_nested_objects(project):
    path = "content/weapons/gun.json"
    (project / "content/weapons").mkdir()
    (project / path).write_text('{"bullet":{"damage":10}}', encoding="utf-8")
    probe = SourceProbe(project)
    probe.call("read_document", path=path)
    probe.change("set_source", path=path, text='{"bullet":{"damage":20}}')
    probe.change("set_field", path=path, objectPath=["bullet"], field="damage", text="30")
    probe.change("undo")
    probe.change("undo")
    probe.change("redo")
    probe.change("redo")
    assert probe.state()["documents"][0]["data"]["bullet"]["damage"] == 30


def test_result_too_large_for_cache_is_completed_tombstone_without_reexecution(project, monkeypatch):
    probe = SourceProbe(project)
    probe.call("read_document", path=PATH)
    monkeypatch.setattr(probe.service, "MAX_RESULT_CACHE_BYTES", 10_000)
    envelope = probe.envelope("set_source", path=PATH,
                              text=json.dumps({"type": "Wall", "custom": "x" * 20_000}),
                              expectedRevision=probe.state()["revision"])
    result = probe.service.request(envelope)
    assert result["ok"]
    recovered = probe.service.request_result(envelope["requestId"])
    assert recovered["state"] == "completed" and recovered["response"]["error"]["code"] == "RESULT_EXPIRED"
    assert "已经执行" in recovered["response"]["error"]["message"]
    assert probe.service.request(envelope) == recovered["response"]
    assert probe.state()["revision"] == result["data"]["revision"]


def test_failed_source_request_replays_identical_error_without_overwriting_good_document(project):
    probe = SourceProbe(project)
    probe.call("read_document", path=PATH)
    before = probe.state()
    envelope = probe.envelope("set_source", path=PATH, text='{bad', expectedRevision=before["revision"])
    failed = probe.service.request(envelope)
    assert failed["error"]["code"] == "SOURCE_INVALID"
    assert probe.service.request(envelope) == failed
    assert probe.service.request_result(envelope["requestId"])["response"] == failed
    assert probe.state() == before


def test_registration_failure_after_attach_rolls_back_core_owner(project, monkeypatch):
    (project / PATH).write_text('{broken}', encoding="utf-8")
    probe = SourceProbe(project)
    probe.call("read_document", path=PATH)
    before = probe.state()
    attach = probe.service._session.attach_content

    def fail_after_attach(relative, candidate):
        attach(relative, candidate)
        raise ValueError("注册完成后的故障")

    monkeypatch.setattr(probe.service._session, "attach_content", fail_after_attach)
    result = probe.response("set_source", path=PATH, text='{"health":2}', expectedRevision=before["revision"])
    assert not result["ok"] and probe.state() == before
    assert probe.service._session.loaded_content("blocks/wall.json") is None


def test_unavailable_form_projection_does_not_reject_legal_source_after_commit(project, monkeypatch):
    probe = SourceProbe(project)
    probe.call("read_document", path=PATH)

    def unavailable(*_args):
        raise ValueError("资料投影不可用")

    monkeypatch.setattr(probe.service._editing.nested, "plan", unavailable)
    result = probe.change("set_source", path=PATH, text='{"type":"FutureCustom","future":9007199254740993}')
    document = result["documents"][0]
    assert document["validData"] and document["form"]["notice"]
    assert document["form"]["groups"] == []
    assert document["form"]["addableGroups"] == []
    assert document["form"]["objectPath"] == []
    assert document["form"]["contentType"] == "FutureCustom"
    assert document["form"]["knownType"] is False
    assert "9007199254740993" in document["sourceText"]
    probe.change("save_opened")
    assert json.loads((project / PATH).read_text(encoding="utf-8"))["future"] == 9007199254740993


@pytest.mark.parametrize("field", ["name", "type"])
def test_invalid_unicode_tree_metadata_remains_openable_raw_source(project, field):
    raw = '{"' + field + '":"\\ud800"}'
    (project / PATH).write_text(raw, encoding="utf-8")
    healthy = "content/blocks/healthy.json"
    (project / healthy).write_text('{"name":"完整墙","type":"Wall"}', encoding="utf-8")
    probe = SourceProbe(project)
    cached = probe.service.request_result("source-0")
    assert cached["state"] == "completed" and cached["response"]["ok"]
    pending = list(cached["response"]["data"]["tree"])
    leaves = {}
    while pending:
        node = pending.pop()
        pending.extend(node.get("children", []))
        if node["kind"] == "content":
            leaves[node["path"]] = node
    assert leaves[PATH]["label"] == "wall" and leaves[PATH]["error"]
    assert leaves[healthy]["label"] == "完整墙" and "error" not in leaves[healthy]
    document = probe.call("read_document", path=PATH)
    assert document["sourceText"] == raw and document["validData"] is False
    repaired = probe.change("set_source", path=PATH, text='{"name":"修复墙","type":"Wall"}')
    assert repaired["documents"][0]["data"]["name"] == "修复墙"


def test_result_cache_accounts_escaped_metadata_without_failing_completed_operation():
    service = WorkspaceService("metadata")
    response = {"ok": True, "protocolVersion": 1, "requestId": "metadata", "sessionId": None,
                "data": {"displayName": "\ud800"}}
    service._cache_result("metadata", "a" * 64, response)
    assert service.request_result("metadata")["response"] == response
    assert service._result_bytes == len(json.dumps(response, ensure_ascii=True).encode("utf-8"))
