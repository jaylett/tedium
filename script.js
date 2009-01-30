function tedium_funkify() {
    var check = function(elt, clsName) {
        if (elt.className.indexOf(" ") >= 0) {
            var classes = elt.className.split(" ");
            for(var j = 0;j < classes.length;j++){
                if(classes[j] == clsName) {
		    return true;
		}
            }
        } else if (elt.className == clsName) {
	    return true;
	}
	return false;
    };
    var get_children_text = function(elt) {
	text = '';
	for (var j=0; j < elt.childNodes.length; j++) {
	    var t = elt.childNodes[j].nodeValue;
	    if (t!=null) {
		text = text + t;
	    }
	    text = text + get_children_text(elt.childNodes[j]);
	}
	return text;
    };
    var elements = document.getElementsByTagName('*');
    var current_author = '';
    var current_retweet = null;
    var tweetbox = document.getElementById('status');
    var tweetinreply = document.getElementById('in-reply-to');
    for (var i = 0; i < elements.length; i++){
	if (check(elements[i], 'author-name')) {
	    current_author = get_children_text(elements[i]);
	}
	if (check(elements[i], 'tweet') && current_retweet) {
	    var current_tweet = get_children_text(elements[i]);
	    current_retweet.onclick = function(tweet, author) { return function() { var val =  'RT @' + author + ': ' + tweet; tweetbox.value = val; tweetbox.focus(); if (val.length > tweetbox.maxLength) { alert('RT will be too long!'); } return true; } }(current_tweet, current_author);
	    current_retweet = null;
	}

	if (check(elements[i], 'tweet-tools')) {
	    var reply = document.createElement('img');
	    reply.className = 'reply-button';
	    reply.src = 'icons/arrow_redo.png';
	    reply.width = 16;
	    reply.height = 16;
	    reply.title = 'Reply to this tweet';
	    tweetid = elements[i].id.substring(11);
	    reply.onclick = function(author, tweetid) { return function() { tweetbox.value = '@' + author + ': '; tweetinreply.value = tweetid; tweetbox.focus(); return true; } }(current_author, tweetid);
	    elements[i].appendChild(reply);

	    var retweet = document.createElement('img');
	    retweet.className = 'reply-button';
	    retweet.src = 'icons/arrow_right.png';
	    retweet.width = 16;
	    retweet.height = 16;
	    retweet.title = 'Retweet';
	    current_retweet = retweet;
	    elements[i].appendChild(retweet);
	}
    }
    var element = document.getElementById('key');
    var n = document.createTextNode(' Clicking on ');
    element.appendChild(n);
    n = document.createElement('img');
    n.width = 16;
    n.height = 16;
    n.src = 'icons/arrow_redo.png';
    element.appendChild(n);
    n = document.createTextNode(' starts a reply to that tweet, or ');
    element.appendChild(n);
    n = document.createElement('img');
    n.width = 16;
    n.height = 16;
    n.src = 'icons/arrow_right.png';
    element.appendChild(n);
    n = document.createTextNode(' retweets.');
    element.appendChild(n);

    element = document.getElementById('url-form');
    element.onsubmit = function() {
	submit = document.getElementById('shorten-uri');

	function handler() {
	    if (this.readyState==4 && this.status==200) {
		elt = document.getElementById('short-uri');
		elt.value = this.responseText;
		submit.value = ">> Shorten!";
		append = document.getElementById('append-uri');
		append.style.display = '';
		append.onclick = function() {
		    target = document.getElementById('status');
		    target.value = target.value + ': ' + elt.value;
		    return false;
		};
	    }
	}

        var client = new XMLHttpRequest();
	client.onreadystatechange = handler;
	client.open("POST", 'index.cgi', true);
	client.setRequestHeader("Content-Type", "application/x-www-form-urlencoded");
        elt = document.getElementById('long-uri');
	client.send('long-uri=' + escape(elt.value));
	submit.value = "Shortening";
	elt = document.getElementById('short-uri');
	elt.value = '';
        return false;
    };
    element.style.display = 'block';
};
tedium_funkify();
