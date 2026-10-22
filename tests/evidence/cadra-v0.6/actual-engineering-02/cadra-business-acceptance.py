from pathlib import Path
import importlib, json, sys
root=Path(sys.argv[1]).resolve(); mode=sys.argv[2]
sys.path.insert(0,str(root))
prefix=importlib.import_module('prefix'); greeting=importlib.import_module('greeting')
assert prefix.greeting_prefix()=='Hello'
results=[]
for value in ['', 'Ada', ' Ada ', '   ', '\tAda\n', '\t\n', 'Ada Lovelace', '  Ada  Lovelace  ']:
    name=value.strip() if mode=='trim' else value
    expected='Hello, '+(name if name else 'world')+'!'
    actual=greeting.greet(value)
    assert actual==expected,(value,expected,actual)
    results.append({'input':value,'expected':expected,'actual':actual})
print(json.dumps({'mode':mode,'cases':len(results),'passed':True,'results':results},ensure_ascii=False,indent=2))
