"""Static notebook checks; no Colab GPU or model execution is claimed here."""
import ast
import json
from pathlib import Path


def test_notebook_compiles_and_embeds_current_runtime_without_external_code_uploads():
    root = Path(__file__).resolve().parents[2]
    notebook = json.loads((root / 'notebooks/WebQA_Cloud_LLM.ipynb').read_text())
    code_cells = [c for c in notebook['cells'] if c['cell_type'] == 'code']
    assert len(code_cells) == 5
    for index, cell in enumerate(code_cells):
        source = ''.join(cell['source'])
        compile(source, f'notebook-cell-{index}', 'exec')
        assert cell['outputs'] == []
    tree = ast.parse(''.join(code_cells[0]['source']))
    bundle_node = next(n for n in tree.body if isinstance(n, ast.Assign) and
                       any(isinstance(t, ast.Name) and t.id == 'BUNDLED_FILES' for t in n.targets))
    bundle = ast.literal_eval(bundle_node.value)
    for name, contents in bundle.items():
        if name.startswith('webqa/'):
            assert contents == (root / 'src' / name).read_text()
        if name.endswith('.py'):
            compile(contents, name, 'exec')
    assert 'Cloud-Inbox' in str(notebook)
    assert (root / 'src/webqa/assets/WebQA_Cloud_LLM.ipynb').read_bytes() == (root / 'notebooks/WebQA_Cloud_LLM.ipynb').read_bytes()
