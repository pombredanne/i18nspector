# Copyright © 2014 Jakub Wilk <jwilk@jwilk.net>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the “Software”), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import collections
import re

_directive_re = re.compile('''
    (?P<literal> [^%]+ ) |
    (
        %
        (?P<index> [0-9]+[$] )?
        (?P<flags> [#0 +'I-]* )
        (?:
            (?P<width> [1-9][0-9]* ) |
            (?P<varwidth> [*] ) (?P<varwidth_index> [0-9]+[$] )?
        )?
        (?:
            [.]
            (?:
                (?P<precision> [0-9]* ) |
                (?P<varprec> [*] ) (?P<varprec_index> [0-9]+[$] )?
            )
        )?
        (?:
            (?P<length>
                hh? | ll? | [qjzZt] | L
            )?
            (?P<conversion>
                [diouxXeEfFgGaAcsCSpnm%]
            ) |
            < (?: PRI (?P<c99conv>[diouxX]) (?P<c99len> (?:LEAST|FAST)?(?:8|16|32|64)|MAX|PTR) ) >
        )
    )
''', re.VERBOSE)

class _info:

    oct_cvt = 'o'
    hex_cvt = 'xXaA'
    dec_cvt = 'diufFgG'
    float_cvt = 'aAeEfFgG'
    uint_cvt = 'ouxX'
    int_cvt = 'di' + uint_cvt
    str_cvt = 'sS'

    int_types = '''
    hh = signed char | unsigned char
    h = short int | unsigned short int
    l = long int | unsigned long int
    ll = long long int | unsigned long long int
    q = long long int | unsigned long long int
    j = intmax_t | uintmax_t
    z = ssize_t | size_t
    Z = ssize_t | size_t
    t = ptrdiff_t | [unsigned ptrdiff_t]
    = int | unsigned int
    '''
    # FIXME: GNU libc seems to allow Ld (and friends), contrary to POSIX
    int_types = dict(
        (key, tuple(str.strip(v) for v in values.split('|')))
        for line in int_types.strip().splitlines()
        for key, values in [map(str.strip, line.split('='))]
    )

INT_MAX = (1 << 31) - 1  # on most architectures
NL_ARGMAX = 4096  # on GNU/Linux

class FormatError(Exception):
    message = 'invalid conversion specification'

# errors in argument indexing:

class ForbiddenArgumentIndex(FormatError):
    message = 'argument index not allowed'

class ArgumentRangeError(FormatError):
    message = 'argument index too small or too large'

class MissingArgument(FormatError):
    message = 'missing argument'

class ArgumentTypeMismatch(FormatError):
    message = 'argument type mismatch'

class ArgumentNumberingMixture(FormatError):
    message = 'mixed numbered and unnumbered argument specifications'

# errors in length modifiers:

class LengthError(FormatError):
    message = 'invalid length modifier'

# errors in flag characters:

class FlagError(FormatError):
    message = 'unexpected format flag character'

class RedundantFlag(FormatError):
    message = 'redundant flag character'

# errors in field width:

class WidthError(FormatError):
    message = 'unexpected width'

class WidthRangeError(FormatError):
    message = 'field width too large'

# errors in precision:

class PrecisionError(FormatError):
    message = 'unexpected precision'

class PrecisionRangeError(FormatError):
    message = 'precision too large'


class VariableWidth(object):

    type = 'int'

    def __init__(self, parent):
        self._parent = parent

class VariablePrecision(object):

    type = 'int'

    def __init__(self, parent):
        self._parent = parent

class FormatString(object):

    def __init__(self, s):
        self._items = items = []
        self._argument_map = collections.defaultdict(list)
        self._next_arg_index = 1
        self.warnings = []
        last_pos = 0
        for match in _directive_re.finditer(s):
            if match.start() != last_pos:
                raise FormatError(s[last_pos:])
            last_pos = match.end()
            literal = match.group('literal')
            if literal is not None:
                items += [literal]
            else:
                items += [Conversion(self, match)]
        if last_pos != len(s):
            raise FormatError(s[last_pos:])
        self.arguments = []
        for i in range(1, NL_ARGMAX + 1):
            if not self._argument_map:
                break
            try:
                args = self._argument_map.pop(i)
            except KeyError:
                raise MissingArgument(s, i)
            self.arguments += [args]
        assert not self._argument_map
        self._argument_map = None
        for i, args in enumerate(self.arguments, start=1):
            types = frozenset(a.type for a in args)
            if len(types) > 1:
                raise ArgumentTypeMismatch(i, types)

    def add_argument(self, n, value):
        if self._argument_map is None:
            raise RuntimeError('arguments already initialized')
        if n is None:
            if self._next_arg_index is None:
                raise IndexError
            else:
                n = self._next_arg_index
                self._next_arg_index += 1
        else:
            if self._next_arg_index is None:
                pass
            elif self._next_arg_index == 1:
                assert not self._argument_map
                self._next_arg_index = None
            else:
                raise IndexError
        self._argument_map[n] += [value]

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)

