function die(e) {
    console.error(e);
    alert(interpolate(gettext("There's been an error: %s"),[e.message]));
}

const exam_data_json = document.getElementById('exam-data-json').textContent;
const exam_data = JSON.parse(exam_data_json);

const numbas_ready = new Promise((resolve,reject) => {
    try {
        Numbas.getStandaloneFileURL = function(extension, path) {
		return exam_data['extracted_url']+'/extensions/'+extension+'/standalone_scripts/'+path;
        }
        Numbas.queueScript('web-remarking',['start-exam'],function() {
            try {
                for(var x in Numbas.extensions) {
                    Numbas.activateExtension(x);
                }
                Numbas.display = null;
                resolve(Numbas);
            } catch(e) {
                die(e);
            }
        });
    } catch(e) {
        die(e);
    }
});

function load_exam() {
    return numbas_ready.then(Numbas => {
        if(Numbas.schedule.unhalt) {
            Numbas.schedule.unhalt();
            for(var x in Numbas.signals.callbacks) {
                delete Numbas.signals.callbacks[x];
            }
        } else {
            Numbas.schedule.halted = false;
            Numbas.signals.error = null;
        }
        window.pipwerks.SCORM.API.handle = null;
        window.pipwerks.SCORM.API.isFound = null;
        window.pipwerks.SCORM.connection.isActive = false;


        var seed = Math.seedrandom(new Date().getTime());
        var job = Numbas.schedule.add;
        Numbas.xml.loadXMLDocs();
        var store = Numbas.store = new Numbas.storage.scorm.SCORMStorage();
        var xml = Numbas.xml.examXML.selectSingleNode('/exam');
        var exam = Numbas.exam = Numbas.createExamFromXML(xml,store,true);

        const p = new Promise(function(resolve,reject) {
            Numbas.signals.on('Numbas initialised').catch(error => {
                reject(error);
            });
            exam.signals.on('ready',function() {
                resolve(exam);
            }).catch(error => {
                reject(error);
            });
        });

        exam.seed = Numbas.util.hashCode(seed);
        var entry = store.getEntry();
        if(store.getMode() == 'review') {
            entry = 'review';
        }
        exam.entry = entry;

        switch(entry) {
            case 'ab-initio':
                job(exam.init,exam);
                exam.signals.on('ready', function() {
                    Numbas.signals.trigger('exam ready');
                })
                break;
            case 'resume':
            case 'review':
                job(exam.load,exam);
                exam.signals.on('ready', function() {
                    Numbas.signals.trigger('exam ready');
                    job(function() {
                        if(entry == 'review') {
                            job(exam.end,exam,false);
                        }
                    });
                });
                break;
        }
        job(function() {
            Numbas.signals.trigger('Numbas initialised');
        });

        return p;
    });
}

function reset(exam) {
    exam.store.exam = null;
    if(exam.store.receive_window_message) {
        window.removeEventListener('message',exam.store.receive_window_message);
    }
    if(Numbas.schedule.reset) {
        Numbas.schedule.reset();
    } else {
        Numbas.schedule.calls = [];
        Numbas.schedule.lifts = [];
        Numbas.schedule.signalboxes = [];
        Numbas.signals = new Numbas.schedule.SignalBox();
    }
}

function remark_session(options) {
    options = options || {};
    const promise = new Promise((resolve,reject) => {
        load_exam().then(exam => {
            const pre_submit_promises = [];
            exam.questionList.forEach(function(q) {
                q.store.saveQuestion(q);
                q.allParts().forEach(function(p) {
                    p.store.partAnswered(p);
                    p.revealed = false;
                    if(options.use_unsubmitted) {
                        p.stagedAnswer = p.resume_stagedAnswer || p.stagedAnswer;
                    }
                    p.pre_submit_cache = [];
                });
                if(options.use_unsubmitted) {
                    q.parts.forEach(function(p) {
                        p.revealed = false;
                        p.submit();
                        if(p.waiting_for_pre_submit) {
                            pre_submit_promises.push(p.waiting_for_pre_submit);
                        }
                    });
                }
            });

            Promise.all(pre_submit_promises).then(results => {
                exam.store.saveExam(exam);

                reset(exam);

                resolve({success: true});
            });
        }).catch(err=>{
            resolve({success: false, error: err});
        })
    });
    return promise;
}

window.addEventListener('message', (event) => {
    const {pk, action} = event.data
    switch(action) {
        case 'start':
            numbas_ready.then(N=>{
                remark_session({use_unsubmitted: event.data.use_unsubmitted}).then(result=>{
                    window.parent.postMessage({success: result.success, pk: pk, error: result.error ? result.error.message : undefined});
                });
            });

            break;
    }
});

