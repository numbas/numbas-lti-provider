import {createApp} from './vue.js';

const BATCH_SIZE = 50;

const _ = gettext;

function format_datetime(t) {
    return t.toLocaleString(DateTime.DATETIME_MED_WITH_SECONDS);
}

/**
 * A representation of an attempt, containing all its SCORM data and metadata.
 * The SCORM data is loaded asynchronously.
 */
class Attempt {
    constructor(metadata) {
        const a = this;
        this.pk = metadata.pk;
        this.metadata = metadata;
        this.start_time = DateTime.fromISO(metadata.start_time);
        this.completion_status = metadata.completion_status;
        this.user = metadata.user;
        this.status = 'not loaded';
        this.original_raw_score = null;
        this.remarked_raw_score = null;
        this.saved_raw_score = null;
        this.is_changed = false;
        this.remark_error = null;
        this.fetch_error = null;

        /** possible values for status:
         * not loaded
         * loaded
         * remarking
         * remarked
         */

        this.changed_keys = {};
        this.load_scorm_data = new Promise((resolve,reject) => {
            a.load_scorm_data_resolve = resolve;
        });
    }

    get is_loaded() {
        return !(this.status=='not loaded' || this.status=='loading');
    }

    get is_remarked() {
        return this.status=='remarked' || this.status == 'error';
    }

    get review_url() {
        return '/run_attempt/'+this.pk+resource_link_id_query;
    }

    get timeline_url() {
        return '/attempt/'+this.pk+'/timeline'+resource_link_id_query;
    }

    get can_save() {
        return this.status=='remarked' && this.remarked_raw_score!=this.saved_raw_score && this.status != 'saved';
    }

    get completion_status_display() {
        switch(this.completion_status) {
            case 'not attempted':
                return gettext('Not attempted');
            case 'incomplete':
                return gettext('Incomplete');
            case 'completed':
                return gettext('Complete');
        }
    }

    get remark_button_title() {
        return interpolate(_('Re-mark attempt by %s started at %s'), [this.user.full_name, format_datetime(this.start_time)]);
    }

    get save_button_title() {
        return interpolate(_('Save changes to attempt by %s started at %s'), [this.user.full_name, format_datetime(this.start_time)]);
    }

    get review_link_title() {
        return interpolate(_('Review attempt by %s started at %s'), [this.user.full_name, format_datetime(this.start_time)]);
    }

    get data_link_title() {
        return interpolate(_('Data for attempt by %s started at %s'), [this.user.full_name, format_datetime(this.start_time)]);
    }
}

const parameters_json = document.getElementById('parameters-json').textContent;
const parameters = JSON.parse(parameters_json);
const attempts_json = document.getElementById('attempts-json').textContent;
const attempts = JSON.parse(attempts_json).map(data => new Attempt(data));
const exam_source_json = document.getElementById('exam-source-json').textContent;
const exam_source = JSON.parse(exam_source_json);

const exam_window = document.getElementById('exam-iframe').contentWindow;

const ignore_keys = {
//    'cmi.suspend_data': true
};

let resource_link_id;
if(location.search) {
    const bits = location.search.slice(1).split('&');
    bits.forEach(bit => {
        const [k,v] = bit.split('=');
        if(k=='resource_link_id' || k=='lti_13_launch_id') {
            resource_link_id = bit;
        }
    });
}
const resource_link_id_query = resource_link_id ? '?'+resource_link_id : '';

