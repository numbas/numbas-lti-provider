class RawHTMLElement extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode: 'open'});
  }
  connectedCallback() {
    this.setContent();
  }

  static observedAttributes = ['content'];

  setContent() {
    this.shadowRoot.innerHTML = this.getAttribute('content');
    for(let style of document.querySelectorAll('link[rel="stylesheet"]')) {
        const s = style.cloneNode(true);
        this.shadowRoot.append(s);
    }
    MathJax.typesetPromise(this.shadowRoot.children); 
  }

  attributeChangedCallback() {
    this.setContent();
  }
}
customElements.define('raw-html', RawHTMLElement);

class DownloadFileElement extends HTMLElement {
  constructor() {
    super();
  }
  connectedCallback() {
    this.setContent();
  }

  static observedAttributes = ['filename','content'];

  setContent() {
    const label = this.textContent;
    if(!this.shadowRoot) {
      this.attachShadow({mode: 'open'});
      const a = document.createElement('a');
      this.link = a;
      this.shadowRoot.append(a);

    }
    const filename = this.getAttribute('filename');
    const content = this.getAttribute('content');
    const blob = new Blob([content]);
    this.link.setAttribute('href',URL.createObjectURL(blob));
    this.link.setAttribute('download', filename);
    this.link.setAttribute('target','_blank');
    this.link.textContent = label; 
  }

  attributeChangedCallback() {
    this.setContent();
  }
  
}
customElements.define('download-file', DownloadFileElement);


function init_app(flags) {

    const app = Elm.App.init({node: document.body, flags});

    return app;
}


window.init_app = init_app;
