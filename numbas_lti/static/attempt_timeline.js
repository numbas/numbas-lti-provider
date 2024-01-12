import {createApp} from './vue.js';

function load_json(id) {
    var json = document.getElementById(id).textContent;
    return JSON.parse(json);
}

var elements = load_json('scorm-elements');
var remarked_elements = load_json('remarked-elements');
var launches = load_json('launches');
var metadata = load_json('metadata');

var DateTime = luxon.DateTime;

var _ = gettext;

function percentage(n) {
    return Math.floor(100*n)+'%';
}

function pluralise(n,single,plural) {
    n = parseFloat(n);
    return n==1 ? single : plural;
}

function parse_part_path(path) {
    var m = path.match(/^q(\d+)(?:p(\d+)(?:g(\d+)|s(\d+))?)?$/);
    if(!m) {
        throw(new Error(interpolate("Can't parse part path %s"),[path]));
    }
    return {
        question: parseInt(m[1]),
        part: parseInt(m[2]),
        gap: parseInt(m[3]),
        step: parseInt(m[4])
    };
}

function score_icon(score,marks) {
    return marks==0 ? '' : score<marks ? 'not-ok' : 'ok'
}

const app = createApp({
    delimiters: ['[[', ']]'],
    data() {
        return {
            question: 0,
            completion_status: '',
            raw_elements: elements.slice(),
            remarked_elements: remarked_elements.slice(),
            launches: launches.slice(),
            all_elements: [],
            timeline: []
        }
    },

    mounted() {
        document.body.classList.add('loaded');
        elements.forEach(e => this.add_element(e));
        launches.forEach(l => this.add_launch(l));
    },

    computed: {
        /** Timeline items, with elements within a second of each other grouped together.
         *  Elements created by remarking are always put in a separate group to other elements.
         */
        grouped_timeline() {
            let seen_location = false;

            const timeline = this.timeline.sort(function(a,b) {
                a = a.time;
                b = b.time;
                return a<b ? -1 : a>b ? 1 : 0;
            });

            const groups = [];
            let current_group = null;

            timeline.forEach(function(item) {
                var remarked_by = item.element.remarked ? item.element.remarked.user : null;
                seen_location = seen_location || item.element.key=='cmi.location';
                if(current_group==null || item.time.diff(current_group.time).as('seconds')>1 || current_group.remarked_by != remarked_by) {
                    current_group = {
                        time: item.time,
                        remarked_by: remarked_by,
                        items: [],
                        seen_location: seen_location
                    }
                    groups.push(current_group);
                }
                current_group.items.push(item);
            });

            var item_order = [
                'launch',
                'scorm part answer',
                'scorm part score',
                'scorm question score raw',
                'scorm exam score raw',
                'scorm completion_status',
                'scorm location',
                'scorm suspend_data'
            ];

            function score_for_item(item) {
                return item_order.indexOf(item.kind);
            }

            let previous_exam_score = NaN;

            groups.forEach(g => {
                if(g.items.length) {
                    var element_items = g.items.filter(function(i){ return i.css.scorm });
                    var element = element_items.length ? element_items[element_items.length-1].element : {time: g.items[g.items.length-1].time, counter: Infinity};
                    g.exam_raw_score = parseFloat(this.element_at('cmi.score.raw',element) || 0);
                    g.exam_max_score = parseFloat(this.element_at('cmi.score.max',element) || 0);
                    var exam_scaled_score = parseFloat(this.element_at('cmi.score.scaled',element) || 0);
                    g.exam_scaled_score = percentage(exam_scaled_score);

                    if(g.exam_raw_score != previous_exam_score) {
                        g.exam_score_changed = true;
                        previous_exam_score = g.exam_raw_score;
                    }
                }
                g.items.sort(function(a,b) {
                    a = score_for_item(a);
                    b = score_for_item(b);
                    return a<b ? -1 : a>b ? 1 : 0;
                });
            });

            return groups;
        }
    },

    methods: {
        element_at: function(key,element) {
            var t,counter;
            if(!element) {
                t = Infinity;
                counter = Infinity;
            } else {
                t = (new Date(element.time))-0;
                counter = element.counter;
            }
            var value;
            this.all_elements.forEach(function(e) {
                var et = (new Date(e.time))-0;
                if(e.key==key && (et<t || et==t && e.counter<counter)) {
                    value = e.value;
                }
            });
            return value;
        },
        datamodel_at: function(element) {
            var t,counter;
            if(!element) {
                t = Infinity;
                counter = Infinity;
            } else {
                t = (new Date(element.time))-0;
                counter = element.counter;
            }
            var datamodel = {};
            this.all_elements.forEach(function(e) {
                var et = (new Date(e.time))-0;
                if(et<t || et==t && e.counter<counter) {
                    datamodel[e.key] = e.value;
                }
            });
            return datamodel;
        },

        suspend_data_at: function(element) {
            var json_suspend_data = this.element_at('cmi.suspend_data',element);
            if(json_suspend_data) {
                return JSON.parse(json_suspend_data);
            } else {
                return {}
            }
        },

        getPart: function(id,element) {
            var id_key = 'cmi.interactions.'+id+'.id';
            var path = this.element_at(id_key,element);
            if(!path) {
                return {
                    id: id,
                    name: 'Part with id '+id,
                    path: '',
                    marks: 0
                };
            }
            var desc = parse_part_path(path);
            var suspend_data = this.suspend_data_at(element);
            var part;
            try {
                var p = suspend_data.questions[desc.question].parts[desc.part];
                if(!isNaN(desc.gap)) {
                    p = p.gaps[desc.gap];
                } else if(!isNaN(desc.step)) {
                    p = p.steps[desc.step];
                }
                var part_type = this.element_at('cmi.interactions.'+id+'.description',element);
                var marks = parseFloat(this.element_at('cmi.interactions.'+id+'.weighting',element));
                part = {
                    id: id,
                    name: p.name || path,
                    path: path,
                    type: part_type,
                    marks: marks
                }
            } catch(e) {
                part = {
                    id: id,
                    name: path,
                    path: path,
                    marks: 0
                }
            }
            part.name = 'Question '+(desc.question+1)+', '+part.name;
            return part;
        },

        has_started: function(element) {
            var s = this.suspend_data_at(element);
            return s.start!==undefined;
        },

        add_element: function(element) {
            var key = element.key
            this.all_elements.push(element);
            element.remarked = this.remarked_elements.find(function(r) { return r.element == element.pk; });

            var m;

            if(key=='cmi.completion_status') {
                this.completion_status = element.value;
                var messages = {
                    'incomplete': _('Started the attempt.'),
                    'completed': _('Ended the attempt.'),
                };
                var message = messages[element.value];
                var icons = {
                    'incomplete': 'play',
                    'completed': 'save'
                }
                var icon = icons[element.value];
                if(message) {
                    this.add_timeline_item(new TimelineItem(
                        message,
                        element,
                        'scorm completion_status',
                        icon
                    ));
                }
                return;
            }

            if(!this.has_started(element)) {
                return;
            }

            if(key=='cmi.location') {
                var number = parseInt(element.value);
                this.add_timeline_item(new TimelineItem(
                    interpolate(_('Moved to <em class="question">Question %s</em>.'),[number+1]),
                    element,
                    'scorm location',
                    'list'
                ));
                this.question = number;
            } else if(m = key.match(/^cmi.interactions.(\d+).learner_response$/)) {
                var id = parseInt(m[1]);
                var p = this.getPart(id,element);
                if(p.type!=='gapfill' && element.value!='undefined') {
                    this.add_timeline_item(new TimelineItem(
                        interpolate(_('<em class="part">%s</em>: Submitted answer <code>%s</code>.'),[p.name, element.value]),
                        element,
                        'scorm part answer',
                        'pencil'
                    ));
                }
            } else if(m = key.match(/^cmi.interactions.(\d+).staged_answer$/)) {
                var id = parseInt(m[1]);
                var p = this.getPart(id,element);
                var later = this.raw_elements.find(function(e2) {
                    return e2.time>element.time && (e2.key=='cmi.interactions.'+id+'.staged_answer' || e2.key=='cmi.interactions.'+id+'.learner_response');
                });
                if(!later && p.type!=='gapfill' && element.value!='undefined') {
                    this.add_timeline_item(new TimelineItem(
                        interpolate(_('<em class="part">%s</em>: Entered but did not submit answer <code>%s</code>.'),[p.name, element.value]),
                        element,
                        'scorm part answer',
                        'pencil'
                    ));
                }
            } else if(m = key.match(/^cmi.interactions.(\d+).result$/)) {
                var id = parseInt(m[1]);
                var p = this.getPart(id,element);
                var score = parseFloat(element.value);
                this.add_timeline_item(new TimelineItem(
                    interpolate(ngettext('<em class="part">%s</em>: Received <strong>%s/%s</strong> mark.','<em class="part">%s</em>: Received <strong>%s/%s</strong> marks.',score),[p.name, score,p.marks]),
                    element,
                    'scorm part score',
                    score_icon(score,p.marks)
                ));
            } else if(m = key.match(/^cmi.objectives.(\d+).score.raw$/)) {
                var id = parseInt(m[1]);
                this.add_timeline_item(new TimelineItem(
                    interpolate(_('<em class="question">Question %s</em>: Total score is <strong>%s</strong>.'),[id+1,element.value]),
                    element,
                    'scorm question score raw',
                    ''
                ));
            } else if(key=='cmi.score.raw') {
                this.add_timeline_item(new TimelineItem(
                    interpolate(_('Total score for exam is <strong>%s</strong>.'),[element.value]),
                    element,
                    'scorm exam score raw',
                    ''
                ));
            } else if(key=='x.reason ended') {
                this.add_timeline_item(new TimelineItem(
                    interpolate(_('The session was ended automatically because: <strong>%s</strong>.'),[element.value]),
                    element,
                    'scorm reason-ended',
                    'save'
                ));
            }
        },
        add_launch: function(launch) {
            var msg;
            if(launch.user!=null) {
                msg = interpolate(_('Launched in %s mode by %s.'),[launch.mode,launch.user]);
            } else {
                msg = interpolate(_('Launched in %s mode.'),launch.mode);
            }
            this.add_timeline_item(new TimelineItem(
                msg,
                launch,
                'launch',
                'eye-open'
            ))
        },
        add_timeline_item: function(item) {
            this.timeline.push(item);
        },

        listen_for_changes: function(url) {
            var dm = this;
            var ws_scheme = window.location.protocol == "https:" ? "wss" : "ws";
            var socket = this.socket = new RobustWebSocket(ws_scheme + '://' + window.location.host + url);

            socket.onmessage = function(e) {
                var data = JSON.parse(e.data);
                switch(data.type) {
                    case 'scorm.new.element':
                        dm.add_element(data.element);
                        break;
                }
            }
        },

        scrollIntoView: function(element) {
            if(element.nodeType!=element.ELEMENT_NODE) {
                element = element.parentElement;
            }
            if(element.classList.contains('item')) {
                element.scrollIntoView();
            }
        }
    }
});

app.component('VueIcon', VueIcon);

app.mount('#app');

function TimelineItem(message,element,kind,icon) {
    var ti = this;
    this.message = message;
    this.element = element;
    this.time = DateTime.fromISO(element.time);
    this.time_iso = this.time.toISO();
    this.time_string = this.time.toLocaleString(DateTime.DATETIME_MED_WITH_SECONDS);
    this.review_url = metadata.review_url + (metadata.review_url.match(/\?/) ? '&' : '?')+'at_time='+encodeURIComponent(this.time.toISO());
    this.kind = kind;
    this.css = {};
    kind.split(' ').forEach(function(cls) {
        ti.css[cls] = true;
    });
    this.css['remarked'] = element.remarked !== undefined;
    this.icon = icon;
}