const app = createApp({
    delimiters: ['[[',']]'],
    data() {
        return {
            attempts: attempts,
            apis: {},
            is_remarking_batch: false,
            remarking_batch: [],
            start_remark_batch: new Date(),
            end_remark_batch: 0,
            stopping_marking: false,
            use_unsubmitted: false,
            show_only: 'all',
            name_search: '',
            save_url: parameters['save_url'],
            saving: false,
            save_error: null,
            sort_by: 'name',
            sort_direction: 'ascending',
            page_number: 0,
            num_attempts_per_page: 100,
        }
    },

    mounted() {
        this.attempts.forEach(async attempt => {
            const data = await attempt.load_scorm_data;
            attempt.cmi = data.cmi;
            attempt.status = 'loaded';
            attempt.max_score = parseFloat((attempt.cmi['cmi.score.max'] || {}).value || 0);
            attempt.original_raw_score = parseFloat((attempt.cmi['cmi.score.raw'] || {}).value || 0);
            attempt.saved_raw_score = data.raw_score;
        });

        window.attempts = this.attempts;

        //this.fetch_all_attempt_data();

        window.addEventListener('message',(event) => {
            this.get_remarking_results(event.data);
        });
    },

    methods: {
        stop_marking: function() {
            this.stopping_marking = true;
            this.attempts.forEach(a=>a.await_remark=false);
        },
        fetch_all_attempt_data: async function() {
            let fetch_again = true;
            while(fetch_again) {
                fetch_again = await this.fetch_attempt_data();
            }
        },
        fetch_attempt_data: async function(include_attempt) {
            const unloaded_attempts = this.attempts.filter(a=>a.status=='not loaded');
            const batch = unloaded_attempts.slice(0,BATCH_SIZE);
            if(include_attempt && include_attempt.status=='not loaded' && batch.indexOf(include_attempt)==-1) {
                batch.splice(0,1,include_attempt);
            }
            const pks = batch.map(a=>a.pk);
            if(!pks.length) { 
                return false;
            }

            const url = new URL('remark/attempt_data', window.location);
            url.searchParams.append('attempt_pks', pks.join(','));

            if(resource_link_id) {
                url.searchParams.append(...resource_link_id.split('='));
            }
            try {
                const response = await fetch(url,{method:'GET',credentials:'same-origin'});
                const d = await response.json();
                d.cmis.forEach(cd=>{
                    const a = this.attempts.find(a=>a.pk==cd.pk);
                    a.load_scorm_data_resolve(cd);
                });
                return true;
            } catch(e) {
                batch.forEach(a=>{
                    a.fetch_error = e.message;
                    a.status = 'error';
                });
                console.error("Error getting attempt data:",e);
                return false;
            }
        },
        remark_single_attempt: function(attempt) {
            this.remarking_batch = false;
            this.remark_attempt(attempt);
        },
        remark_attempt: function(attempt) {
            if(!attempt.is_loaded) {
                this.fetch_attempt_data(attempt);
            }
            if(attempt.status=='remarking') {
                return;
            }
            if(this.attempts.some(a=>a.status=='remarking')) {
                this.await_remark = true;
                return;
            }
            attempt.load_scorm_data.then(data => {
                const api = this.apis[attempt.pk] = window.API_1484_11 = new SCORM_API({
                    offline: true,
                    scorm_cmi: attempt.cmi
                });
                api.allow_set = true;
                attempt.status = 'remarking';
                attempt.await_remark = false;
                exam_window.postMessage({action:'start',pk:attempt.pk,use_unsubmitted: this.use_unsubmitted});
            });
        },

        save_single_attempt: function(attempt) {
            this.save_attempts([attempt]);
        },

        save_changed_attempts: function() {
            this.save_attempts(this.shown_attempts.filter(a=>a.can_save));
        },

        save_attempts: function(attempts) {
            var csrftoken = getCSRFToken();
            this.saving = true;

            const data = attempts.map(a=>{
                const changed_data = {}
                Object.entries(a.changed_keys).forEach(([key,value]) => {
                    changed_data[key] = value[1];
                });
                return {
                    pk: a.pk,
                    changed_keys: changed_data
                }
            });

            this.save_error = null;

            var request = fetch(this.save_url, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'X-CSRFToken': csrftoken,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    attempts: data
                })
            })

            request.finally(()=>{
                this.saving = false;
            });

            request.then(r=>r.json()).then(d=>{
                if(!d.success) {
                    this.save_error = d.message;
                }
                attempts.forEach(a => {
                    a.status = d.saved.indexOf(a.pk)!=-1 ? 'saved' : 'error saving';
                    if(a.changed_keys['cmi.score.raw'] !== undefined) {
                        a.saved_raw_score = parseFloat(a.changed_keys['cmi.score.raw'][1]);
                    }
                });
            }).catch(err=>{
                this.save_error = err;
            });
        },

        get_remarking_results: function(data) {
            const pk = data.pk;
            const api = this.apis[pk];
            const attempt = this.attempts.find(a=>a.pk==pk);

            const changed_keys = {};
            attempt.is_changed = false;
            Object.keys(api.data).forEach(x=>{
                if(!ignore_keys[x] && !x.match(/\._count$/) && (attempt.cmi[x]===undefined || api.data[x]!=attempt.cmi[x].value)) {
                    attempt.is_changed = true;
                    changed_keys[x] = [attempt.cmi[x] && attempt.cmi[x].value,api.data[x]];
                }
            })
            attempt.changed_keys = changed_keys;
            attempt.remarked_raw_score = parseFloat(api.data['cmi.score.raw']);
            attempt.status = 'remarked';
            attempt.remark_success = data.success;
            attempt.remark_error = data.error;
            if(!attempt.remark_success) {
                attempt.status = 'error';
            }
         
            this.remark_next();
        },


        remark_next: function() {
            const next_to_remark = this.attempts.find(a => a.await_remark);
            if(!this.stopping_marking && next_to_remark) {
                this.remark_attempt(next_to_remark);
            } else {
                this.end_remark_batch = new Date();
            }
        },

        remark_current_page: function() {
            this.batch_remark(this.current_page);
        },

        remark_all: function() {
            this.batch_remark(this.shown_attempts);
        },

        batch_remark(attempts) {
            this.stopping_marking = false;
            attempts.forEach(a => a.await_remark = true);
            const first = attempts[0];
            if(!first) {
                return;
            }
            this.start_remark_batch = new Date();
            this.end_remark_batch = new Date();
            this.remarking_batch = attempts;
            this.is_remarking_batch = true;
            this.remark_attempt(first);
        },

        prev_page: function() {
            this.page_number = Math.max(this.page_number - 1, 0);
        },
        next_page: function() {
            this.page_number = Math.min(this.page_number + 1, this.num_pages - 1);
        },

        clear_filters: function() {
            this.show_only = 'all';
            this.name_search = '';
        }
    },
    watch: {
        name_search(value) {
            if(value.trim() != '') {
                this.show_only = 'all';
            }
        }
    },
    computed: {
        users: function() {
            const users = new Set();
            this.attempts.forEach(attempt => {
                users.add(`${attempt.user.full_name} ${attempt.user.identifier}`);
            });
            return users;
        },
        num_attempts: function() { return this.attempts.length; },
        remarked_attempts: function() {
            return this.attempts.filter(a=>a.is_remarked);
        },
        remarking_progress: function() { 
            this.end_remark_batch = new Date();
            if(this.remarking_batch.length == 0) {
                return 1;
            }
            return this.remarking_batch.filter(a => a.is_remarked && !a.await_remark).length / this.remarking_batch.length;
        },
        remark_batch_time: function() {
            return this.end_remark_batch-this.start_remark_batch;
        },
        estimated_end: function() {
            const total = this.remark_batch_time/this.remarking_progress;
            return total - this.remark_batch_time;
        },
        sorted_attempts: function() {
            const direction = {'ascending': 1, 'descending': -1}[this.sort_direction] || 1;

            const [sort_key,sort_dir] = {
                'name': [a => a.user.full_name, 1],
                'identifier': [a => a.user.identifier, 1],
                'start_time': [a => a.start_time, -1],
                'original_score': [a => a.original_raw_score, 1],
                'saved_score': [a => a.saved_raw_score, 1],
                'completion_status': [a => ['completed','incomplete','not attempted'].indexOf(a.completion_status), 1]
            }[this.sort_by];
            function compare_attempts(a,b) {
                [a,b] = [sort_key(a), sort_key(b)];
                return (a>b ? 1 : a<b ? -1 : 0)*sort_dir*direction;
            }
            return this.attempts.sort(compare_attempts);
        },

        /** Attempts which should be shown, after applying the selected filters.
         */
        shown_attempts: function() {
            let list = this.sorted_attempts.filter(a=>{
                switch(this.show_only) {
                    case 'all':
                        return true;
                    case 'completed':
                        return a.completion_status == 'completed';
                    case 'changed':
                        return a.remarked_raw_score !== null && a.saved_raw_score != a.remarked_raw_score;
                    case 'increased':
                        return a.remarked_raw_score !== null && a.original_raw_score < a.remarked_raw_score;
                    case 'decreased':
                        return a.remarked_raw_score !== null && a.original_raw_score > a.remarked_raw_score;
                }
            });

            const search = this.name_search.trim().toLowerCase();
            if(search != '') {
                list = list.filter(attempt => `${attempt.user.full_name} ${attempt.user.identifier}`.includes(search));
            }
            return list;
        },

        /** The number of pages of attempts to be shown.
         */
        num_pages: function() {
            return Math.ceil(this.shown_attempts.length / this.num_attempts_per_page);
        },

        /** Attempts on the current page.
         */
        current_page: function() {
            const page = Math.min(this.page_number, Math.floor(this.shown_attempts.length / this.num_attempts_per_page));
            return this.shown_attempts.slice(page * this.num_attempts_per_page, (page + 1) * this.num_attempts_per_page);
        },
        /* The index of the first attempt on the page.
         */
        first_on_page: function() {
            return Math.min(this.page_number * this.num_attempts_per_page, this.shown_attempts.length-1);
        },
        /* The index of the last attempt on the page.
         */
        last_on_page: function() {
            return Math.min((this.page_number+1) * this.num_attempts_per_page-1, this.shown_attempts.length-1);
        },
        num_attempts_hidden: function() {
            return this.attempts.length - this.shown_attempts.length;
        },
        changed_attempts: function() {
            return this.shown_attempts.filter(a=>a.can_save);
        },
    }
});

