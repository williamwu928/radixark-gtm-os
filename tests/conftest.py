import os, sys, pathlib, shutil, tempfile
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
TMP = tempfile.mkdtemp()
# isolated data dir with the real seed, aliases, taxonomy and the frozen LF snapshot
shutil.copytree(ROOT / "data" / "seed", pathlib.Path(TMP) / "seed")
shutil.copytree(ROOT / "data" / "sources", pathlib.Path(TMP) / "sources")
os.environ["GTM_DATA_DIR"] = TMP
os.environ["DATABASE_URL"] = f"sqlite:///{TMP}/test.db"
