# Copyright © 2012 Jakub Wilk <jwilk@jwilk.net>
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

import os
import re
import subprocess as ipc

from nose.tools import (
    assert_list_equal,
)

here = os.path.dirname(__file__)

parse_tags = re.compile('# ([A-Z]): ([\w-]+.*)').match

class fuzzy_str(str):

    _ellipsis = '<...>'
    _split = re.compile('({})'.format(re.escape(_ellipsis))).split

    def __init__(self, s):
        regexp = ''.join(
            '.*' if chunk == self._ellipsis else re.escape(chunk)
            for chunk in self._split(s)
        )
        self._regexp = re.compile('^{}$'.format(regexp))

    def __eq__(self, other):
        if isinstance(other, str):
            return self._regexp.match(other)
        else:
            return NotImplemented

def _test(path):
    path = os.path.relpath(os.path.join(here, path), start=os.getcwd())
    expected = []
    with open(path, 'rt', encoding='ASCII', errors='ignore') as file:
        for line in file:
            match = parse_tags(line)
            if not match:
                break
            expected += [fuzzy_str('{code}: {path}: {tag}'.format(
                code=match.group(1),
                path=path,
                tag=match.group(2)
            ))]
    prog = os.path.join(here, os.pardir, os.pardir, 'gettext-inspector')
    stdout = ipc.check_output([prog, path])
    stdout = stdout.decode('ASCII').splitlines()
    assert_list_equal(stdout, expected)

def test():
    for root, dirnames, filenames in os.walk(here):
        for filename in filenames:
            if not filename.endswith('.po'):
                continue
            path = os.path.relpath(os.path.join(root, filename), start=here)
            yield _test, path

# vim:ts=4 sw=4 et
