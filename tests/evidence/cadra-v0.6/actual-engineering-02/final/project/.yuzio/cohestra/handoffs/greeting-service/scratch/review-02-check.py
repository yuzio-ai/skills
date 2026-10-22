from greeting import greet
from unittest.mock import patch
cases=[('', 'world'), (' \t\n','world'), ('\u00a0','world'), ('\u2003 Ada \u3000','Ada'), (' A\t B ', 'A\t B'), (' \0 ', '\0'), (' \u200b ', '\u200b'), (' e\u0301 ', 'e\u0301'), (' 你好🌍 ', '你好🌍'), (' world ', 'world')]
for raw,expected in cases:
 actual=greet(raw)
 assert actual=='Hello, '+expected+'!', (repr(raw),actual,expected)
 print(repr(raw), '=>',repr(actual))
with patch('greeting.greeting_prefix',side_effect=['X','Y']) as prefix:
 assert greet(' A ')=='X, A!'
 assert greet('\u00a0')=='Y, world!'
 assert prefix.call_args_list==[(),()]
print('10 boundary cases and 2 dynamic-prefix calls passed')
