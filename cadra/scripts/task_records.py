"""Shared parsing and source checks for Cadra Task documents."""

from pathlib import Path
import json
import re
import shutil
import subprocess

RUBY = r'''
require 'yaml'; require 'json'; require 'date'
def check(node)
  raise 'YAML aliases are not accepted' if node.is_a?(Psych::Nodes::Alias)
  if node.respond_to?(:tag) && node.tag
    raise 'unsupported YAML tag' unless node.tag.match(/\Atag:yaml.org,2002:(str|int|float|bool|null|map|seq|timestamp)\z/)
  end
  if node.is_a?(Psych::Nodes::Mapping)
    keys = node.children.each_slice(2).map { |k,v| k.value }
    raise 'duplicate YAML key' unless keys.uniq.length == keys.length
  end
  (node.children || []).each { |c| check(c) } if node.respond_to?(:children)
end
out = JSON.parse(STDIN.read).map do |raw|
  begin
    tree = Psych.parse_stream(raw)
    raise 'one YAML document required' unless tree.children.length == 1
    check(tree)
    {data: YAML.safe_load(raw, permitted_classes: [Date, Time], aliases: false)}
  rescue => e
    {error: 'invalid YAML header (' + e.class.name + ')'}
  end
end
print JSON.generate(out)
'''


def require(condition, message):
    if not condition:
        raise ValueError(message)


def yaml_batch(blocks, read_json):
    if not blocks:
        return []
    ruby = shutil.which('ruby')
    if not ruby:
        return [{'error': 'YAML parser unavailable: Ruby/Psych required'} for _ in blocks]
    try:
        proc = subprocess.run([ruby, '-e', RUBY], input=json.dumps(blocks), text=True,
                              capture_output=True, timeout=60, check=False)
        require(proc.returncode == 0, 'YAML parser failed')
        result = read_json(proc.stdout)
        require(isinstance(result, list) and len(result) == len(blocks), 'invalid YAML parser response')
        return result
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return [{'error': 'YAML parser unavailable or failed'} for _ in blocks]


def valid_slug(slug):
    return isinstance(slug, str) and re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug) is not None


def task_path(root, slug):
    require(valid_slug(slug), 'invalid Task slug')
    return Path(root) / 'tasks' / (slug + '.md')


def read_file(path, project):
    """Read only an unlinked regular file beneath the already resolved project."""
    require(path.is_relative_to(project) and '..' not in path.parts, f'path escapes project: {path}')
    for part in (path, *path.parents):
        if not part.is_relative_to(project):
            break
        require(not part.is_symlink(), f'linked path: {part}')
    try:
        info = path.stat()
    except FileNotFoundError:
        return None
    require(path.is_file() and info.st_nlink == 1, f'expected an unlinked regular file: {path}')
    return path.read_bytes()


def documents(raws, split_document, read_json):
    """Parse only the supplied Task documents, batching any YAML headers."""
    parsed = {}
    yaml_keys, blocks = [], []
    for key, raw in raws.items():
        block, body = split_document(raw)
        parsed[key] = dict(raw=raw, body=body)
        if block.lstrip().startswith('{'):
            parsed[key]['data'] = read_json(block)
        else:
            yaml_keys.append(key)
            blocks.append(block)
    for key, result in zip(yaml_keys, yaml_batch(blocks, read_json), strict=True):
        require('error' not in result, f"{key}: {result.get('error')}")
        parsed[key].update(result)
    return parsed


def requirement(body):
    section = re.search(r'^## Requirement\s*\n(.*?)(?=^## |\Z)', body, re.M | re.S)
    return section[1].strip() if section else None


def validate_task(data, slug, rules):
    require(data.get('slug') == slug and valid_slug(slug), 'Task identity mismatch')
    require(isinstance(data.get('title'), str) and data['title'].strip(), 'missing Task title')
    require(type(data.get('revision')) is int and data['revision'] > 0, 'invalid Task revision')
    require(data.get('preparation') in ('draft', 'ready'), 'invalid preparation')
    require(data.get('priority', 'medium') in ('high', 'medium', 'low'), 'invalid priority')
    require(data.get('cohestra_task') == f'.yuzio/cohestra/handoffs/{slug}/', 'Task binding mismatch')
    deps = data.get('dependencies', [])
    require(isinstance(deps, list) and all(isinstance(d, str) and d for d in deps), 'invalid dependencies')
    rules.normalize_flow(data.get('flow', 'code'), data['protocol'])


def same_definition(task, item):
    definition = item['definition']
    current = task['data']
    # Snapshots may add requirement/source_document; all Task header fields
    # must still match while owned by an unfinished Run.
    if any(definition.get(k) != v for k, v in current.items()):
        return False
    documents = [definition[k] for k in ('source_document', 'definition_record') if k in definition]
    if documents and any(not isinstance(value, str) or value != task['raw'].decode('utf-8') for value in documents):
        return False
    text = requirement(task['body'])
    if text is not None and 'requirement' in definition:
        return isinstance(definition['requirement'], str) and definition['requirement'].strip() == text
    return bool(documents)


def tail(entries, revision, protocol, unfinished_runs=()):
    if not entries:
        return None
    children = {}
    for run_id, item in entries.items():
        require(item['definition']['protocol'] == protocol, 'cross-protocol source chain is not supported')
        require('previous_run' in item, 'missing previous_run')
        previous = item['previous_run']
        require(previous is None or isinstance(previous, str) and previous in entries, 'missing source Run')
        require(previous not in unfinished_runs,
                f'Run lifecycle contradiction: unfinished predecessor {previous} has successor {run_id}')
        require(previous not in children, 'branched source chain')
        require(item['revision'] <= revision, 'Run revision exceeds Task')
        children[previous] = run_id
    seen, key, prior = set(), children.get(None), 0
    last = None
    while key is not None and key not in seen:
        seen.add(key)
        last = (key, entries[key])
        require(last[1]['revision'] >= prior, 'revision regressed along source chain')
        prior = last[1]['revision']
        key = children.get(key)
    require(key is None and len(seen) == len(entries), 'cyclic or disconnected source chain')
    return last
