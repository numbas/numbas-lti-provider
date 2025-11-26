async function init_app() {
    document.querySelector('#items-fallback').hidden = true;
    const item_trs = [...document.querySelectorAll('#items-fallback tbody tr')];
    const items = item_trs.map(tr => {
      const name = tr.querySelector('a').textContent; 
      const url = tr.querySelector('a').href; 
      const checkbox = tr.querySelector('input[name="resource_pk"]');
      const pk = checkbox.value;
      const selected = checkbox.checked;
      const group = tr.querySelector(`input[name="resource-${pk}-group"]`).value;
      const order = tr.querySelector(`input[name="resource-${pk}-order"]`).valueAsNumber;
      const group_order = tr.querySelector(`input[name="resource-${pk}-group_order"]`).valueAsNumber;
      return {pk, name, url, group, selected, order, group_order};
    });
    const app = Elm.App.init({node: document.getElementById('sorter'), flags: {items}});

    app.ports.send_output.subscribe(groups => {
      for(let tr of item_trs) {
        tr.querySelector('input[name="resource_pk"]').checked = false;
      }
      groups.forEach((group,gi) => {
        group.items.forEach((pk,ii) => {
          const tr = item_trs.find(tr => tr.querySelector(`input[name="resource_pk"]`).value == pk);
          tr.querySelector('input[name="resource_pk"]').checked = true;
          tr.querySelector(`input[name="resource-${pk}-group"]`).value = group.name;
          tr.querySelector(`input[name="resource-${pk}-order"]`).value = ii;
          tr.querySelector(`input[name="resource-${pk}-group_order"]`).value = gi;
        })
      })
    });
}

init_app();
