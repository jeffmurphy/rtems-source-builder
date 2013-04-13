#
# RTEMS Tools Project (http://www.rtems.org/)
# Copyright 2010-2013 Chris Johns (chrisj@rtems.org)
# All rights reserved.
#
# This file is part of the RTEMS Tools package in 'rtems-tools'.
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

#
# Macro tables.
#

import re
import os
import string

import error
import path

#
# Macro tables
#
class macros:

    class macro_iterator:
        def __init__(self, keys):
            self.keys = keys
            self.index = 0

        def __iter__(self):
            return self

        def next(self):
            if self.index < len(self.keys):
                key = self.keys[self.index]
                self.index += 1
                return key
            raise StopIteration

        def iterkeys(self):
            return self.keys

    def __init__(self, name = None, original = None, sbdir = '.'):
        self.files = []
        self.macro_filter = re.compile(r'%{[^}]+}')
        if original is None:
            self.macros = {}
            self.read_map = 'global'
            self.write_map = 'global'
            self.macros[self.read_map] = {}
            self.macros[self.read_map]['_cwd'] = ('dir', 'required', path.shell(os.getcwd()))
            self.macros[self.read_map]['_sbdir'] = ('dir', 'required', path.shell(sbdir))
        else:
            self.macros = {}
            for m in original.macros:
                if m not in self.macros:
                    self.macros[m] = {}
                for k in original.macros[m]:
                    self.macros[m][k] = original.macros[m][k]
            self.read_map = original.read_map
            self.write_map = original.write_map
        if name is not None:
            self.load(name)

    def __copy__(self):
        return macros(original = self)

    def __str__(self):
        text_len = 80
        text = ''
        for f in self.files:
            text += '> %s%s' % (f, os.linesep)
        for map in self.macros:
            text += '[%s]%s' % (map, os.linesep)
            for k in sorted(self.macros[map].keys()):
                d = self.macros[map][k]
                text += " %s:%s '%s'%s '%s'%s" % \
                    (k, ' ' * (20 - len(k)),
                     d[0], ' ' * (8 - len(d[0])),
                     d[1], ' ' * (10 - len(d[1])))
                if len(d[2]) == 0:
                    text += "''%s" % (os.linesep)
                else:
                    if '\n' in d[2]:
                        text += "'''"
                    else:
                        text += "'"
                indent = False
                ds = d[2].split('\n')
                lc = 0
                for l in ds:
                    lc += 1
                    while len(l):
                        if indent:
                            text += ' %21s %10s %12s' % (' ', ' ', ' ')
                        text += l[0:text_len]
                        l = l[text_len:]
                        if len(l):
                            text += ' \\'
                        elif lc == len(ds):
                            if len(ds) > 1:
                                text += "'''"
                            else:
                                text += "'"
                        text += '%s' % (os.linesep)
                        indent = True
        return text

    def __iter__(self):
        return macros.macro_iterator(self.keys())

    def __getitem__(self, key):
        macro = self.get(key)
        if macro is None or macro[1] == 'undefine':
            raise IndexError('key: %s' % (key))
        return macro[2]

    def __setitem__(self, key, value):
        if type(key) is not str:
            raise TypeError('bad key type (want str): %s' % (type(key)))
        if type(value) is str:
            value = ('none', 'none', value)
        if type(value) is not tuple:
            raise TypeError('bad value type (want tuple): %s' % (type(value)))
        if len(value) != 3:
            raise TypeError('bad value tuple (len not 3): %d' % (len(value)))
        if type(value[0]) is not str:
            raise TypeError('bad value tuple type field: %s' % (type(value[0])))
        if type(value[1]) is not str:
            raise TypeError('bad value tuple attrib field: %s' % (type(value[1])))
        if type(value[2]) is not str:
            raise TypeError('bad value tuple value field: %s' % (type(value[2])))
        if value[0] not in ['none', 'triplet', 'dir', 'file', 'exe']:
            raise TypeError('bad value tuple (type field): %s' % (value[0]))
        if value[1] not in ['none', 'optional', 'required', 'override', 'undefine']:
            raise TypeError('bad value tuple (attrib field): %s' % (value[1]))
        self.macros[self.write_map][self.key_filter(key)] = value

    def __delitem__(self, key):
        self.undefine(key)

    def __contains__(self, key):
        return self.has_key(key)

    def __len__(self):
        return len(self.keys())

    def keys(self):

        def _map_keys(_map):
            u = []
            k = []
            for mk in _map:
                if _map[mk][1] == 'undefine':
                    u += [mk]
                else:
                    k += [mk]
            return k, u

        keys, undefined = _map_keys(self.macros[self.read_map])
        if map is not 'global':
            gk, u = _map_keys(self.macros['global'])
            undefined = set(undefined + u)
            for k in gk:
                if k not in undefined:
                    keys += [k]
        return sorted(set(keys))

    def has_key(self, key):
        if type(key) is not str:
            raise TypeError('bad key type (want str): %s' % (type(key)))
        if self.key_filter(key) not in self.keys():
            return False
        return True

    def maps(self):
        return self.macros.keys()

    def key_filter(self, key):
        if key.startswith('%{') and key[-1] is '}':
            key = key[2:-1]
        return key.lower()

    def parse(self, lines):
        macros = { 'global': {} }
        map = 'global'
        lc = 0
        state = 'key'
        token = ''
        macro = []
        for l in lines:
            lc += 1
            #print 'l:%s' % (l[:-1])
            if len(l) == 0:
                continue
            for c in l:
                #print ']]]]]]]] c:%s(%d) s:%s t:"%s" m:%r M:%s' % (c, ord(c), state, token, macro, map)
                if c is '#' and not state.startswith('value'):
                    break
                if c == '\n' or c == '\r':
                    if not (state is 'key' and len(token) == 0) and \
                            not state.startswith('value-multiline'):
                        raise error.general('malformed macro line:%d: %s' % (lc, l))
                if state is 'key':
                    if c not in string.whitespace:
                        if c is '[':
                            state = 'map'
                        elif c is ':':
                            macro += [token]
                            token = ''
                            state = 'attribs'
                        elif c is '#':
                            break
                        else:
                            token += c
                elif state is 'map':
                    if c is ']':
                        if token not in macros:
                            macros[token] = {}
                        map = token
                        token = ''
                        state = 'key'
                    elif c in string.printable and c not in string.whitespace:
                        token += c
                    else:
                        raise error.general('invalid macro map:%d: %s' % (lc, l))
                elif state is 'attribs':
                    if c not in string.whitespace:
                        if c is ',':
                            macro += [token]
                            token = ''
                            if len(macro) == 3:
                                state = 'value-start'
                        else:
                            token += c
                elif state is 'value-start':
                    if c is "'":
                        state = 'value-line-start'
                elif state is 'value-line-start':
                    if c is "'":
                        state = 'value-multiline-start'
                    else:
                        state = 'value-line'
                        token += c
                elif state is 'value-multiline-start':
                    if c is "'":
                        state = 'value-multiline'
                    else:
                        macro += [token]
                        state = 'macro'
                elif state is 'value-line':
                    if c is "'":
                        macro += [token]
                        state = 'macro'
                    else:
                        token += c
                elif state is 'value-multiline':
                    if c is "'":
                        state = 'value-multiline-end'
                    else:
                        token += c
                elif state is 'value-multiline-end':
                    if c is "'":
                        state = 'value-multiline-end-end'
                    else:
                        state = 'value-multiline'
                        token += "'" + c
                elif state is 'value-multiline-end-end':
                    if c is "'":
                        macro += [token]
                        state = 'macro'
                    else:
                        state = 'value-multiline'
                        token += "''" + c
                else:
                    raise error.internal('bad state: %s' % (state))
                if state is 'macro':
                    macros[map][macro[0].lower()] = (macro[1], macro[2], macro[3])
                    macro = []
                    token = ''
                    state = 'key'
        for m in macros:
            if m not in self.macros:
                self.macros[m] = {}
            for mm in macros[m]:
                self.macros[m][mm] = macros[m][mm]

    def load(self, name):
        try:
            name = self.expand(name)
            mc = open(name, 'r')
        except IOError, err:
            raise error.general('opening macro file: %s' % (path.host(name)))
        macros = self.parse(mc)
        mc.close()
        self.files += [name]

    def get(self, key):
        if type(key) is not str:
            raise TypeError('bad key type: %s' % (type(key)))
        key = self.key_filter(key)
        if self.read_map is not 'global'and key in self.macros[self.read_map]:
            return self.macros[self.read_map][key]
        if key in self.macros['global']:
            return self.macros['global'][key]
        return None

    def get_type(self, key):
        m = self.get(key)
        if m is None:
            return None
        return m[0]

    def get_attribute(self, key):
        m = self.get(key)
        if m is None:
            return None
        return m[1]

    def overridden(self, key):
        return self.get_attribute(key) == 'override'

    def define(self, key, value = '1'):
        if type(key) is not str:
            raise TypeError('bad key type: %s' % (type(key)))
        self.__setitem__(key, ('none', 'none', value))

    def undefine(self, key):
        if type(key) is not str:
            raise TypeError('bad key type: %s' % (type(key)))
        key = self.key_filter(key)
        for map in self.macros:
            if key in self.macros[map]:
                del self.macros[map][key]

    def expand(self, _str):
        """Simple basic expander of config file macros."""
        expanded = True
        while expanded:
            expanded = False
            for m in self.macro_filter.findall(_str):
                name = m[2:-1]
                macro = self.get(name)
                if macro is None:
                    raise error.general('cannot expand default macro: %s in "%s"' %
                                        (m, _str))
                _str = _str.replace(m, macro[2])
                expanded = True
        return _str

    def find(self, regex):
        what = re.compile(regex)
        keys = []
        for key in self.keys():
            if what.match(key):
                keys += [key]
        return keys

    def set_read_map(self, map):
        if map in self.macros:
            self.read_map = map
            return True
        return False

    def set_write_map(self, map):
        if map in self.macros:
            self.write_map = map
            return True
        return False

if __name__ == "__main__":
    import copy
    import sys
    m = macros(name = 'defaults.mc')
    d = copy.copy(m)
    m['test1'] = 'something'
    if d.has_key('test1'):
        print 'error: copy failed.'
        sys.exit(1)
    m.parse("[test]\n" \
            "test1: none, undefine, ''\n" \
            "name:  none, override, 'pink'\n")
    m.set_read_map('test')
    if m['name'] != 'pink':
        print 'error: override failed. name is %s' % (m['name'])
        sys.exit(1)
    if m.has_key('test1'):
        print 'error: map undefine failed.'
        sys.exit(1)
    print m
    print m.keys()
