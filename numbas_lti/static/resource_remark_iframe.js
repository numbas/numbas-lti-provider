function die(e) {
    console.error(e);
    alert("There's been an error: "+e.message);
}

const numbas_ready = new Promise((resolve,reject) => {
    try {
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

function remark_session(options) {
    options = options || {};
    const promise = new Promise((resolve,reject) => {
        load_exam().then(exam => {
            exam.questionList.forEach(function(q) {
                q.store.saveQuestion(q);
                q.allParts().forEach(function(p) {
                    p.store.partAnswered(p);
                    p.revealed = false;
                    if(options.use_unsubmitted) {
                        p.stagedAnswer = p.resume_stagedAnswer || p.stagedAnswer;
                    }
                });
                if(options.use_unsubmitted) {
                    q.parts.forEach(function(p) {
                        p.revealed = false;
                        p.submit();
                    });
                }
            });
            exam.store.saveExam(exam);

            resolve({success: true});
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
                    window.parent.postMessage({success: result.success, pk: pk, error: result.error.message});
                });
            });

            break;
    }
});