class Conversion(object):

    type = None

    def __init__(self, parent, match):
        i = _info
        self._s = s = match.string[slice(*match.span())]
        # length and conversion:
        c99conversion = match.group('c99conv')
        c99length = match.group('c99len')
        length = match.group('length')
        conversion = match.group('conversion')
        tp = None
        if c99conversion is not None:
            assert c99length is not None
            if c99conversion in 'di':
                tp = 'int'
            elif c99conversion in 'ouxX':
                tp = 'uint'
            else:
                # should not happen
                assert 0  # <no-coverage>
            conversion = c99conversion
            if c99length.startswith(('LEAST', 'FAST')):
                tp += '_' + c99length.lower()
            else:
                tp += c99length.lower()
            tp += '_t'
        elif conversion in i.int_cvt + 'n':
            tp = i.int_types.get(length or '')
            # TODO: “q” and “t” are obsolete; emit a warning
            if tp is not None:
                tp = tp[conversion in i.uint_cvt]
                if conversion == 'n':
                    tp += ' *'
        elif conversion in i.float_cvt:
            if length is None:
                tp = 'double'
            elif length == 'L':
                tp = 'long double'
        elif conversion == 'c':
            if length is None:
                tp = '[int converted to unsigned char]'
            elif length == 'l':
                tp = 'wint_t'
        elif conversion == 'C':
            # TODO: “C” is obsolete; emit a warning
            if length is None:
                tp = 'wint_t'
        elif conversion == 's':
            if length is None:
                tp = 'const char *'
            elif length == 'l':
                tp = 'const wchar_t *'
        elif conversion == 'S':
            # TODO: “S” is obsolete; emit a warning
            if length is None:
                tp = 'const wchar_t *'
        elif conversion == 'p':
            if length is None:
                tp = 'void *'
        elif conversion in {'m', '%'}:
            if length is None:
                tp = 'void'
        else:
            # should not happen
            assert 0  # <no-coverage>
        if tp is None:
            assert length is not None
            raise LengthError(s, length)
        self.type = tp
        # flags:
        flags = collections.Counter(match.group('flags'))
        for flag, count in flags.items():
            if count != 1:
                parent.warnings += [RedundantFlag(s, flag, flag)]
            if conversion == 'n':
                raise FlagError(s, flag)
            if flag == '#':
                if conversion not in i.oct_cvt + i.hex_cvt + i.float_cvt:
                    raise FlagError(s, flag)
            elif flag == '0':
                if conversion not in i.int_cvt + i.float_cvt:
                    raise FlagError(s, flag)
            elif flag == "'":
                if conversion not in i.dec_cvt:
                    raise FlagError(s, flag)
            else:
                if conversion == '%':
                    raise FlagError(s, flag)
                assert flag in {'-', ' ', '+', 'I'}
        for f1, f2 in [('-', '0'), ('+', ' ')]:
            if (f1 in flags) and (f2 in flags):
                parent.warnings += [RedundantFlag(s, f1, f2)]
        # width:
        width = match.group('width')
        if width is not None:
            width = int(width)
            if width > INT_MAX:
                raise WidthRangeError(s, width)
        elif match.group('varwidth'):
            varwidth_index = match.group('varwidth_index')
            if varwidth_index is not None:
                varwidth_index = int(varwidth_index.rstrip('$'))
                if not (0 < varwidth_index <= NL_ARGMAX):
                    raise ArgumentRangeError(s, varwidth_index)
            parent.add_argument(varwidth_index, VariableWidth(self))
            width = ...
        if width is not None:
            if conversion in '%n':
                raise WidthError(s)
        # precision:
        precision = match.group('precision')
        if precision is not None:
            precision = int(precision or '0')
            if precision > INT_MAX:
                raise PrecisionRangeError(s)
        elif match.group('varprec'):
            varprec_index = match.group('varprec_index')
            if varprec_index is not None:
                varprec_index = int(varprec_index.rstrip('$'))
                if not (0 < varprec_index <= NL_ARGMAX):
                    raise ArgumentRangeError(s, varprec_index)
            parent.add_argument(varprec_index, VariablePrecision(self))
            precision = ...
        if precision is not None:
            if conversion in i.int_cvt + i.float_cvt + i.str_cvt:
                pass
            else:
                raise PrecisionError(s)
            if '0' in flags:
                parent.warnings += [RedundantFlag(s, '0')]
        # index:
        index = match.group('index')
        if index is not None:
            index = int(index.rstrip('$'))
            if not (0 < index <= NL_ARGMAX):
                raise ArgumentRangeError(s, index)
        if tp == 'void':
            if index is not None:
                if conversion == '%':
                    raise ForbiddenArgumentIndex(s)
                else:
                    # Although not specifically forbidden, having an argument index
                    # for %m (which doesn't consume any argument) doesn't make any
                    # sense. TODO: Emit a warning.
                    pass
            # XXX The printf(3) manpage says that numbered arguments can be
            # mixed only with %%. But practically, mixing them with %m (which
            # also doesn't consume any argument) must be also allowed.
        else:
            try:
                parent.add_argument(index, self)
            except IndexError:
                raise ArgumentNumberingMixture(s)

# vim:ts=4 sw=4 et
