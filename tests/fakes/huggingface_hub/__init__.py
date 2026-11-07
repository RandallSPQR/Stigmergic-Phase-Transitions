"""A stand-in for huggingface_hub's HfApi (upload_folder, list_repo_tree) backed by a local folder, for tests of the
pod script's upload step. FAKE_HF_REMOTE names the folder. delete_patterns follow huggingface_hub's rule: remote files
under path_in_repo that match a pattern are deleted unless uploaded in the same commit."""
import fnmatch, os, shutil
from pathlib import Path


class _F:
    def __init__(self, path, size):
        self.path, self.size = path, size


class HfApi:
    def upload_folder(self, repo_id, repo_type, folder_path, path_in_repo, commit_message="", delete_patterns=None):
        root = Path(os.environ["FAKE_HF_REMOTE"]) / path_in_repo
        up = {str(p.relative_to(folder_path)) for p in Path(folder_path).rglob("*") if p.is_file()}
        if delete_patterns and root.exists():
            for p in [q for q in root.rglob("*") if q.is_file()]:
                rel = str(p.relative_to(root))
                if rel not in up and any(fnmatch.fnmatch(rel, pat) for pat in delete_patterns):
                    p.unlink()
        for rel in up:
            (root / rel).parent.mkdir(parents=True, exist_ok=True); shutil.copy2(Path(folder_path) / rel, root / rel)

    def list_repo_tree(self, repo_id, repo_type, path_in_repo, recursive=True):
        root = Path(os.environ["FAKE_HF_REMOTE"])
        return [_F(str(p.relative_to(root)), p.stat().st_size) for p in (root / path_in_repo).rglob("*") if p.is_file()]


def snapshot_download(repo_id, repo_type=None, allow_patterns=None, local_dir=None, **kw):
    """Stand-in: the local remote folder (FAKE_HF_REMOTE) plays the downloaded snapshot."""
    return os.environ["FAKE_HF_REMOTE"]
