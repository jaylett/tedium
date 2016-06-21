# Tedium

Tedium is a Twitter Digest Manager: it will watch your friends'
tweets, and produce an emailed digest every so often. There's also a
slightly nifty web interface, which gives control over things like
which authors to pay attention to their replies (either to or from
them) even in digest mode; it also gives training control over a spam
filter.

It probably doesn't work any more, either from Python package bitrot
or from the Twitter API changing; the latter is almost guaranteed
since this was worked on. It was never really intended to be used by
anyone other than me, and I haven't used it in years. It may contain a
very old Twitter API key, but that's long-since disabled.

If you can get it running, invoke once to configure (it'll prompt
you), then run with an email address to get a digest; there are some
other options available in the usual fashion. It expects to be run as
a CGI script behind HTTP authentication (in the way Apache does it),
which gives some measure of protection against accidentally letting
everyone see protected tweets and any security holes.

You need `pysqlite2`, `jinja2` and `spambayes` installed, although I
have no idea which versions will actually work any more. Sorry.
