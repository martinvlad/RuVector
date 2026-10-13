import io
import tarfile
import unittest
from prepare import chunks,gold_files,snapshot_documents
from retrieval import bm25,evaluate,file_ranking


class LocalizationTests(unittest.TestCase):
    def test_legacy_syntax_keeps_candidate(self):
        rows=chunks("pkg/a.py","print 'legacy'\n")
        self.assertEqual(rows[0]["kind"],"syntax-fallback")
        self.assertEqual(rows[0]["path"],"pkg/a.py")

    def test_source_never_executes(self):
        rows=chunks("pkg/a.py","raise RuntimeError('do not execute')\ndef f():\n return 1\n")
        self.assertEqual(len(rows),2)

    def test_archive_traversal_rejected(self):
        buffer=io.BytesIO()
        with tarfile.open(fileobj=buffer,mode="w:gz") as archive:
            item=tarfile.TarInfo("root/../evil.py");item.size=1;archive.addfile(item,io.BytesIO(b"x"))
        with self.assertRaises(ValueError):snapshot_documents(buffer.getvalue(),"pkg/")

    def test_ranking_and_complete_universe(self):
        docs=[dict(path="a.py",text="decode json response"),dict(path="b.py",text="network socket")]
        ranking=file_ranking(docs,bm25("decode json",docs))
        self.assertEqual(ranking[0]["path"],"a.py")
        self.assertEqual(evaluate(ranking,["a.py"])["mrr"],1)
        with self.assertRaises(ValueError):evaluate(ranking,["missing.py"])
        with self.assertRaises(ValueError):file_ranking(docs,[float("nan"),0])

    def test_labels_separate_and_production_only(self):
        patch="--- a/pkg/a.py\n+++ b/pkg/a.py\n--- a/tests/test_a.py\n+++ b/tests/test_a.py"
        self.assertEqual(gold_files(patch,"pkg/"),["pkg/a.py"])


if __name__=="__main__":unittest.main()
