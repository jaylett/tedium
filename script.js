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
		current_author = current_author + elements[i].childNodes[j].nodeValue;
	    }
	}
	if (check(elements[i], 'tweet')) {
	    var reply = document.createElement('img');
	    reply.className = 'reply-button';
	    reply.src = 'icons/arrow_right.png';
	    reply.width = 16;
	    reply.height = 16;
	    reply.title = 'Reply to this tweet';
	    var tweetbox = document.getElementById('status');
	    reply.onclick = function(author) { return function() { tweetbox.value = '@' + author + ': '; tweetbox.focus(); return true; } }(current_author);
	    elements[i].insertBefore(reply, elements[i].firstChild);
	}
    }
};
tedium_funkify();
