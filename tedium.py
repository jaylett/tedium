#!/usr/bin/python
#
# Tedium runner
#
# Copyright (C) 2008 James Aylett
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
#
# FEATURE: spam filtering is used not just displayed in CGI
# FIXME: spam unlearn then learn doesn't seem to work properly
# FEATURE: use jinja for email digest? (split into separate module if so)
# FEATURE: update to jinja > 1.0
# FIXME: assumes UTC coming out of twitter (however this is probably true)
#
# Prereqs on a Mac:
#
# sudo easy_install pysqlite
#
# spambayes
#
# you also need jinja; I suspect that >= 1.0 won't work, as I'm currently
# using 0.9 or so packaged for Debian. This is my problem to fix at some
# point... :-/

import tedium

if __name__ == '__main__':
    tedium.main()
