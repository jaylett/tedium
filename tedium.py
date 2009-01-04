#!/usr/bin/python
#
# Tedium runner
#
# Copyright (C) 2009 James Aylett
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
# FIXME: spam unlearn then learn doesn't seem to work properly
# FEATURE: if can't post tweet (or do some other operation), pend it
# FEATURE: email digest and escapable entities, waaah (works, but... eww)
# FEATURE: use jinja for email digest? (split into separate module if so)
# FEATURE: click on any username to configure to/from/ban/following options
# FEATURE: HEAD tinyurls etc. to put a title attribute on with final URL
#          or, indeed, expand them fully
# FIXME: assumes UTC coming out of twitter (however this is probably true)
#
# Prereqs (most should work fine via easy_install):
#
# pysqlite
# jinja 2.1.1 or later
# spambayes

import tedium

if __name__ == '__main__':
    tedium.main()
