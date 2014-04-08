r"""Simple Python templates

USAGE
------
`render()` compiles and renders a template, returning a string:

>>> render('Hello {{name}}!', name='World')
'Hello World!'

`compile()` compiles a template into a function for later use:

>>> func = compile('Hello {{name}}!', args=['name'])
>>> func('World')
'Hello World!'

SYNTAX
-------
Inline statements are of the form {{...}}. Any single python expression
that can be evaluated using `eval()` is allowed:

>>> render('{{1 + 1}}')
'2'

Control structures are also allowed within inline expressions. However,
they have to be explictly closed using the special keyword `end`:

>>> render('{{for x in range(10):}}{{x}} {{end}}')
'0 1 2 3 4 5 6 7 8 9 '

Blocks of python code can be embedded using <%...%>:

>>> render('<%x = 42%>x is {{x}}')
'x is 42'

Tokens can be escaped using the backslash character:

>>> render(r'\<%x = 42%>')
'<%x = 42%>'

Placing a minus sign (-) at the start or end of a code block or inline
statement will remove all whitespace before or after that block
respectively:

>>> render('''{{ for x in range(10): -}}
...     {{x}}
... {{-end}}''')
'0123456789'

"""
import re
import sys
import inspect
import signal
import optparse

__license__ = 'MIT'
__version__ = '0.9.0'
__all__ = ['compile', 'render']


# Keep a reference to the builtin compile() as we will override the name later
__compile = compile


class Parser(object):
    _re_tok = r"""
    # 1: All kinds of python strings
    ([urbURB]?
        (?:''(?!') # Empty string
        | ""(?!") # Empty string
        | '{6} # Empty string
        | "{6} # Empty string
        | '(?:[^\\']|\\.)+?'
        | "(?:[^\\"]|\\.)+?"
        | '{3}(?:[^\\]|\\.|\n)+?'{3}
        | "{3}(?:[^\\]|\\.|\n)+?"{3}
        )
    )
    # 2: Comments (until end of line, but not the newline itself)
    | (\#.*)
    # 3, 4: Keywords that start or continue a python block (only start of line)
    | ^([ \t]*(?:if|for|while|with|try|def|class)\b)
    | ^([ \t]*(?:elif|else|except|finally)\b)
    # 5: The special 'end' keyword (but only if it stands alone)
    | ((?:^|;)[ \t]*end[ \t]*(?=(?:-?%(inline_end)s[ \t]*)?\r?|;|\#))
    # 6: End of code block token
    | (-?%(inline_end)s | -?%(block_end)s)
    # 7: A single newline
    | (\r?\n)
    """
    _re_split = r'(\\?)((%(inline_start)s-?\s*)|(%(block_start)s-?\s*))'

    def __init__(self, block_start='<%', block_end='%>', inline_start='{{',
                 inline_end='}}', listname='_tempy_out'):
        self.block_start = block_start
        self.block_end = block_end
        self.inline_start = inline_start
        self.inline_end = inline_end
        self.listname = listname
        pattern_vars = {'block_start': block_start, 'block_end': block_end,
                        'inline_start': inline_start, 'inline_end': inline_end}
        self.re_tok = re.compile(self._re_tok % pattern_vars,
                                 re.MULTILINE | re.VERBOSE)
        self.re_split = re.compile(self._re_split % pattern_vars,
                                   re.MULTILINE)
        self.out = []  # Output code

    def parse(self, src):
        self._src = src
        self._text = []  # Text buffer
        self._text_rstrip = False  # str.rstrip() on the next _flush_text
        self._text_lstrip = False  # str.lstrip() on the next _flush_text
        self._indent_cur = 0  # Current indent level
        self._indent_mod = 0  # Indent level change after _write_line
        while True:
            m = self.re_split.search(self._src)
            if m:
                self._text.append(self._src[:m.start()])
                self._src = self._src[m.end():]
                if m.group(1):  # Escaped start block
                    self._text.append(m.group(2))
                    continue
                # Start of code block
                if m.group(0).rstrip().endswith('-'):
                    self._text_rstrip = True
                self._flush_text()
                self._parse_code(inline=bool(m.group(3)))
            else:
                break
        self._text.append(self._src)
        self._flush_text()

    def _write_line(self, line):
        if line:
            self.out.append('  ' * self._indent_cur + line)
        self._indent_cur += self._indent_mod  # Apply indent modification
        self._indent_mod = 0

    def _flush_text(self):
        text = ''.join(self._text)
        if self._text_rstrip:
            text = text.rstrip()
            self._text_rstrip = False
        if self._text_lstrip:
            text = text.lstrip()
            self._text_lstrip = False
        if text:
            self._write_line('{0}.append({1!r})'.format(self.listname, text))
        self._text = []

    def _parse_code(self, inline):
        is_control = False
        code_end = self.inline_end if inline else self.block_end
        self._code = []  # Code buffer
        while True:
            m = self.re_tok.search(self._src)
            if not m:
                raise Exception('Non-terminated code block')
            self._code.append(self._src[:m.start()])
            self._src = self._src[m.end():]
            _str, _com, _blk1, _blk2, _end, _cend, _nl = m.groups()
            if (_blk1 or _blk2) and self._code and self._code[-1].strip():
                # a if b else c
                self._code.append(_blk1 or _blk2)
                continue
            if _str:  # Python string
                self._code.append(_str)
            elif _com:  # Python comment (up to EOL)
                # Comment can still end with block_end or inline_end
                _com = _com.rstrip()
                if _com.endswith(code_end):
                    return self._end_code(inline, is_control,
                                          _com[-len(code_end) - 1:])
            elif _blk1:  # Start of block keyword
                self._code.append(_blk1)
                is_control = True
                if inline:
                    self._indent_mod += 1
            elif _blk2:
                self._code.append(_blk2)
                is_control = True
                if inline:
                    self._indent_cur -= 1
                    self._indent_mod += 1
            elif _end:
                is_control = True
                if inline:
                    self._indent_mod -= 1
            elif _cend:
                return self._end_code(inline, is_control, _cend)
            elif _nl:
                if not inline:
                    self._write_line(''.join(self._code).rstrip())
                    self._code = []
                    is_control = False

    def _end_code(self, inline, is_control, cend):
        code = ''.join(self._code)
        if inline:
            if is_control:
                self._write_line(code.strip())
            elif code.strip():
                tpl = '{0}.append(str(eval({1!r})))'
                self._write_line(tpl.format(self.listname, code.strip()))
        else:
            self._write_line(code.rstrip())
        if cend.startswith('-'):
            self._text_lstrip = True
        self._code = []


