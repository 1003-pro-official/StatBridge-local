"""Fully read first-party text/code, index call sites without executing the app."""
from pathlib import Path
import os,ast,json,re,hashlib,collections,subprocess
ROOT=Path(__file__).resolve().parents[1];PRODUCT=ROOT.parent/'StatBridge'/'StatBridge-local1'
SKIP={'.git','.venv','.venv_runtime','node_modules','dist','__pycache__','.pytest_cache','runtime_data','evaluation_runs','output','outputs','.mypy_cache','.ruff_cache'}
EXT={'.py','.js','.jsx','.ts','.tsx','.cjs','.mjs','.css','.json','.jsonl','.md','.txt','.toml','.yaml','.yml','.cmd','.bat','.ps1','.csv','.html','.ini','.cfg'}
inventory=[];modules=[];excluded=collections.Counter();errors=[]
for folder,dirs,files in os.walk(PRODUCT):
    allowed=[]
    for d in dirs:
        if d in SKIP or 'StatBridge-evaluation-private' in d:excluded['dependency/generated/private/runtime_directories']+=1
        else:allowed.append(d)
    dirs[:]=allowed
    for name in files:
        p=Path(folder)/name;rel=p.relative_to(PRODUCT).as_posix()
        if name.startswith('.env') and name!='.env.example':excluded['credential_configuration']+=1;continue
        if 'holdout' in name.lower() or 'private' in rel.lower() or '/data/tables/' in '/'+rel:excluded['private_holdout_or_raw_data']+=1;continue
        if p.suffix.lower() not in EXT and name not in ['requirements.txt','Dockerfile','Makefile']:excluded['binary_or_other_file']+=1;continue
        raw=p.read_bytes()
        try:text=raw.decode('utf-8-sig')
        except UnicodeError:
            try:text=raw.decode('cp949')
            except UnicodeError:excluded['unknown_encoding']+=1;continue
        entry={'path':rel,'bytes':len(raw),'lines':len(text.splitlines()),'sha256':hashlib.sha256(raw).hexdigest(),'read_mode':'full_text'}
        inventory.append(entry)
        if p.suffix=='.py':
            try:
                tree=ast.parse(text,filename=rel)
                def callname(n):
                    if isinstance(n,ast.Name):return n.id
                    if isinstance(n,ast.Attribute):return callname(n.value)+'.'+n.attr
                    return '<expression>'
                functions=[]
                for node in ast.walk(tree):
                    if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
                        functions.append({'name':node.name,'line':node.lineno,'end_line':node.end_lineno,'calls':sorted({callname(n.func) for n in ast.walk(node) if isinstance(n,ast.Call)}),'decorators':[ast.unparse(d) for d in node.decorator_list]})
                modules.append({'path':rel,'imports':[ast.unparse(n) for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom))],'functions':functions,'classes':[n.name for n in ast.walk(tree) if isinstance(n,ast.ClassDef)]})
            except SyntaxError as exc:errors.append({'path':rel,'line':exc.lineno,'type':'SyntaxError'})
        elif p.suffix.lower() in {'.ts','.tsx','.js','.jsx','.mjs','.cjs'}:
            modules.append({'path':rel,'imports':re.findall(r'\b(?:import|export)[^;\n]*?from\s*[\'\"]([^\'\"]+)',text),'functions':re.findall(r'(?:export\s+)?(?:async\s+)?function\s+(\w+)',text),'http_route_strings':sorted(set(re.findall(r'[\'\"](/api/[^\'\"\s]+)',text)))})
out={'root':str(PRODUCT),'scope':'all fully read first-party text; Python AST + JS/TS import/route index; binaries/dependencies/secrets/runtime/private holdout excluded','files':len(inventory),'bytes_read':sum(x['bytes'] for x in inventory),'counts_by_extension':dict(collections.Counter(Path(x['path']).suffix for x in inventory)),'exclusions':dict(excluded),'syntax_errors':errors,'inventory':inventory,'modules':modules}
(ROOT/'audit/evidence/full_source_read_index.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in out.items() if k not in ['inventory','modules']},ensure_ascii=False))