function todp(n,p) {
    const s = n.toFixed(p);
    return s.replace(/\.?0+$/,'')
}

app.config.globalProperties.$filters = {
    duration: function(value) {
        const d = luxon.Duration.fromMillis(value);
        return d.toFormat('mm:ss');
    },

    percent: function(value) {
        const pc = Math.floor(100*value);
        return pc;
    },

    pluralize: function(str, number) {
        return str + (Math.abs(number)==1 ? '' : 's');
    },

    dp: function(n,p) {
        if(isNaN(n) || typeof(n)!='number') {
            return n;
        }
        return todp(n,p);
    },

    datetime: format_datetime,
};

app.component('ScoreChange', {
    data() {
        return {}
    },
    props: ['from', 'to'],
    computed: {
        classes: function() {
            const a = this.to;
            const b = this.from;
            if(a === null) {
                return {};
            }
            return {
                'score-change': true,
                'decreased': a<b,
                'unchanged': a==b,
                'increased': a>b
            };
        },
        change: function() {
            const diff = this.to - this.from;
            const sn = todp(diff, 3)
            if(diff >= 0) {
                return '+'+sn;
            } else {
                return sn;
            }
        }
    },
    template: `
<div :class="classes">
    {{change}}
</div>`
});

window.app = app.mount('#app');