def compile(src, name='template', args=(), varargs=None, varkw=None,
            defaults=None, filename='<string>', listname='_tempy_out',
            block_start='<%', block_end='%>', inline_start='{{',
            inline_end='}}'):
    """Compiles template `src` into a function.

    `args` is a list of argument names of the function, and
    `varargs` and `varkw` are the names of the * and ** arguments.
    `defaults` is a list specifying the default arguments. If the list
    has `n` arguments, they correspond to the last `n` elements listed in
    `args`. The beginning and ending tokens of blocks and inline statements
    can be set using the `block_start`, `block_end`, `inline_start` and
    `inline_end` arguments respectively.
    """
    locals = {}
    p = Parser(block_start, block_end, inline_start, inline_end, listname)
    p.parse(src)
    args_str = inspect.formatargspec(args, varargs, varkw, defaults)
    out = ['def {0}{1}:'.format(name, args_str),
           '  {0} = []'.format(listname)]
    out.extend(['  ' + x for x in p.out])
    out.append("  return ''.join({0})".format(listname))
    code = __compile('\n'.join(out), filename, 'exec')
    eval(code, globals(), locals)
    return locals[name]


def render(src, **kwargs):
    """Renders template `src` with the variables in `kwargs`."""
    p = Parser(listname='_tempy_out')
    p.parse(src)
    out = ['_tempy_out = []']
    out.extend(p.out)
    code = __compile('\n'.join(out), '<string>', 'exec')
    eval(code, globals(), kwargs)
    return ''.join(kwargs['_tempy_out'])


def main(args):
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    p = optparse.OptionParser(usage='usage: %prog [-o FILE] [TEMPLATE]')
    p.add_option('--version', default=None, action='store_true',
                 help='Print version information and exit')
    p.add_option('-o', '--output', default=None, metavar='FILE',
                 help='Write output to FILE [default: stdout]')
    opts, args = p.parse_args(args)
    if opts.version:
        print('tempy {0}'.format(__version__))
        return 0
    if len(args) > 1:
        p.error('incorrect number of arguments')
    fo = open(opts.output, 'w') if opts.output else sys.stdout
    if not args or args[0] == '-':
        fi = sys.stdin
    else:
        fi = open(args[0], 'r')
    fo.write(render(fi.read()))
    fo.close()
    fi.close()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
