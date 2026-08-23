"""Tests for app.core.commands — CommandStack, SetFieldCommand, path parsing."""

import pytest

from app.core.commands import (
    ArrayInsertCommand,
    ArrayRemoveCommand,
    CommandStack,
    ReplaceDataCommand,
    SetFieldCommand,
)


class TestSetFieldCommand:
    def test_execute_sets_value(self):
        data = {"health": 150}
        cmd = SetFieldCommand(data=data, path="health", new_value=300)
        cmd.execute()
        assert data["health"] == 300

    def test_undo_restores_value(self):
        data = {"health": 150}
        cmd = SetFieldCommand(data=data, path="health", new_value=300)
        cmd.execute()
        cmd.undo()
        assert data["health"] == 150

    def test_nested_path(self):
        data = {"weapons": [{"bullet": {"damage": 10}}]}
        cmd = SetFieldCommand(data=data, path="weapons[0].bullet.damage", new_value=25)
        cmd.execute()
        assert data["weapons"][0]["bullet"]["damage"] == 25

    def test_nested_path_undo(self):
        data = {"weapons": [{"bullet": {"damage": 10}}]}
        cmd = SetFieldCommand(data=data, path="weapons[0].bullet.damage", new_value=25)
        cmd.execute()
        cmd.undo()
        assert data["weapons"][0]["bullet"]["damage"] == 10

    def test_set_new_key(self):
        data = {"health": 100}
        cmd = SetFieldCommand(data=data, path="armor", new_value=5)
        cmd.execute()
        assert data["armor"] == 5

    def test_undo_new_key_removes_it(self):
        data = {"health": 100}
        cmd = SetFieldCommand(data=data, path="armor", new_value=5)
        cmd.execute()
        cmd.undo()
        assert "armor" not in data

    def test_set_none_value(self):
        data = {"name": "test"}
        cmd = SetFieldCommand(data=data, path="name", new_value=None)
        cmd.execute()
        assert data["name"] is None

    def test_merge_consecutive_same_path(self):
        data = {"health": 100}
        cmd1 = SetFieldCommand(data=data, path="health", new_value=200)
        cmd2 = SetFieldCommand(data=data, path="health", new_value=300)
        merged = cmd1.merge_with(cmd2)
        assert merged is not None
        # Merged command should undo to original value
        merged.execute()
        assert data["health"] == 300
        merged.undo()
        assert data["health"] == 100

    def test_no_merge_different_paths(self):
        data = {"health": 100, "armor": 0}
        cmd1 = SetFieldCommand(data=data, path="health", new_value=200)
        cmd2 = SetFieldCommand(data=data, path="armor", new_value=5)
        merged = cmd1.merge_with(cmd2)
        assert merged is None


class TestArrayCommands:
    def test_insert(self):
        data = {"weapons": [{"name": "a"}]}
        cmd = ArrayInsertCommand(
            data=data, path="weapons", index=1, element={"name": "b"}
        )
        cmd.execute()
        assert len(data["weapons"]) == 2
        assert data["weapons"][1]["name"] == "b"

    def test_insert_undo(self):
        data = {"weapons": [{"name": "a"}]}
        cmd = ArrayInsertCommand(
            data=data, path="weapons", index=1, element={"name": "b"}
        )
        cmd.execute()
        cmd.undo()
        assert len(data["weapons"]) == 1
        assert data["weapons"][0]["name"] == "a"

    def test_remove(self):
        data = {"weapons": [{"name": "a"}, {"name": "b"}]}
        cmd = ArrayRemoveCommand(data=data, path="weapons", index=0)
        cmd.execute()
        assert len(data["weapons"]) == 1
        assert data["weapons"][0]["name"] == "b"

    def test_remove_undo(self):
        data = {"weapons": [{"name": "a"}, {"name": "b"}]}
        cmd = ArrayRemoveCommand(data=data, path="weapons", index=0)
        cmd.execute()
        cmd.undo()
        assert len(data["weapons"]) == 2
        assert data["weapons"][0]["name"] == "a"


class TestCommandStack:
    def test_execute_and_undo(self):
        stack = CommandStack()
        data = {"health": 100}
        stack.execute(SetFieldCommand(data=data, path="health", new_value=200))
        assert data["health"] == 200
        stack.undo()
        assert data["health"] == 100

    def test_redo(self):
        stack = CommandStack()
        data = {"health": 100}
        stack.execute(SetFieldCommand(data=data, path="health", new_value=200))
        stack.undo()
        stack.redo()
        assert data["health"] == 200

    def test_can_undo_empty(self):
        stack = CommandStack()
        assert not stack.can_undo

    def test_can_redo_empty(self):
        stack = CommandStack()
        assert not stack.can_redo

    def test_undo_clears_redo_on_new_command(self):
        stack = CommandStack()
        data = {"health": 100}
        stack.execute(SetFieldCommand(data=data, path="health", new_value=200))
        stack.undo()
        assert stack.can_redo
        stack.execute(SetFieldCommand(data=data, path="health", new_value=300))
        assert not stack.can_redo

    def test_on_change_callback(self):
        stack = CommandStack()
        calls = []
        stack.set_on_change(lambda: calls.append(1))
        data = {"x": 0}
        stack.execute(SetFieldCommand(data=data, path="x", new_value=1))
        assert len(calls) >= 1


class TestReplaceDataCommand:
    def test_replace_undo_and_redo_keep_the_shared_data_reference(self):
        data = {"type": "UnitType", "weapons": [{"bullet": {"damage": 10}}]}
        original_reference = data
        replacement = {"type": "UnitType", "weapons": [{"bullet": {"damage": 25}}], "health": 200}
        stack = CommandStack()

        stack.execute(ReplaceDataCommand(data, replacement))

        assert data is original_reference
        assert data == replacement
        stack.undo()
        assert data == {"type": "UnitType", "weapons": [{"bullet": {"damage": 10}}]}
        stack.redo()
        assert data == replacement

    def test_replace_snapshots_nested_values_against_later_caller_mutation(self):
        data = {"type": "Wall", "health": 100}
        replacement = {"type": "Wall", "requirements": [{"item": "copper", "amount": 10}]}

        command = ReplaceDataCommand(data, replacement)
        replacement["requirements"][0]["amount"] = 999
        command.execute()

        assert data["requirements"][0]["amount"] == 10
