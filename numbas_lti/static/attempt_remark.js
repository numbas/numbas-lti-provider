var form = document.getElementById('parts-form');

function update_part(part) {
    var remark = part.querySelector('.remark').checked;
    var score = part.querySelector('.score');
    score.disabled = !remark;
    var row = part;
    while(row && !row.classList.contains('part')) {
        row = row.parentElement;
    }
    row.classList.toggle('remarked',remark);
}

form.addEventListener('change', function(e) {
    if(e.target.tagName=='INPUT' && e.target.classList.contains('remark')) {
        update_part(e.target.parentElement);
    }
});

for(let p of document.querySelectorAll('.part.remarkable')) {
    update_part(p);
}
