================================
tempy - Simple Python templates
================================

tempy is a tiny (~200 SLOC) python template engine for text
processing tasks. It exposes the full functionality of Python
in your templates by passing everything to ``compile()`` and
``eval()`` with minimal processing.

Requirements
-------------

* Python 2.6+ (2.6, 2.7, 3.2, 3.3, 3.4)

Usage
------
The function `render` compiles and renders a template. Any keyword arguments
passed to it will be used as local variables::

    >>> import tempy
    >>> tempy.render('Hello {{name}}!', name='World')
    'Hello World!'

The function `compile` compiles a template into a function for later use::

    >>> import tempy
    >>> func = tempy.compile('Hello {{name}}!', args=['name'],
    ...                      defaults=['Bill'])
    >>> func('World')
    'Hello World!'
    >>> func()
    'Hello Bill!'

The resulting function signature can be controlled using the arguments `args`,
`varargs`, `varkw` and `defaults`. `args` is a list of argument names, 
`varargs` and `varkw` are the names of the ``*`` and ``**`` arguments,
and `defaults` is a list if default argument values. If `defaults` has
`n` elements, they correspond to the last `n` elements listed in `args`.

Template Syntax
----------------

Inline Expressions
~~~~~~~~~~~~~~~~~~~

Inline expressions are of the form ``{{...}}``. Any python
expression that can be evaluated using `eval` is allowed::

    >>> tempy.render('{{ 1 + 1 }}')
    '2'

Control Structures
~~~~~~~~~~~~~~~~~~~
The syntax for `inline expressions`_ can also be used for control structures
such as ``if``, ``for``, ``def`` and so forth. However, they
have to be explictly closed using the special keyword ``end``::

    >>> tempy.render('{{for x in range(10):}}{{x}} {{end}}')
    '0 1 2 3 4 5 6 7 8 9 '


Note, though, that special keywords like ``continue`` and ``pass`` are only
valid in `code blocks`_::

    >>> tempy.render('''{{for x in range(10):-}}
    ... <%- if x == 2: continue -%>
    ... {{x}} {{end}}''')
    '0 1 3 4 5 6 7 8 9 '

Code Blocks
~~~~~~~~~~~~
Blocks of python code embedded within ``<%...%>`` will be executed::

    >>> tempy.render('<% x = 42 %>x is {{x}}')
    'x is 42'

Note that python indentation rules apply within code blocks::

    >>> tempy.render('''<%
    ... out = []
    ... for x in range(10):
    ...   out.append(str(x))
    ... %>{{' '.join(out)}}''')
    '0 1 2 3 4 5 6 7 8 9'


Escaping
~~~~~~~~~
To escape a code block or inline statement, place a backslash
character (``\``) before the start of a code block or inline
statement token. For example::

    >>> tempy.render(r'\<%x = 42%>')
    '<%x = 42%>'

Whitespace Control
~~~~~~~~~~~~~~~~~~~
Placing a minus sign (``-``) at the start or end of a code block
or inline statement will remove all whitespace before or after
that block respectively::

    >>> tempy.render('{{if True:-}}  42  {{end}}')
    '42  '
    >>> tempy.render('{{if True:}}  42  {{-end}}')
    '  42'
    >>> tempy.render('{{if True:-}}  42  {{-end}}')
    '42'


License
--------
MIT License
