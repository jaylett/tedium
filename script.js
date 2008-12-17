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
    var elements = document.getElementsByTagName('*');
    var current_author = '';
    for (var i = 0; i < elements.length; i++){
	if (check(elements[i], 'author-name')) {
	    current_author = '';
	    for (var j=0; j < elements[i].childNodes.length; j++) {
		var t = elements[i].childNodes[j].nodeValue;
		if (t!=null) {
		    current_author = current_author + t;
		}
	    }
	}
	if (check(elements[i], 'tweet-tools')) {
	    var reply = document.createElement('img');
	    reply.className = 'reply-button';
	    reply.src = 'icons/arrow_right.png';
	    reply.width = 16;
	    reply.height = 16;
	    reply.title = 'Reply to this tweet';
	    var tweetbox = document.getElementById('status');
	    reply.onclick = function(author) { return function() { tweetbox.value = '@' + author + ': '; tweetbox.focus(); return true; } }(current_author);
	    elements[i].appendChild(reply);
	}
    }
    var element = document.getElementById('key');
    var n = document.createTextNode(' Clicking on ');
    element.appendChild(n);
    n = document.createElement('img');
    n.width = 16;
    n.height = 16;
    n.alt = 'arrow';
    n.src = 'icons/arrow_right.png';
    element.appendChild(n);
    n = document.createTextNode(' starts a reply to that tweet.');
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
