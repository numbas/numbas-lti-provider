DIRNAME=$(notdir $(CURDIR))

ELMS=$(wildcard src/*.elm)

STATIC_DIR=../../static

$(STATIC_DIR)/group-sorter.js: app.js
	cp $< $@

app.js: src/App.elm load-app.js $(ELMS)
	-elm make $< --output=tmp.$@ 2> error.txt
	@echo "(function() {" > $@
	@cat tmp.$@ >> $@
	@rm tmp.$@
	@echo "}).apply(window);" >> $@
	@cat load-app.js >> $@
	@cat error.txt
