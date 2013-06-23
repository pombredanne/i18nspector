# Copyright © 2013 Jakub Wilk <jwilk@jwilk.net>
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

'''
MO file parser
'''

import re
import struct

import polib

little_endian_magic = b'\xde\x12\x04\x95'
big_endian_magic = little_endian_magic[::-1]

class SyntaxError(Exception):
    pass

class Parser(object):

    def __init__(self, path, *, encoding=None, check_for_duplicates=False, klass=None):
        self._encoding = encoding
        if check_for_duplicates:
            raise NotImplementedError
        with open(path, 'rb') as file:
            contents = file.read()
        self._view = memoryview(contents)
        if klass is None:
            klass = polib.MOFile
        try:
            self.instance = klass(
                fpath=path,
                check_for_duplicates=False,
            )
            self._parse()
        finally:
            del self._view

    def parse(self):
        return self.instance

    def _read_ints(self, at, n=1):
        begin = at
        end = at + 4 * n
        view = self._view
        if end > len(self._view):
            raise SyntaxError('truncated file')
        return struct.unpack(
            self._endian + 'I' * n,
            view[begin:end],
        )

    def _parse(self):
        view = self._view
        magic = view[:4].tobytes()
        if magic == little_endian_magic:
            self._endian = '<'
        elif magic == big_endian_magic:
            self._endian = '>'
        else:
            raise SyntaxError('unexpected magic')
        [revision] = self._read_ints(at=4)
        major_revision, minor_revision = divmod(revision, 1 << 16)
        if major_revision > 1:
            raise SyntaxError('unexpected major revision number: {n}'.format(n=major_revision))
        [n_strings] = self._read_ints(at=8)
        [msgid_offset, msgstr_offset] = self._read_ints(at=12, n=2)
        self._last_msgid = None
        for i in range(n_strings):
            entry = self._parse_entry(i, msgid_offset + 8 * i, msgstr_offset + 8 * i)
            self.instance.append(entry)

    def _parse_entry(self, i, msgid_offset, msgstr_offset):
        view = self._view
        [length, offset] = self._read_ints(at=msgid_offset, n=2)
        msgid = view[offset:offset+length].tobytes()
        try:
            if view[offset + length] != b'\0':
                raise SyntaxError('msgid is not null-terminated')
        except IndexError:
            raise SyntaxError('truncated file')
        msgids = msgid.split(b'\0', 2)
        msgid = msgids[0]
        if len(msgids) > 2:
            raise SyntaxError('unexpected null byte in msgid')
        [length, offset] = self._read_ints(at=msgstr_offset, n=2)
        msgstr = view[offset:offset+length].tobytes()
        try:
            if view[offset + length] != b'\0':
                raise SyntaxError('msgstr is not null-terminated')
        except IndexError:
            raise SyntaxError('truncated file')
        msgstrs = msgstr.split(b'\0')
        if len(msgids) == 1 and len(msgstrs) > 1:
            raise SyntaxError('unexpected null byte in msgstr')
        encoding = self._encoding
        if i == 0:
            if encoding is None:
                encoding = 'ASCII'
                # http://git.savannah.gnu.org/cgit/gettext.git/tree/gettext-runtime/intl/dcigettext.c?id=159cd1aefcf2#n1106
                match = re.search(b'charset=([^ \t\n]+)', msgstr)
                if match is not None:
                    try:
                        encoding = match.group(1).decode('ASCII')
                    except UnicodeError:
                        pass
                try:
                    b'charset'.decode(encoding)
                except (LookupError, UnicodeError):
                    encoding = 'ASCII'
                self._encoding = encoding
        else:
            if msgids == self._last_msgid:
                raise SyntaxError('duplicate message definition')
            elif msgid < self._last_msgid:
                raise SyntaxError('messages are not sorted')
        self._last_msgid = msgid
        assert encoding is not None
        msgid, *msgctxt = msgid.split(b'\x04', 1)
        kwargs = dict(msgid=msgid.decode(encoding))
        if msgctxt:
            [msgctxt] = msgctxt
            kwargs.update(msgctxt=msgctxt.decode(encoding))
        if len(msgids) == 1:
            assert [msgstr] == msgstrs
            kwargs.update(msgstr=msgstr.decode(encoding))
        else:
            assert len(msgids) == 2
            assert len(msgstrs) >= 1
            kwargs.update(msgid_plural=msgids[1].decode(encoding))
            kwargs.update(msgstr_plural=
                {i: s.decode(encoding) for i, s in enumerate(msgstrs)}
            )
        entry = polib.MOEntry(**kwargs)
        entry.occurrences = ()
        entry.flags = ()  # https://bitbucket.org/izi/polib/issue/47
        entry.translated = lambda: True
        return entry

__all__ = ['Parser', 'SyntaxError']

def main():
    import argparse
    ap = argparse.ArgumentParser(description='msgunfmt(1) replacement')
    ap.add_argument('files', metavar='<file>', nargs='+')
    options = ap.parse_args()
    for path in options.files:
        parser = Parser(path)
        print(parser.parse())

if __name__ == '__main__':
    main()

# vim:ts=4 sw=4 et