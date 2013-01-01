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

import contextlib
import functools
import os
import shutil
import sys
import tempfile

_tmp_prefix = 'i18nspector.tests.'

temporary_file = functools.partial(
    tempfile.NamedTemporaryFile,
    prefix=_tmp_prefix,
)

@contextlib.contextmanager
def temporary_directory():
    tmpdir = tempfile.mkdtemp(prefix=_tmp_prefix)
    try:
        yield tmpdir
    finally:
        shutil.rmtree(tmpdir)

basedir = os.path.join(
    os.path.dirname(__file__),
    os.pardir,
)
basedir = os.environ.get('I18NSPECTOR_BASEDIR', basedir)
basedir = os.path.join(basedir, '')
os.stat(basedir)
datadir = os.path.join(basedir, 'data')
os.stat(datadir)
sys.path[:0] = [basedir]

# vim:ts=4 sw=4 et