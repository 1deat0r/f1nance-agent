import os
import tempfile
import unittest

from f1nance.core import (
    KINDS,
    RETRACTED,
    Fact,
    MemoryStore,
    render_json,
    render_markdown,
    write_view,
)


class FactTest(unittest.TestCase):
    def test_add_assigns_identity(self):
        s = MemoryStore(os.path.join(tempfile.mkdtemp(), "s.json"))
        f = s.add("a fact", "memory", "test")
        self.assertTrue(f.id)
        self.assertTrue(f.created_at)
        self.assertTrue(f.active)
        self.assertEqual(f.kind, "memory")

    def test_add_blank_content_raises(self):
        s = MemoryStore(os.path.join(tempfile.mkdtemp(), "s.json"))
        with self.assertRaises(ValueError):
            s.add("   ", "memory", "test")

    def test_add_unknown_kind_raises(self):
        s = MemoryStore(os.path.join(tempfile.mkdtemp(), "s.json"))
        with self.assertRaises(ValueError):
            s.add("x", "gossip", "test")

    def test_all_kinds_accepted(self):
        s = MemoryStore(os.path.join(tempfile.mkdtemp(), "s.json"))
        for kind in KINDS:
            s.add(f"{kind} fact", kind, "test", persist=False)
        self.assertEqual(len(s.facts), len(KINDS))


class SupersedeTest(unittest.TestCase):
    def _store(self):
        return MemoryStore(os.path.join(tempfile.mkdtemp(), "s.json"))

    def test_supersede_marks_old_inactive(self):
        s = self._store()
        a = s.add("old", "memory", "test")
        b = s.add("new", "memory", "test", supersedes=[a.id])
        self.assertFalse(a.active)
        self.assertEqual(a.superseded_by, b.id)

    def test_active_excludes_superseded(self):
        s = self._store()
        a = s.add("old", "memory", "test")
        s.add("new", "memory", "test", supersedes=[a.id])
        self.assertEqual([f.content for f in s.active("memory")], ["new"])

    def test_history_reconstructs_chain_oldest_first(self):
        s = self._store()
        a = s.add("v1", "memory", "test")
        b = s.add("v2", "memory", "test", supersedes=[a.id])
        c = s.add("v3", "memory", "test", supersedes=[b.id])
        chain = s.history(c.id)
        self.assertEqual([f.content for f in chain], ["v1", "v2", "v3"])

    def test_history_from_middle_walks_to_newest(self):
        s = self._store()
        a = s.add("v1", "memory", "test")
        b = s.add("v2", "memory", "test", supersedes=[a.id])
        s.add("v3", "memory", "test", supersedes=[b.id])
        chain = s.history(a.id)
        self.assertEqual([f.content for f in chain], ["v1", "v2", "v3"])

    def test_supersede_unknown_id_is_noop(self):
        s = self._store()
        f = s.add("x", "memory", "test", supersedes=["nope"])
        self.assertTrue(f.active)


class RetractTest(unittest.TestCase):
    def _store(self):
        return MemoryStore(os.path.join(tempfile.mkdtemp(), "s.json"))

    def test_retract_marks_inactive_with_sentinel(self):
        s = self._store()
        f = s.add("x", "memory", "test")
        s.retract(f.id)
        self.assertEqual(f.superseded_by, RETRACTED)
        self.assertFalse(f.active)

    def test_retract_excludes_from_active_and_export(self):
        s = self._store()
        f = s.add("x", "memory", "test")
        s.retract(f.id)
        self.assertEqual(s.active("memory"), [])
        self.assertEqual(s.export(), {})

    def test_retract_unknown_returns_none(self):
        s = self._store()
        self.assertIsNone(s.retract("nope"))

    def test_retract_inactive_returns_none(self):
        s = self._store()
        a = s.add("x", "memory", "test")
        s.add("y", "memory", "test", supersedes=[a.id])
        self.assertIsNone(s.retract(a.id))

    def test_retracted_fact_recoverable_by_history(self):
        s = self._store()
        f = s.add("x", "memory", "test")
        s.retract(f.id)
        self.assertEqual(len(s.history(f.id)), 1)


class HistoryTest(unittest.TestCase):
    def test_history_unknown_returns_empty(self):
        s = MemoryStore(os.path.join(tempfile.mkdtemp(), "s.json"))
        self.assertEqual(s.history("nope"), [])


class ExportTest(unittest.TestCase):
    def test_groups_by_kind(self):
        s = MemoryStore(os.path.join(tempfile.mkdtemp(), "s.json"))
        s.add("m", "memory", "t")
        s.add("u", "user", "t")
        self.assertEqual(s.export(), {"user": ["u"], "memory": ["m"]})

    def test_empty_store_exports_empty(self):
        s = MemoryStore(os.path.join(tempfile.mkdtemp(), "s.json"))
        self.assertEqual(s.export(), {})


class PersistenceTest(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "store.json")
            s = MemoryStore(path)
            s.add("hello", "memory", "test")
            s.add("world", "identity", "test")
            loaded = MemoryStore(path)
        self.assertEqual([f.content for f in loaded.active("memory")], ["hello"])
        self.assertEqual([f.content for f in loaded.active("identity")], ["world"])

    def test_supersede_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "store.json")
            s = MemoryStore(path)
            a = s.add("old", "memory", "test")
            s.add("new", "memory", "test", supersedes=[a.id])
            loaded = MemoryStore(path)
        self.assertEqual([f.content for f in loaded.active("memory")], ["new"])
        self.assertEqual([f.content for f in loaded.history(a.id)], ["old", "new"])

    def test_mutate_reloads_latest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "store.json")
            s1 = MemoryStore(path)
            s1.add("from s1", "memory", "test")
            s2 = MemoryStore(path)
            with s2.mutate():
                s2.add("from s2", "memory", "test")
            # s1 is now stale in memory; mutate() must reload before acting
            with s1.mutate():
                self.assertEqual(len(s1.facts), 2)

    def test_missing_store_starts_empty(self):
        s = MemoryStore(os.path.join(tempfile.mkdtemp(), "does-not-exist.json"))
        self.assertEqual(s.facts, [])


class ProjectorTest(unittest.TestCase):
    def _store(self):
        s = MemoryStore(os.path.join(tempfile.mkdtemp(), "s.json"))
        s.add("sovereign agent", "identity", "bootstrap")
        s.add("DeepSeek-v4-pro", "directive", "bootstrap")
        return s

    def test_render_has_sections(self):
        md = render_markdown(self._store())
        self.assertIn("## Identity", md)
        self.assertIn("## Directives", md)
        self.assertIn("sovereign agent", md)

    def test_render_excludes_retracted(self):
        s = self._store()
        f = s.add("secret", "memory", "test")
        s.retract(f.id)
        md = render_markdown(s)
        self.assertNotIn("secret", md)

    def test_render_json_matches_export(self):
        s = self._store()
        self.assertEqual(render_json(s), s.export())

    def test_write_view_writes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "STATE.md")
            write_view(self._store(), out)
            self.assertTrue(os.path.exists(out))
            with open(out, encoding="utf-8") as fh:
                self.assertIn("## Identity", fh.read())


class FactShapeTest(unittest.TestCase):
    def test_fact_is_a_dataclass_instance(self):
        s = MemoryStore(os.path.join(tempfile.mkdtemp(), "s.json"))
        f = s.add("x", "memory", "test")
        self.assertIsInstance(f, Fact)


if __name__ == "__main__":
    unittest.main()
