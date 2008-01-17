# Tedium library
#
# (c) Copyright James Aylett 2008
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301
# USA

VERSION = '0.2'
DB_VERSION = 2
#DEFAULT_DIGEST_FORMAT = u'(%(time)5.5s) %(nick)12.12s: %(tweet)-48.48s \u00bb\n'
#DEFAULT_DIGEST_FORMAT = '(%(time)5.5s) %(nick)12.12s: %(tweet)s\n'
DEFAULT_DIGEST_FORMAT = '(%(time)5.5s) %(fn)s: \n%(wrapped_tweet)s\n\n'

class TediumError(RuntimeError):
    def __init__(self, message, aux=None):
        RuntimeError.__init__(self, message)
        self.aux = aux