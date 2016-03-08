(function() {

    function sendRequest(url, callback, postData) {
        var req = new XMLHttpRequest();
        if (!req)
            return;
        var method = (postData) ? "POST" : "GET";
        req.open(method, url, true);
        if (postData)
            req.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');
        req.onreadystatechange = function() {
            if (req.readyState != 4)
                return;
            if (req.status != 200 && req.status != 304)
                return;
            callback(req);
        }
        if (req.readyState == 4)
            return;
        req.send(postData);
    }

    function $(expr, con) {
        return typeof expr === "string" ? (con || document).querySelector(expr) : expr || null ;
    }
    function $$(expr, con) {
        return Array.prototype.slice.call((con || document).querySelectorAll(expr));
    }
    function $create(tag, o) {
        var element = document.createElement(tag);
        for (var i in o) {
            var val = o[i];
            if (i === "inside") {
                $(val).appendChild(element);
            } else if (i === "around") {
                var ref = $(val);
                ref.parentNode.insertBefore(element, ref);
                element.appendChild(ref);
            } else if (i in element) {
                element[i] = val;
            } else {
                element.setAttribute(i, val);
            }
        }
        return element;
    }

    // check for html5 date input suppport
    var input = document.createElement('input');
    input.setAttribute('type', 'date');
    var notADateValue = 'not-a-date';
    input.setAttribute('value', notADateValue);
    if (input.value === notADateValue) {
        // load fallback date picker
        $create('link', {
            inside: $('head'),
            rel: 'stylesheet',
            href: 'static/pikaday.css',
            type: 'text/css'
        });
        // load pikaday after moment.js
        // moment.js needed to get properly formatted ISO dates in pikaday
        $create('script', {
            inside: 'body',
            src: 'static/moment.js',
            onload: function() {
                $create('script', {
                    inside: 'body',
                    src: 'static/pikaday.js',
                    onload: function() {
                        var q = $$('input[type=date]');
                        for (var i = q.length; i--; )
                            var p = new Pikaday({
                                field: q[i]
                            });
                    }
                });
            }
        });
    }


    // add account input in options bar,
    // and add account/amount row in add transaction form
    //
    // cloneNode on the whole row messes up because of awesomplete (wrapping
    // elements already present, so making another awesomplete doesn't work properly)
    // therefore the way it's done is to add a readonly stack of inputs before, and
    // leave the current autocompletion etc intact.
    var q = $$('.add');
    for (var i = q.length; i--; )
        q[i].addEventListener('click', (function() {
            var tr = this;
            do {
                tr = tr.parentNode;
            } while (tr.parentNode && !tr.classList.contains('row'));
            var div = document.createElement('div');
            div.classList.add('row');
            var ins = tr.getElementsByTagName('input');
            for (var i = 0; i < ins.length; i++) {
                var n = ins[i].cloneNode();
                n.setAttribute('readonly', true);
                // dir=to/from needs to be kept
                if (n.getAttribute('type').toUpperCase() != 'HIDDEN')
                    ins[i].value = '';
                div.appendChild(n);
            }
            var x = tr.querySelector('.add').cloneNode();
            x.textContent = 'x';
            x.classList.remove('add');
            x.classList.add('remove');
            $(x).addEventListener('click', (function(row) {
                return function() {
                    row.remove();
                }
            })(div), false);
            div.appendChild(x);
            tr.parentNode.insertBefore(div, tr);
        }), false);

    // ADD FORM & OPTIONS BAR

    var awesomes = {};
    sendRequest('js', function(req) {
        var tmp = JSON.parse(req.responseText);
        Object.keys(tmp).forEach(function(key) {
            var d = document.getElementById(key);
            for (var i = tmp[key].length; i--; )
                d.appendChild(new Option(tmp[key][i]));
        });
        var q = document.querySelectorAll('input[list]');
        for (var i = q.length; i--; ) {
            var a = new Awesomplete(q[i],{
                autoFirst: 1,
                maxItems: 15,
                sort: function(a, b) {
                    return a < b ? -1 : 1
                }
            });
            // save awesomplete instance for the next part (adaptive sorting)
            if (q[i].id)
                awesomes[q[i].id] = a;
            // needed to disable firefox suggestions,
            // even though awesomplete sets it to false
            q[i].setAttribute('autocomplete', 'off');
            // I want tab key to select current item before moving forward
            $(q[i]).addEventListener('keydown', (function(a) {
                return function(e) {
                    if (a.opened && e.keyCode == 9)
                        a.select()
                }
            })(a), false);
        }
    });

    // ADD FORM

    // click dollar sign to edit commodity
    var q = document.getElementsByClassName('edit_comm');
    for (var i = q.length; i--; ) {
        $(q[i]).addEventListener('click', function() {
            var e = this;
            do {
                e = e.nextElementSibling;
            } while (e && e.getAttribute('name') !== 'commodity');
            if (e) {
                e.setAttribute('type', 'text');
                this.remove();
            }
        }, false);
    }
    // when payee is given, show accounts commonly used with this payee first in suggestions
    var q = $('#i_payee');
    if (q)
        q.addEventListener('blur', function() {
            if (this.value) {
                ['from', 'to'].forEach(function(dir, index, arr) {
                    sendRequest('accounts/' + dir + '/' + encodeURIComponent(this.value), function(req) {
                        var root = JSON.parse(req.responseText);
                        awesomes['i_a_' + dir].sort = function(a, b) {
                            var av = root[a] || 0
                              , bv = root[b] || 0;
                            if (av !== bv)
                                return bv - av;
                            return a < b ? -1 : 1;
                        }
                        awesomes['i_a_' + dir].minChars = 0;
                    })
                }, this);
            }
        }, false);

})()
