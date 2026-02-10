DIRNAME=$(notdir $(CURDIR))

ELMS=$(wildcard src/*.elm)

STATIC_DIR=../../static

deploy: $(patsubst %, $(STATIC_DIR)/%, resource-analysis.js resource-analysis.css)

$(STATIC_DIR)/%: ./%
	cp $< $@

resource-analysis.js: src/App.elm load-app.js $(ELMS)
	-elm make --optimize $< --output=tmp.$@
	@echo "(function() {" > $@
	@cat tmp.$@ >> $@
	@rm tmp.$@
	@echo "}).apply(window);" >> $@
	@cat load-app.js >> $@
